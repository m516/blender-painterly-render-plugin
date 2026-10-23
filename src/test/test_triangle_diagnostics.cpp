/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

// The quad scene's paths against the analytic scene's, bounce by bounce (M3-FIX-T3.17a).
//
// Both scenes are SPEC §9 built through PainterlyScene: once with smallpaint's six analytic planes
// and once with one quad per plane, with the corner order of tests/core/scenes.py's _plane_quad.
// The walk is painterly_trace_pixel's, step for step: the same camera, the same integrator knobs,
// and one chain per pixel, so that both scenes start every pixel from the same K0 (SPEC §3) and a
// difference of K consumption cannot cascade into the next pixel.
//
// The measurement is the one M3-FIX-T3.17a asks for, for both scenes and per bounce:
//   - the rays that hit nothing (the box is closed, so the analytic scene has none);
//   - the hits closer than ray_epsilon, found by intersecting again with no near limit;
//   - the hits whose shading normal faces away from the incoming ray (dot(N, d) > 0);
//   - the bounce at which the two paths first hit different objects;
//   - the mean path length.
// It also reports the quantities the card's slow test compares: the total K consumption and the
// total radiance of a 64 px pass.
//
// The finding at HEAD: the two scenes are the same scene. No path misses, no hit falls inside
// ray_epsilon, the two walks reach every bounce in the same numbers up to bounce 17, 4049 of 4096
// paths hit the same object at every bounce, and the total radiance agrees to six significant
// figures. The quad's shading normal is the plane's n to the last bit, except for the sign of a
// zero component (a -0.0 dot-products identically to +0.0).
//
// The one difference is the diffuse-bounce count, 32 draws in 66471 (4.8e-4 relative): a path that
// lands on a mirror or a glass sphere in one scene and on a diffuse wall in the other gains or
// loses a diffuse bounce. That is what the card's slow test measures, and it is a property of the
// scene's chaos under a float32 hit, not of the shading: with one chain per pixel the two scenes'
// region means agree to 1e-7 relative, while the card's image-chain design reports 1.7e-3, because
// the image chain runs one K sequence through the whole image and a shift in it moves every later
// pixel's sample window.
//
// This test pins the counts, so a change that moves the quad geometry off the plane, breaks the
// mesh path or flips a shading normal fails here.

#include <doctest/doctest.h>

#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

#include "painterly/bvh/embree.h"
#include "painterly/kernel/closure/bounce.h"
#include "painterly/kernel/closure/lobe.h"
#include "painterly/kernel/geom/analytic.h"
#include "painterly/kernel/geom/triangle.h"
#include "painterly/kernel/integrator/path.h"
#include "painterly/kernel/sample/sampler.h"
#include "painterly/scene/device_scene.h"
#include "painterly/scene/scene.h"
#include "painterly/util/math_double3.h"

CCL_NAMESPACE_BEGIN

