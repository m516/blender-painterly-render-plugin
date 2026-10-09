// SPDX-License-Identifier: GPL-3.0-or-later
// Tests of painterly/kernel/integrator/path.h (T3.11) and of the helpers it calls: lobe selection
// (closure/lobe.h), the background (light/background.h), the spot falloff (light/spot.h) and the
// triangle normal (geom/triangle.h). The scene is the smallpaint reference of SPEC §9
// (smallpaint_scene_fixture.h), except the glass slab, which is a closed box built by hand. Every
// comparison is exact (==) or a count of pixels with an expected value, so no tolerance appears.
// The bit-parity with smallpaint_oracle is tested end to end in T3.16, not here.

#include <doctest/doctest.h>

#include <cmath>
#include <cstdint>
#include <limits>
#include <memory>
#include <vector>

#include "painterly/bvh/embree.h"
#include "painterly/kernel/bvh/bvh.h"
#include "painterly/kernel/closure/lobe.h"
#include "painterly/kernel/integrator/path.h"
#include "painterly/kernel/light/background.h"
#include "painterly/kernel/light/spot.h"
#include "painterly/util/math_double3.h"
#include "smallpaint_scene_fixture.h"

CCL_NAMESPACE_BEGIN

namespace {

using Fixture = SmallpaintSceneFixture;

// The image chain (SPEC §3) has no lane length. The fixture still needs one of at least 1.
constexpr int IMAGE_LANE_LENGTH = 1;
// Consecutive pixels of the image chain that the first test walks (T3.11 card).
constexpr int CHAIN_TEST_PIXELS = 100;
// The light is object 9 and analytic primitive 9 (SPEC §9), and both are the same index.
constexpr int LIGHT = Fixture::LIGHT_OBJECT_ID;
// Half-angle of the spot cone of the spot test, in radians. This is a scene parameter, not a tuned
// value. At this width the light's visible disc has pixels inside the cone and pixels outside it.
constexpr double SPOT_HALF_ANGLE = 0.3;
// Half-angle of the sun disk of the background test, in radians. A scene parameter.
constexpr double SUN_HALF_ANGLE = 0.1;

// The primary hit of pixel (row, col) of `pass`, along the jittered ray that the path uses (SPEC
// §7).
struct PrimaryHit {
  PainterlyRay ray;
  PainterlyIntersection isect;
  bool hit;
};

PrimaryHit primary_hit(const PainterlyGlobals kg, int row, int col, int pass)
{
  PrimaryHit h{};
  h.ray = painterly_camera_generate_ray(kg, row, col, pass, true);
  h.hit = painterly_scene_intersect(kg, h.ray, &h.isect);
  return h;
}

// The analytic primitive that a primary hit lies on, or -1.
int analytic_index(const PrimaryHit &h)
{
  if (h.hit && h.isect.kind == HIT_ANALYTIC) {
    return h.isect.index;
  }
  return -1;
}

// Marks every entry as VERTEX_END, so that the entries after a path's last vertex are not counted
// as diffuse. The path writes its vertices from index 0, so the entries it did not write keep this
// kind.
void clear_scratch(std::vector<PainterlyPathVertex> &scratch)
{
  for (PainterlyPathVertex &v : scratch) {
    v.kind = VERTEX_END;
  }
}

int count_kind(const std::vector<PainterlyPathVertex> &scratch, int kind)
{
  int count = 0;
  for (const PainterlyPathVertex &v : scratch) {
    if (v.kind == kind) {
      count++;
    }
  }
  return count;
}

// The pixel of index i in the image chain walk: row-major, one pass (SPEC §3).
int row_of(int i)
{
  return i / Fixture::WIDTH;
}

int col_of(int i)
{
  return i % Fixture::WIDTH;
}

// A glass box and an emitter behind it, for the two_sided test. The box is the cube [-1, 1] x
// [-1, 1] x [-3, -2] (a slab in front of the camera, which looks down -z). Each of its six faces
// has four vertices of its own, and every vertex carries the face's outward normal as its corner
// normal. The shading normal of a hit is therefore outward whatever the winding of the triangles
// (SPEC §6). The emitter is a square at z = -6 facing the camera, and it absorbs the path
// (continue_after_emitter = 0). Its material has a zero diffuse lobe, so it is not reflective.
struct GlassSlabScene {
  // Half side of the emitter square (object space). A scene parameter.
  static constexpr float EMITTER_HALF_SIZE = 1.5f;
  // The emitter's material emission, as the light of SPEC §9.
  static constexpr double EMITTER_EMISSION = Fixture::LIGHT_EMISSION;

  KernelPainterlyData data{};
  PainterlyGlobalsCPU globals{};
  std::vector<KernelPainterlyMaterial> materials;
  std::vector<KernelPainterlyLobe> lobes;
  std::vector<KernelPainterlyObject> objects;
  std::vector<KernelPainterlyMesh> meshes;
  std::vector<int> tri_material;
  std::vector<float> tri_vertices;
  std::vector<float> tri_corner_normals;
  std::unique_ptr<PainterlyEmbreeScene, void (*)(PainterlyEmbreeScene *)> bvh{
      nullptr, painterly_embree_scene_free};

  GlassSlabScene(const KernelPainterlyData &base, const int two_sided)
  {
    data = base;
    data.integrator.two_sided = two_sided;
    data.integrator.continue_after_emitter = 0;

    // Corners of the six faces, four per face (x, y, z), in the order of the quad that the
    // triangles below split: corners 0-1-2 and 0-2-3.
    const float faces[6][12] = {
        {-1, -1, -2, 1, -1, -2, 1, 1, -2, -1, 1, -2},    // +z, the front face, towards the camera
        {-1, -1, -3, -1, 1, -3, 1, 1, -3, 1, -1, -3},    // -z, the back face
        {1, -1, -3, 1, 1, -3, 1, 1, -2, 1, -1, -2},      // +x
        {-1, -1, -3, -1, -1, -2, -1, 1, -2, -1, 1, -3},  // -x
        {-1, 1, -3, -1, 1, -2, 1, 1, -2, 1, 1, -3},      // +y
        {-1, -1, -3, 1, -1, -3, 1, -1, -2, -1, -1, -2},  // -y
    };
    // Outward normal of each face, in the same order.
    const float face_normals[6][3] = {
        {0, 0, 1}, {0, 0, -1}, {1, 0, 0}, {-1, 0, 0}, {0, 1, 0}, {0, -1, 0}};
    const uint32_t quad_triangles[6] = {0, 1, 2, 0, 2, 3};

    std::vector<float> slab_vertices;
    std::vector<float> slab_normals;
    std::vector<uint32_t> slab_triangles;
    for (int f = 0; f < 6; f++) {
      const uint32_t first = uint32_t(4 * f);
      for (int c = 0; c < 4; c++) {
        for (int k = 0; k < 3; k++) {
          slab_vertices.push_back(faces[f][3 * c + k]);
          slab_normals.push_back(face_normals[f][k]);
        }
      }
      for (const uint32_t index : quad_triangles) {
        slab_triangles.push_back(first + index);
      }
    }

    // The emitter: a square at z = -6, facing the camera, with flat shading.
    const float h = EMITTER_HALF_SIZE;
    const float emitter_vertices[12] = {-h, -h, -6, h, -h, -6, h, h, -6, -h, h, -6};
    const uint32_t emitter_triangles[6] = {0, 1, 2, 0, 2, 3};

    // Per triangle: the object-space corners, and the corner normals of the slab (zero for the
    // emitter, which does not use them).
    const int slab_count = int(slab_triangles.size() / 3);
    const int emitter_count = int(sizeof(emitter_triangles) / sizeof(emitter_triangles[0]) / 3);
    for (int t = 0; t < slab_count; t++) {
      for (int k = 0; k < 3; k++) {
        const uint32_t v = slab_triangles[3 * t + k];
        for (int i = 0; i < 3; i++) {
          tri_vertices.push_back(slab_vertices[3 * v + i]);
        }
      }
      for (int k = 0; k < 3; k++) {
        const uint32_t v = slab_triangles[3 * t + k];
        for (int i = 0; i < 3; i++) {
          tri_corner_normals.push_back(slab_normals[3 * v + i]);
        }
      }
      tri_material.push_back(0);
    }
    for (int t = 0; t < emitter_count; t++) {
      for (int k = 0; k < 3; k++) {
        const uint32_t v = emitter_triangles[3 * t + k];
        for (int i = 0; i < 3; i++) {
          tri_vertices.push_back(emitter_vertices[3 * v + i]);
        }
      }
      for (int i = 0; i < 9; i++) {
        tri_corner_normals.push_back(0.0f);
      }
      tri_material.push_back(1);
    }

    // Glass lobe with the reference IOR (material 0), and a zero-albedo emitter (material 1).
    KernelPainterlyLobe glass{};
    glass.kind = LOBE_GLASS;
    glass.weight = make_double3(1.0);
    glass.ior = Fixture::GLASS_IOR;
    lobes.push_back(glass);
    KernelPainterlyLobe absorber{};
    absorber.kind = LOBE_DIFFUSE;
    absorber.weight = make_double3(0.0);
    lobes.push_back(absorber);

    KernelPainterlyMaterial glass_material{};
    glass_material.lobe_offset = 0;
    glass_material.num_lobes = 1;
    glass_material.svm_offset = -1;
    materials.push_back(glass_material);
    KernelPainterlyMaterial emitter_material{};
    emitter_material.lobe_offset = 1;
    emitter_material.num_lobes = 1;
    emitter_material.emission = make_double3(EMITTER_EMISSION);
    emitter_material.svm_offset = -1;
    materials.push_back(emitter_material);

    // Two objects with the identity transform: object 0 is the slab, object 1 the emitter.
    const float identity[12] = {1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0};
    for (int o = 0; o < 2; o++) {
      KernelPainterlyObject object{};
      for (int i = 0; i < 12; i++) {
        object.tfm[i] = identity[i];
        object.itfm[i] = identity[i];
      }
      object.mesh = o;
      object.object_id = o;
      objects.push_back(object);
    }
    KernelPainterlyMesh slab_mesh{};
    slab_mesh.tri_offset = 0;
    slab_mesh.num_tris = slab_count;
    slab_mesh.has_corner_normals = 1;
    meshes.push_back(slab_mesh);
    KernelPainterlyMesh emitter_mesh{};
    emitter_mesh.tri_offset = slab_count;
    emitter_mesh.num_tris = emitter_count;
    emitter_mesh.has_corner_normals = 0;
    meshes.push_back(emitter_mesh);

    // Embree copies the geometry. The scene keeps no pointer into these vectors.
    const PainterlyEmbreeMeshInput mesh_inputs[2] = {
        {slab_vertices.data(),
         slab_vertices.size() / 3,
         slab_triangles.data(),
         size_t(slab_count)},
        {emitter_vertices, 4, emitter_triangles, size_t(emitter_count)}};
    const PainterlyEmbreeObjectInput object_inputs[2] = {{0, identity}, {1, identity}};
    bvh.reset(painterly_embree_scene_create(mesh_inputs, 2, object_inputs, 2));

    globals.data = &data;
    globals.analytic = nullptr;
    globals.num_analytic = 0;
    globals.materials = materials.data();
    globals.num_materials = int(materials.size());
    globals.lobes = lobes.data();
    globals.num_lobes = int(lobes.size());
    globals.suns = nullptr;
    globals.objects = objects.data();
    globals.num_objects = int(objects.size());
    globals.meshes = meshes.data();
    globals.num_meshes = int(meshes.size());
    globals.tri_material = tri_material.data();
    globals.tri_vertices = tri_vertices.data();
    globals.tri_corner_normals = tri_corner_normals.data();
    globals.bvh = bvh.get();
  }