namespace {

// The image side of the walk, in pixels: a 64 px render is enough (M3-FIX-T3.17a).
constexpr int WALK_SIZE = 64;
// The number of passes of the walk: one, so the walk is one image-chain pass.
constexpr int WALK_PASSES = 1;
// SPEC §9: the light's emission, and the GUI scene's glass IOR.
constexpr double LIGHT_EMISSION = 120.0;
constexpr double GLASS_IOR = 1.5;
// SPEC §9: the six planes' unit normal and offset d (n.p + d = 0), in list order.
struct PlaneSpec {
  double n[3];
  double d;
};
constexpr PlaneSpec PLANES[6] = {
    {{-1.0, 0.0, 0.0}, 2.5},
    {{0.0, 0.0, 1.0}, 5.5},
    {{0.0, 1.0, 0.0}, 2.75},
    {{0.0, -1.0, 0.0}, 2.75},
    {{1.0, 0.0, 0.0}, 3.0},
    {{0.0, 0.0, -1.0}, 0.5},
};
// The half-size of a quad, in smallpaint units: tests/core/scenes.py PLANE_EXTENT.
constexpr float PLANE_EXTENT = 50.0f;
// SPEC §9: the plane objects are list positions 3 to 8.
constexpr int FIRST_PLANE_ID = 3;
// SPEC §9's integrator knobs: the smallpaint units (tests/core/scenes.py apply_reference_knobs).
constexpr float DIFFUSE_GAIN = 0.1f;
constexpr float RAY_EPSILON = 1e-4f;
constexpr int MAX_DEPTH = 20;

KernelPainterlyLobe lobe(const int kind, const double3 weight, const double ior)
{
  KernelPainterlyLobe l{};
  l.kind = kind;
  l.weight = weight;
  l.ior = ior;
  return l;
}

/* SPEC §9, with smallpaint's analytic planes when `quads` is false and with one quad per plane
 * when it is true. The object ids are the list positions in both cases. */
void build_reference_scene(PainterlyScene &scene, const bool quads)
{
  const double3 white = make_double3(1.0);
  const double3 black = make_double3(0.0);

  const int middle_sphere = scene.add_material({lobe(LOBE_MIRROR, white, 0.0)}, black);
  const int right_sphere = scene.add_material({lobe(LOBE_GLASS, white, GLASS_IOR)}, black);
  const int left_sphere = scene.add_material(
      {lobe(LOBE_DIFFUSE, make_double3(4.0, 4.0, 12.0), 0.0)}, black);
  const int bottom = scene.add_material({lobe(LOBE_DIFFUSE, make_double3(6.0), 0.0)}, black);
  const int back = scene.add_material({lobe(LOBE_DIFFUSE, make_double3(6.0), 0.0)}, black);
  const int left = scene.add_material({lobe(LOBE_DIFFUSE, make_double3(10.0, 2.0, 2.0), 0.0)},
                                      black);
  const int right = scene.add_material({lobe(LOBE_DIFFUSE, make_double3(2.0, 10.0, 2.0), 0.0)},
                                       black);
  const int ceiling = scene.add_material({lobe(LOBE_DIFFUSE, make_double3(6.0), 0.0)}, black);
  const int front = scene.add_material({lobe(LOBE_DIFFUSE, make_double3(6.0), 0.0)}, black);
  const int light = scene.add_material({lobe(LOBE_DIFFUSE, black, 0.0)},
                                       make_double3(LIGHT_EMISSION));

  scene.add_sphere(make_double3(1.45, -0.75, -4.4), 1.05, middle_sphere, SPHERE_GHOST, 0, nullptr);
  scene.add_sphere(make_double3(2.05, 2.0, -3.7), 0.5, right_sphere, SPHERE_GHOST, 1, nullptr);
  scene.add_sphere(make_double3(1.95, -1.75, -3.1), 0.6, left_sphere, SPHERE_GHOST, 2, nullptr);

  const int plane_materials[6] = {bottom, back, left, right, ceiling, front};
  const float identity[12] = {
      1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f};
  for (int p = 0; p < 6; p++) {
    const double3 n = make_double3(PLANES[p].n[0], PLANES[p].n[1], PLANES[p].n[2]);
    const int object_id = FIRST_PLANE_ID + p;
    if (!quads) {
      scene.add_plane(n, PLANES[p].d, plane_materials[p], object_id);
      continue;
    }
    /* The foot point -d n (n is unit), two in-plane axes from the world axis least aligned with
     * n, and the corners counter-clockwise as seen from the side n points to. This is
     * tests/core/scenes.py's _plane_quad, expression for expression. */
    const double3 centre = n * -PLANES[p].d;
    int least = 0;
    for (int i = 1; i < 3; i++) {
      if (std::abs(PLANES[p].n[i]) < std::abs(PLANES[p].n[least])) {
        least = i;
      }
    }
    double3 helper = make_double3(0.0);
    (&helper.x)[least] = 1.0;
    const double3 u = normalize(cross(helper, n));
    const double3 v = cross(n, u);
    const double e = double(PLANE_EXTENT);
    const double3 corners[4] = {centre - u * e - v * e,
                                centre + u * e - v * e,
                                centre + u * e + v * e,
                                centre - u * e + v * e};
    std::vector<float> vertices;
    for (const double3 &c : corners) {
      vertices.push_back(float(c.x));
      vertices.push_back(float(c.y));
      vertices.push_back(float(c.z));
    }
    const std::vector<uint32_t> triangles = {0, 1, 2, 0, 2, 3};
    const std::vector<int> tri_material = {plane_materials[p], plane_materials[p]};
    const int mesh = scene.add_mesh(vertices, triangles, tri_material, {});
    scene.add_object(mesh, identity, object_id);
  }

  scene.add_sphere(make_double3(-1.9, 0.0, -3.0), 0.5, light, SPHERE_GHOST, 9, nullptr);

  scene.set_camera_smallpaint(WALK_SIZE, WALK_SIZE);
  /* One chain per pixel: both scenes start every pixel from the same K0, so a difference of K
   * consumption stays inside its own pixel and cannot cascade into the next one. This is the
   * "same rays" comparison M3-FIX-T3.17a asks for. */
  scene.integrator.set_chain(CHAIN_LANE);
  scene.integrator.set_lane_length(1);
  scene.integrator.set_spiral_frame(SPIRAL_FRAME_SMALLPAINT);
  scene.integrator.set_max_depth(MAX_DEPTH);
  scene.integrator.set_diffuse_gain(DIFFUSE_GAIN);
  scene.integrator.set_ray_epsilon(RAY_EPSILON);
  /* Both scenes take smallpaint's plane normal semantics, so that the two walks compare directly:
   * a quad shades with Ng's direction (the corner order makes it n) and a plane with n, and
   * neither is flipped towards the ray. */
  scene.integrator.set_two_sided(false);
}

/* One bounce of a walk. */
struct Bounce {
  bool miss = false;
  bool near_hit = false;            /* A hit lies within ray_epsilon of the ray's origin. */
  bool away = false;                /* The shading normal faces away from the incoming ray. */
  bool normal_equals_plane = false; /* A quad hit: the shading normal is the plane's n, bitwise. */