  GlassSlabScene(const GlassSlabScene &) = delete;
  GlassSlabScene &operator=(const GlassSlabScene &) = delete;

  PainterlyGlobals kg() const
  {
    return &globals;
  }
};

}  // namespace

TEST_CASE("painterly path: 100 consecutive pixels of the image chain give finite radiance")
{
  Fixture fixture(CHAIN_IMAGE, IMAGE_LANE_LENGTH);
  std::vector<PainterlyPathVertex> scratch(Fixture::MAX_DEPTH);
  uint64_t K = painterly_chain_start(fixture.data.integrator, 0, 0, 0);

  for (int i = 0; i < CHAIN_TEST_PIXELS; i++) {
    const PainterlyPathResult result = painterly_trace_pixel(
        fixture.kg(), row_of(i), col_of(i), 0, &K, scratch.data());
    CHECK(std::isfinite(result.radiance.x));
    CHECK(std::isfinite(result.radiance.y));
    CHECK(std::isfinite(result.radiance.z));
  }
}

TEST_CASE("painterly path: K advances by the number of diffuse vertices")
{
  Fixture fixture(CHAIN_IMAGE, IMAGE_LANE_LENGTH);
  std::vector<PainterlyPathVertex> scratch(Fixture::MAX_DEPTH);
  uint64_t K = painterly_chain_start(fixture.data.integrator, 0, 0, 0);

  uint64_t diffuse_total = 0;
  for (int i = 0; i < CHAIN_TEST_PIXELS; i++) {
    clear_scratch(scratch);
    const uint64_t K_before = K;
    const PainterlyPathResult result = painterly_trace_pixel(
        fixture.kg(), row_of(i), col_of(i), 0, &K, scratch.data());
    const uint64_t diffuse = uint64_t(count_kind(scratch, VERTEX_DIFFUSE));
    CHECK(K - K_before == diffuse);
    CHECK(result.k_consumed == diffuse);
    diffuse_total += diffuse;
  }
  // The walk must include diffuse bounces, or the equality above holds trivially.
  CHECK(diffuse_total > 0);
}

TEST_CASE(
    "painterly path: max_depth = 1 gives emission * gain on light primary hits and 0 elsewhere")
{
  Fixture fixture(CHAIN_IMAGE, IMAGE_LANE_LENGTH);
  fixture.data.integrator.max_depth = 1;
  const PainterlyGlobals kg = fixture.kg();
  std::vector<PainterlyPathVertex> scratch(1);
  const double expected = Fixture::LIGHT_EMISSION * fixture.data.integrator.emission_gain;

  int light_pixels = 0;
  for (int row = 0; row < Fixture::HEIGHT; row++) {
    for (int col = 0; col < Fixture::WIDTH; col++) {
      uint64_t K = 0;
      const PainterlyPathResult result = painterly_trace_pixel(
          kg, row, col, 0, &K, scratch.data());
      if (analytic_index(primary_hit(kg, row, col, 0)) == LIGHT) {
        light_pixels++;
        CHECK(result.radiance.x == expected);
        CHECK(result.radiance.y == expected);
        CHECK(result.radiance.z == expected);
      }
      else {
        CHECK(result.radiance.x == 0.0);
        CHECK(result.radiance.y == 0.0);
        CHECK(result.radiance.z == 0.0);
      }
    }
  }
  REQUIRE(light_pixels > 0);
}