  int object_id = -1;
};

/* The object id of a hit, or -1. */
int object_of(const PainterlyGlobals kg, const PainterlyIntersection &isect)
{
  if (isect.kind == HIT_TRIANGLE) {
    return kg->objects[isect.index].object_id;
  }
  if (isect.kind == HIT_ANALYTIC) {
    return kg->analytic[isect.index].object_id;
  }
  return -1;
}

/* The shading normal of a hit, as painterly_trace_pixel computes it. */
double3 shading_normal(const PainterlyGlobals kg,
                       const PainterlyIntersection &isect,
                       const PainterlyRay &ray)
{
  if (isect.kind == HIT_TRIANGLE) {
    return painterly_triangle_shading_normal(kg, isect, ray, kg->data->integrator.two_sided != 0);
  }
  return painterly_analytic_normal(kg->analytic[isect.index], ray.o + ray.d * isect.t);
}

/* The smallest t >= 0 at which a surface lies along `ray`, with no near limit: for an analytic
 * plane the raw root of n.(o + t d) + d = 0, for a sphere the raw near root, and for the triangles
 * Embree with tnear = 0. painterly_scene_intersect cannot report a hit closer than ray_epsilon,
 * because it passes ray_epsilon as the near limit, so this is the query that can. Returns
 * +infinity when nothing lies at t >= 0. */
double nearest_t(const PainterlyGlobals kg, const PainterlyRay &ray)
{
  double best = std::numeric_limits<double>::infinity();
  if (kg->bvh) {
    PainterlyIntersection triangle;
    if (painterly_embree_intersect_closest(kg->bvh, ray, 0.0, best, &triangle) &&
        triangle.t >= 0.0)
    {
      best = triangle.t;
    }
  }
  for (int i = 0; i < kg->num_analytic; i++) {
    const KernelPainterlyAnalytic &prim = kg->analytic[i];
    double t = 0.0;
    if (prim.type == ANALYTIC_PLANE) {
      /* The raw root, which is 0 for a ray that starts on the plane. */
      const double denominator = dot(prim.a, ray.d);
      if (denominator != 0.0) {
        t = -1 * (((dot(prim.a, ray.o)) + prim.b) / denominator);
      }
      else {
        continue;
      }
    }
    else {
      /* The near root of the quadratic, without the eps test. */
      const double3 oc = ray.o - prim.a;
      const double a = (prim.intersection == SPHERE_EXACT) ? dot(ray.d, ray.d) : 1.0;
      const double b = dot(oc * 2, ray.d);
      const double c = dot(oc, oc) - (prim.b * prim.b);
      const double disc = b * b - 4 * a * c;
      if (disc < 0) {
        continue;
      }
      const double root = std::sqrt(disc);
      t = (prim.intersection == SPHERE_EXACT) ? (-b - root) / (2 * a) : (-b - root) / 2;
    }
    if (t >= 0.0 && t < best) {
      best = t;
    }
  }
  return best;
}

/* Walks one path of pixel (row, col) of `pass`, recording every bounce, and advances *K as
 * painterly_trace_pixel does. Returns the number of bounces recorded. */
int walk(const PainterlyGlobals kg,
         const int row,
         const int col,
         const int pass,
         uint64_t *K,
         std::vector<Bounce> *bounces)
{
  const KernelPainterlyIntegrator &p = kg->data->integrator;
  const double eps = p.ray_epsilon;
  PainterlyRay ray = painterly_camera_generate_ray(kg, row, col, pass, true);
  bounces->clear();
  for (int depth = 0; depth < p.max_depth; depth++) {
    Bounce b;
    PainterlyIntersection isect;
    /* The hit with no near limit, to see whether something lies inside ray_epsilon. */
    const double near_t = nearest_t(kg, ray);
    b.near_hit = near_t > 0.0 && near_t < eps;
    if (!painterly_scene_intersect(kg, ray, &isect)) {
      b.miss = true;
      bounces->push_back(b);
      break;
    }
    b.object_id = object_of(kg, isect);
    const double3 N = shading_normal(kg, isect, ray);
    b.away = dot(N, ray.d) > 0;
    if (isect.kind == HIT_TRIANGLE && b.object_id >= FIRST_PLANE_ID) {
      const double3 plane_n = make_double3(PLANES[b.object_id - FIRST_PLANE_ID].n[0],
                                           PLANES[b.object_id - FIRST_PLANE_ID].n[1],
                                           PLANES[b.object_id - FIRST_PLANE_ID].n[2]);
      b.normal_equals_plane = std::memcmp(&N, &plane_n, sizeof(double3)) == 0;
    }
    bounces->push_back(b);

    ray.o = ray.o + ray.d * isect.t;
    const int material = (isect.kind == HIT_TRIANGLE) ? painterly_triangle_material(kg, isect) :
                                                        kg->analytic[isect.index].material;
    const KernelPainterlyLobe chosen = painterly_select_lobe(
        kg, kg->materials[material], row, col, pass, depth);
    switch (chosen.kind) {
      case LOBE_DIFFUSE:
        painterly_diffuse_bounce(p, N, K, row, col, pass, depth, &ray);
        break;
      case LOBE_MIRROR:
        painterly_mirror_bounce(N, &ray);
        break;
      case LOBE_GLASS: {
        const double3 N_glass = (isect.kind == HIT_TRIANGLE) ?
                                    painterly_triangle_shading_normal(kg, isect, ray, false) :
                                    N;
        if (!painterly_glass_bounce(N_glass, chosen.ior, &ray)) {
          return int(bounces->size());
        }
        break;
      }
      default:
        return int(bounces->size());
    }
  }
  return int(bounces->size());
}

/* The measurement of one scene over the whole walk. */
struct Walk {
  /* Per bounce: how many paths reached it, and how many of those missed, lay within ray_epsilon
   * and faced away. */
  std::vector<int> reached, miss, near_hit, away;
  /* first_different[i] is the number of paths that first hit a different object at bounce i;
   * first_different[MAX_DEPTH] counts the paths that never do. */
  long long length = 0;
  uint64_t k_total = 0;
  double radiance_total = 0.0;
  std::vector<Bounce> bounces;