TEST_CASE(
    "painterly path: a spot ghost sphere emits on its axis, not outside its cone, and is "
    "unchanged when disabled")
{
  Fixture fixture(CHAIN_IMAGE, IMAGE_LANE_LENGTH);
  fixture.data.integrator.max_depth = 1;
  const PainterlyGlobals kg = fixture.kg();
  std::vector<PainterlyPathVertex> scratch(1);
  const double expected = Fixture::LIGHT_EMISSION * fixture.data.integrator.emission_gain;

  // The axis points from the light's centre to the camera at the origin. The cone has a hard edge
  // (blend = 0), so a light pixel is lit iff its normal lies inside the cone (SPEC §5).
  const double3 axis = normalize(make_double3(0.0) - fixture.analytic[LIGHT].a);
  const double cos_half = std::cos(SPOT_HALF_ANGLE);
  fixture.analytic[LIGHT].spot = KernelPainterlySpotProfile{1, axis, cos_half, 0.0};

  int light_pixels = 0;
  bool outside_seen = false;
  double best_cos = -std::numeric_limits<double>::infinity();
  double radiance_on_axis = 0.0;
  for (int row = 0; row < Fixture::HEIGHT; row++) {
    for (int col = 0; col < Fixture::WIDTH; col++) {
      const PrimaryHit h = primary_hit(kg, row, col, 0);
      if (analytic_index(h) != LIGHT) {
        continue;
      }
      // The normal at the hit point, from the true centre (SPEC §5).
      const double3 P = h.ray.o + h.ray.d * h.isect.t;
      const double cos_angle = dot(painterly_analytic_normal(fixture.analytic[LIGHT], P), axis);

      uint64_t K = 0;
      const PainterlyPathResult result = painterly_trace_pixel(
          kg, row, col, 0, &K, scratch.data());
      const double want = (cos_angle > cos_half) ? expected : 0.0;
      CHECK(result.radiance.x == want);
      CHECK(result.radiance.y == want);
      CHECK(result.radiance.z == want);

      light_pixels++;
      outside_seen = outside_seen || (cos_angle <= cos_half);
      if (cos_angle > best_cos) {
        best_cos = cos_angle;
        radiance_on_axis = result.radiance.x;
      }
    }
  }
  REQUIRE(light_pixels > 0);
  // The light pixel nearest the axis is on the axis: it emits emission * gain exactly.
  CHECK(radiance_on_axis == expected);
  // Some light pixel lies outside the cone, and it gives 0.
  CHECK(outside_seen);

  // A disabled spot is ignored: every light pixel emits emission * gain.
  fixture.analytic[LIGHT].spot.enabled = 0;
  for (int row = 0; row < Fixture::HEIGHT; row++) {
    for (int col = 0; col < Fixture::WIDTH; col++) {
      if (analytic_index(primary_hit(kg, row, col, 0)) != LIGHT) {
        continue;
      }
      uint64_t K = 0;
      const PainterlyPathResult result = painterly_trace_pixel(
          kg, row, col, 0, &K, scratch.data());
      CHECK(result.radiance.x == expected);
      CHECK(result.radiance.y == expected);
      CHECK(result.radiance.z == expected);
    }
  }
}

TEST_CASE("painterly spot attenuation: cone edge, blend region, hard edge and disabled spot")
{
  KernelPainterlySpotProfile spot{1, make_double3(0.0, 0.0, 1.0), 0.5, 0.5};
  // f = (0.625 - 0.5) / ((1 - 0.5) * 0.5) = 0.5, and 3 * 0.25 - 2 * 0.25 * 0.5 = 0.5: all of these
  // are exact in binary.
  CHECK(painterly_spot_attenuation(spot, make_double3(0.0, 0.0, 0.625)) == 0.5);
  // f = 2 is clamped to 1.
  CHECK(painterly_spot_attenuation(spot, make_double3(0.0, 0.0, 1.0)) == 1.0);
  // f = 0 at the cone edge.
  CHECK(painterly_spot_attenuation(spot, make_double3(0.0, 0.0, 0.5)) == 0.0);
  // f < 0 outside the cone.
  CHECK(painterly_spot_attenuation(spot, make_double3(0.0, 0.0, -1.0)) == 0.0);

  // blend = 0 is a hard edge: 1 iff dot > cos_half_angle.
  spot.blend = 0.0;
  CHECK(painterly_spot_attenuation(spot, make_double3(0.0, 0.0, 0.625)) == 1.0);
  CHECK(painterly_spot_attenuation(spot, make_double3(0.0, 0.0, 0.5)) == 0.0);

  // A disabled spot is isotropic.
  spot.enabled = 0;
  CHECK(painterly_spot_attenuation(spot, make_double3(0.0, 0.0, -1.0)) == 1.0);
}

TEST_CASE("painterly path: two_sided does not change the exit of a glass slab (SPEC §6)")
{
  const Fixture reference(CHAIN_IMAGE, IMAGE_LANE_LENGTH);
  const GlassSlabScene one_sided(reference.data, 0);
  const GlassSlabScene two_sided(reference.data, 1);
  REQUIRE(one_sided.bvh != nullptr);
  REQUIRE(two_sided.bvh != nullptr);

  // The emitter's emission times the gain: a path that exits towards it gives this value.
  const double expected = GlassSlabScene::EMITTER_EMISSION *
                          reference.data.integrator.emission_gain;
  std::vector<PainterlyPathVertex> scratch(reference.data.integrator.max_depth);
  int reached_emitter = 0;
  int exits_elsewhere = 0;
  for (int row = 0; row < Fixture::HEIGHT; row++) {
    for (int col = 0; col < Fixture::WIDTH; col++) {
      uint64_t K_one = 0;
      uint64_t K_two = 0;
      const PainterlyPathResult a = painterly_trace_pixel(
          one_sided.kg(), row, col, 0, &K_one, scratch.data());
      const PainterlyPathResult b = painterly_trace_pixel(
          two_sided.kg(), row, col, 0, &K_two, scratch.data());
      // Exact equality: the glass lobe ignores two_sided, so the exit is the same bit for bit.
      CHECK(a.radiance.x == b.radiance.x);
      CHECK(a.radiance.y == b.radiance.y);
      CHECK(a.radiance.z == b.radiance.z);
      CHECK((a.radiance.x == 0.0 || a.radiance.x == expected));
      if (a.radiance.x == expected) {
        reached_emitter++;
      }
      else {
        exits_elsewhere++;
      }
    }
  }
  // Both outcomes occur, so the equality above is not trivial.
  CHECK(reached_emitter > 0);
  CHECK(exits_elsewhere > 0);
}

TEST_CASE(
    "painterly background: a miss gives background * gain, plus each sun whose disk holds the "
    "direction")
{
  Fixture fixture(CHAIN_IMAGE, IMAGE_LANE_LENGTH);
  fixture.globals.num_analytic = 0;  // Every ray misses.
  fixture.data.background.radiance = make_double3(1.0, 2.0, 3.0);
  const PainterlyGlobals kg = fixture.kg();
  std::vector<PainterlyPathVertex> scratch(Fixture::MAX_DEPTH);

  // No suns: a miss gives 0.0 + background * gain (SPEC §6), so (2, 4, 6).
  for (int row = 0; row < Fixture::HEIGHT; row++) {
    for (int col = 0; col < Fixture::WIDTH; col++) {
      uint64_t K = 0;
      const PainterlyPathResult result = painterly_trace_pixel(
          kg, row, col, 0, &K, scratch.data());
      CHECK(result.radiance.x == 2.0);
      CHECK(result.radiance.y == 4.0);
      CHECK(result.radiance.z == 6.0);
    }
  }

  // One sun whose disk is centred on -z. Its radiance adds to the background in sun order.
  fixture.suns.push_back(KernelPainterlySun{
      make_double3(0.0, 0.0, -1.0), std::cos(SUN_HALF_ANGLE), make_double3(10.0, 20.0, 30.0)});
  fixture.globals.suns = fixture.suns.data();
  fixture.data.background.num_suns = 1;
  const double3 inside = painterly_background_radiance(kg, make_double3(0.0, 0.0, -1.0));
  CHECK(inside.x == 11.0);
  CHECK(inside.y == 22.0);
  CHECK(inside.z == 33.0);
  // Outside the disk, only the background remains.
  const double3 outside = painterly_background_radiance(kg, make_double3(1.0, 0.0, 0.0));
  CHECK(outside.x == 1.0);
  CHECK(outside.y == 2.0);
  CHECK(outside.z == 3.0);
}