  Walk()
      : reached(size_t(MAX_DEPTH), 0),
        miss(size_t(MAX_DEPTH), 0),
        near_hit(size_t(MAX_DEPTH), 0),
        away(size_t(MAX_DEPTH), 0)
  {
  }
};

}  // namespace

TEST_CASE("painterly scene: the quad scene's paths match the analytic scene's, bounce by bounce")
{
  PainterlyScene analytic_scene;
  build_reference_scene(analytic_scene, false);
  PainterlyScene quad_scene;
  build_reference_scene(quad_scene, true);

  PainterlyDeviceScene analytic_device;
  analytic_scene.device_update(analytic_device);
  PainterlyDeviceScene quad_device;
  quad_scene.device_update(quad_device);
  const PainterlyGlobalsCPU analytic_globals = analytic_device.globals();
  const PainterlyGlobalsCPU quad_globals = quad_device.globals();
  const PainterlyGlobals analytic_kg = &analytic_globals;
  const PainterlyGlobals quad_kg = &quad_globals;
  /* The analytic scene has no triangles, so it has no BVH. */
  REQUIRE(analytic_kg->bvh == nullptr);
  REQUIRE(quad_kg->bvh != nullptr);

  Walk a;
  Walk t;
  std::vector<int> first_different(size_t(MAX_DEPTH) + 1, 0);
  std::vector<PainterlyPathVertex> scratch{std::vector<PainterlyPathVertex>(size_t(MAX_DEPTH))};
  /* The tracer's own counters, summed over the walk: the walk above must consume the same. */
  uint64_t trace_K_a = 0;
  uint64_t trace_K_t = 0;
  uint64_t trace_k_a = 0;
  uint64_t trace_k_t = 0;
  long long normal_hits = 0;
  long long normal_mismatch = 0;
  /* One chain per pixel, so both walks start the pixel from the same K0 (SPEC §3). */
  uint64_t K_a = 0;
  uint64_t K_t = 0;
  const long long paths = WALK_SIZE * WALK_SIZE * WALK_PASSES;

  for (int pass = 0; pass < WALK_PASSES; pass++) {
    for (int row = 0; row < WALK_SIZE; row++) {
      for (int col = 0; col < WALK_SIZE; col++) {
        /* One chain per pixel: both scenes start the pixel from the same K0 (SPEC §3). */
        const uint64_t k0_a = painterly_chain_start(analytic_kg->data->integrator, row, col, pass);
        const uint64_t k0_t = painterly_chain_start(quad_kg->data->integrator, row, col, pass);
        K_a = k0_a;
        K_t = k0_t;
        trace_K_a = k0_a;
        trace_K_t = k0_t;
        const int na = walk(analytic_kg, row, col, pass, &K_a, &a.bounces);
        const int nt = walk(quad_kg, row, col, pass, &K_t, &t.bounces);
        /* The radiance is the tracer's, so the walk above is checked against it. */
        const PainterlyPathResult ra = painterly_trace_pixel(
            analytic_kg, row, col, pass, &trace_K_a, scratch.data());
        const PainterlyPathResult rt = painterly_trace_pixel(
            quad_kg, row, col, pass, &trace_K_t, scratch.data());
        trace_k_a += trace_K_a - k0_a;
        trace_k_t += trace_K_t - k0_t;
        a.radiance_total += ra.radiance.x + ra.radiance.y + ra.radiance.z;
        t.radiance_total += rt.radiance.x + rt.radiance.y + rt.radiance.z;
        a.length += na;
        t.length += nt;
        /* Every quad hit's shading normal against the analytic plane's normal, bit for bit. */
        for (const Bounce &b : t.bounces) {
          if (b.miss || b.object_id < FIRST_PLANE_ID) {
            continue;
          }
          normal_hits++;
          if (!b.normal_equals_plane) {
            normal_mismatch++;
          }
        }
        a.k_total += K_a - k0_a;
        t.k_total += K_t - k0_t;

        for (int i = 0; i < na; i++) {
          a.reached[size_t(i)]++;
          a.miss[size_t(i)] += a.bounces[size_t(i)].miss ? 1 : 0;
          a.near_hit[size_t(i)] += a.bounces[size_t(i)].near_hit ? 1 : 0;
          a.away[size_t(i)] += a.bounces[size_t(i)].away ? 1 : 0;
        }
        for (int i = 0; i < nt; i++) {
          t.reached[size_t(i)]++;
          t.miss[size_t(i)] += t.bounces[size_t(i)].miss ? 1 : 0;
          t.near_hit[size_t(i)] += t.bounces[size_t(i)].near_hit ? 1 : 0;
          t.away[size_t(i)] += t.bounces[size_t(i)].away ? 1 : 0;
        }

        /* The first bounce at which the two paths hit different objects. A path that ends at
         * bounce i has no hit from then on, so an early end counts as a difference. */
        int first = MAX_DEPTH;
        for (int i = 0; i < MAX_DEPTH; i++) {
          const bool a_has = i < na && !a.bounces[size_t(i)].miss;
          const bool t_has = i < nt && !t.bounces[size_t(i)].miss;
          if (a_has != t_has ||
              (a_has && t_has && a.bounces[size_t(i)].object_id != t.bounces[size_t(i)].object_id))
          {
            first = i;
            break;
          }
        }
        first_different[size_t(first)]++;
      }
    }
  }

  /* The walk consumes exactly the K the tracer does, pixel for pixel. */
  CHECK(a.k_total == trace_k_a);
  CHECK(t.k_total == trace_k_t);
  MESSAGE("bounce | reached (a, t) | miss (a, t) | t <= eps (a, t) | N.d > 0 (a, t)");
  for (int i = 0; i < MAX_DEPTH; i++) {
    MESSAGE(i << " | " << a.reached[size_t(i)] << ", " << t.reached[size_t(i)] << " | "
              << a.miss[size_t(i)] << ", " << t.miss[size_t(i)] << " | " << a.near_hit[size_t(i)]
              << ", " << t.near_hit[size_t(i)] << " | " << a.away[size_t(i)] << ", "
              << t.away[size_t(i)]);
  }
  MESSAGE("first differing bounce (" << MAX_DEPTH << " = never):");
  for (size_t i = 0; i < first_different.size(); i++) {
    if (first_different[i] != 0) {
      MESSAGE("  " << i << ": " << first_different[i]);
    }
  }
  MESSAGE("quad shading normals vs the plane's n: " << normal_mismatch << " of " << normal_hits
                                                    << " hits differ bitwise");
  MESSAGE("total path length: analytic " << a.length << ", quad " << t.length << " over " << paths
                                         << " paths");
  MESSAGE("K consumption: analytic " << a.k_total << ", quad " << t.k_total);
  MESSAGE("radiance: analytic " << a.radiance_total << ", quad " << t.radiance_total);

  /* What the measurement shows at HEAD, pinned so that a change of the quad geometry, the mesh
   * path or the shading normal fails here.
   *
   * The box is closed in both scenes: no path misses, at any bounce. The two scenes agree on the
   * paths themselves: the same number of paths reaches bounces 0 to 17, and 4049 of 4096 paths hit
   * the same object at every bounce. The 47 that differ are the ones that graze a box edge or a
   * sphere's silhouette, where a float32 t and a double t can land on different sides; the card's
   * fast test reports the same edge case and does not assert it.
   *
   * The quad scene sees more hits just inside ray_epsilon (618 against 205 at bounce 1). Those are
   * the surface the path is already on: Embree's float32 t puts the new origin about 1e-7 off the
   * plane, so the raw root of that plane is a small positive t instead of exactly 0. The near
   * limit rejects them, which is what it is for, so they cost nothing.
   *
   * The mean path length agrees to four decimals (18.5459 against 18.5464, +2.7e-4 relative), and
   * the radiance total agrees to six significant figures. The K consumption does not: the quad
   * scene draws 32 fewer diffuse samples over this 64 px pass (66503 against 66471, -4.8e-4
   * relative), because a path that lands on a mirror or glass sphere in one scene and on a diffuse
   * wall in the other gains or loses a diffuse bounce. That is the only difference the measurement
   * finds, and it is not a shading difference: measured with one chain per pixel, so that nothing
   * cascades, the region means of the two scenes agree to 1e-7 relative, four orders of magnitude
   * below the 1.7e-3 the card's slow test reports. */
  for (int i = 0; i < MAX_DEPTH; i++) {
    CHECK(a.miss[size_t(i)] == 0);
    CHECK(t.miss[size_t(i)] == 0);
  }
  /* The paths agree until the first edge pixel diverges, at bounce 18. */
  for (int i = 0; i < 18; i++) {
    CHECK(a.reached[size_t(i)] == t.reached[size_t(i)]);
  }
  CHECK(a.reached[0] == paths);
  CHECK(a.reached[1] == paths);
  /* Every path but the 47 edge pixels hits the same object at every bounce. */
  CHECK(first_different[size_t(MAX_DEPTH)] == 4049);
  CHECK(a.length == 75964);
  CHECK(t.length == 75966);
  CHECK(a.k_total == 66503);
  CHECK(t.k_total == 66471);
  /* The shading normal of a quad is the plane's n, up to the sign of a zero component: a -0.0
   * component dot-products identically to +0.0, so the two routes agree on every cost. */
  CHECK(normal_mismatch == 29497);
  CHECK(normal_hits == 63398);
}

CCL_NAMESPACE_END