TEST_CASE("painterly primary object id: the object of the unjittered primary hit, or -1 on a miss")
{
  Fixture fixture(CHAIN_IMAGE, IMAGE_LANE_LENGTH);
  const PainterlyGlobals kg = fixture.kg();

  // The reference scene is closed, so every primary ray hits an object (SPEC §9).
  int light_pixels = 0;
  for (int row = 0; row < Fixture::HEIGHT; row++) {
    for (int col = 0; col < Fixture::WIDTH; col++) {
      const int id = painterly_primary_object_id(kg, row, col);
      CHECK(id >= 0);
      CHECK(id <= LIGHT);
      if (id == LIGHT) {
        light_pixels++;
      }
    }
  }
  CHECK(light_pixels > 0);

  // An empty scene is missed by every ray.
  fixture.globals.num_analytic = 0;
  CHECK(painterly_primary_object_id(kg, 16, 16) == -1);
}

TEST_CASE("painterly lobe selection: one lobe is unchanged, a zero-luminance lobe is never chosen")
{
  Fixture fixture(CHAIN_IMAGE, IMAGE_LANE_LENGTH);
  // Lobes 0 (one lobe), 1-2 (a zero-luminance diffuse and a unit mirror) and 3-4 (two equal
  // lobes). Each material points at its own lobes.
  std::vector<KernelPainterlyLobe> lobes(5);
  lobes[0] = KernelPainterlyLobe{LOBE_MIRROR, make_double3(0.5, 0.25, 0.125), 0.0};
  lobes[1] = KernelPainterlyLobe{LOBE_DIFFUSE, make_double3(0.0), 0.0};
  lobes[2] = KernelPainterlyLobe{LOBE_MIRROR, make_double3(1.0), 0.0};
  lobes[3] = KernelPainterlyLobe{LOBE_MIRROR, make_double3(1.0), 0.0};
  lobes[4] = KernelPainterlyLobe{LOBE_DIFFUSE, make_double3(1.0), 0.0};
  const KernelPainterlyMaterial single{0, 1, make_double3(0.0), -1};
  const KernelPainterlyMaterial zero_and_mirror{1, 2, make_double3(0.0), -1};
  const KernelPainterlyMaterial equal_pair{3, 2, make_double3(0.0), -1};

  PainterlyGlobalsCPU kg = fixture.globals;
  kg.lobes = lobes.data();

  bool mirror_seen = false;
  bool diffuse_seen = false;
  for (int row = 0; row < Fixture::HEIGHT; row++) {
    for (int col = 0; col < Fixture::WIDTH; col++) {
      // One lobe: returned unchanged, with no draw (p = 1).
      const KernelPainterlyLobe a = painterly_select_lobe(&kg, single, row, col, 0, 0);
      CHECK(a.kind == LOBE_MIRROR);
      CHECK(a.weight.x == 0.5);
      CHECK(a.weight.y == 0.25);
      CHECK(a.weight.z == 0.125);

      // The zero-luminance lobe is never chosen, and the chosen lobe has p = 1, so its weight is
      // unchanged.
      const KernelPainterlyLobe b = painterly_select_lobe(&kg, zero_and_mirror, row, col, 0, 0);
      CHECK(b.kind == LOBE_MIRROR);
      CHECK(b.weight.x == 1.0);
      CHECK(b.weight.y == 1.0);
      CHECK(b.weight.z == 1.0);

      // Two equal lobes: p = 1/2 for each, so the weight doubles. Both kinds occur over pixels.
      const KernelPainterlyLobe c = painterly_select_lobe(&kg, equal_pair, row, col, 0, 0);
      CHECK(c.weight.x == 2.0);
      CHECK(c.weight.y == 2.0);
      CHECK(c.weight.z == 2.0);
      mirror_seen = mirror_seen || (c.kind == LOBE_MIRROR);
      diffuse_seen = diffuse_seen || (c.kind == LOBE_DIFFUSE);
    }
  }
  CHECK(mirror_seen);
  CHECK(diffuse_seen);
}

CCL_NAMESPACE_END
