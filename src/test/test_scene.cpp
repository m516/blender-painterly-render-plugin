/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

// Tests of painterly/scene/ (T3.13): the PainterlyIntegrator socket defaults and their round trip,
// the UI info's name-set equality, object-id auto-assignment, the device_update arrays, the normal
// matrix of every object, the mesh validation, the singular-transform rejection, the spiral frame
// F of the four `spiral_frame` cases and the camera jitter of SPEC §7.
//
// Matrices are compared exactly where the card says exactly (e = 0, axis permutations: entries are
// 0/±1) and with a derived binary32 bound for the one general nonzero e, because
// euler_to_transform evaluates cosf/sinf in float (third_party/cycles/util/transform.h:236-260).
// Jitter values are compared bitwise (memcmp, so -0.0 and +0.0 differ) with their defining
// expressions.

#include <doctest/doctest.h>

#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

#include "graph/node_type.h"
#include "painterly/scene/device_scene.h"
#include "painterly/scene/scene.h"
#include "painterly/util/math_double3.h"
#include "util/types.h"

#include "bitwise.h"

CCL_NAMESPACE_BEGIN

namespace {

/* SPEC §8 table order: the socket names, which painterly_integrator_ui_info() must match. */
const char *const SOCKET_NAMES[] = {"chain",
                                    "lane_length",
                                    "seed",
                                    "seed_per_frame",
                                    "passes",
                                    "spiral_frame",
                                    "spiral_rotation",
                                    "u2_mode",
                                    "k0_phase_lock_bits",
                                    "alpha",
                                    "max_depth",
                                    "diffuse_gain",
                                    "emission_gain",
                                    "continue_after_emitter",
                                    "ray_epsilon",
                                    "two_sided",
                                    "emission_scale",
                                    "ghost_lights",
                                    "output_mode",
                                    "exposure",
                                    "jitter"};
constexpr int NUM_SOCKETS = int(sizeof(SOCKET_NAMES) / sizeof(SOCKET_NAMES[0]));

/* SPEC §1: M_s->cam, the matrix with the columns (0,-1,0), (1,0,0), (0,0,1), row-major. */
const double M_S_TO_CAM[9] = {0.0, 1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0};
/* M_s->cam^T, which the smallpaint camera stores as camera_to_world with translation 0 (D19). */
const double M_S_TO_CAM_TRANSPOSE_3X4[12] = {
    0.0, -1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0};
/* An axis permutation (entries 0/±1): the rows (0,1,0), (1,0,0), (0,0,1) swap x and y. */
const double PERMUTATION_3X4[12] = {0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0};
const double PERMUTATION_3X3[9] = {0.0, 1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0};
/* P * M_s->cam, hand-computed row by row: row0 = m1 = (-1,0,0), row1 = m0 = (0,1,0),
 * row2 = m2 = (0,0,1). */
const double PERMUTATION_TIMES_M_S_TO_CAM[9] = {-1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0};

const double IDENTITY_3X3[9] = {1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0};
const double IDENTITY_3X4[12] = {1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0};
/* The same matrix in float: add_object takes the float row-major 3x4 Blender exports. */
const float IDENTITY_3X4_FLOAT[12] = {
    1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f};

/* Binary32 unit round-off: 2^-24. A binary32 significand has 24 bits, so a correctly rounded
 * binary32 result and a standard library cosf/sinf (within 1 ulp on this host) carry at most 2^-24
 * of relative error. */
constexpr double F32_UNIT_ROUNDOFF = 0x1p-24;
/* Absolute bound of one entry of R(e) against its binary64 evaluation. A product of three factors
 * carries at most 3 * F32_UNIT_ROUNDOFF of relative error (one per factor: cosf/sinf and each
 * float multiply), and the sum or difference of the two products adds one more rounding of
 * relative size F32_UNIT_ROUNDOFF on each term, so the entry's absolute error is at most 4 *
 * F32_UNIT_ROUNDOFF * (|a| + |b|), with a and b the two double-evaluated terms. This is the bound
 * the test applies; it is derived, not picked. Measured for e = (0.3f, 0.5f, 0.7f): the worst
 * entry uses 0.40 of its bound (a 9-entry probe of euler_to_transform against this reference,
 * built with g++ -std=c++20 -O2 -ffp-contract=off on this host). */
constexpr double F32_SPIRAL_ENTRY_FACTOR = 4.0 * F32_UNIT_ROUNDOFF;

/* R(e) for the XYZ Euler rotation e, evaluated in binary64, and its two product terms per entry.
 * euler_to_transform's assignment (util/transform.h:246-256) maps its row x to out[0..2], row y to
 * out[3..5] and row z to out[6..8]. */
void reference_euler_rotation(const float3 euler, double out[9], double terms[9][2])
{
  const double cx = std::cos(double(euler.x));
  const double cy = std::cos(double(euler.y));
  const double cz = std::cos(double(euler.z));
  const double sx = std::sin(double(euler.x));
  const double sy = std::sin(double(euler.y));
  const double sz = std::sin(double(euler.z));

  /* euler_to_transform's nine assignments (util/transform.h:246-256), in the order of its rows x,
   * y and z, which are the row-major rows of the matrix. Each entry is the sum of at most two
   * products. */
  const double rows[9][2] = {{cy * cz, 0.0},
                             {sy * sx * cz, -cx * sz},
                             {sy * cx * cz, sx * sz},
                             {cy * sz, 0.0},
                             {sy * sx * sz, cx * cz},
                             {sy * cx * sz, -sx * cz},
                             {-sy, 0.0},
                             {cy * sx, 0.0},
                             {cy * cx, 0.0}};
  for (int i = 0; i < 9; i++) {
    out[i] = rows[i][0] + rows[i][1];
    terms[i][0] = rows[i][0];
    terms[i][1] = rows[i][1];
  }
}

/* Exact equality of two row-major 3x3 matrices. Component ==, not memcmp: an e of 0 gives the
 * entry t.z.x = -sy = -0.0 (util/transform.h:248), which is exactly equal to +0.0 and multiplies
 * to the same result, so the two matrices are the same rotation. */
bool same_matrix_exact(const double a[9], const double b[9])
{
  for (int i = 0; i < 9; i++) {
    if (a[i] != b[i]) {
      return false;
    }
  }
  return true;
}

/* True when every entry of `actual` is within the derived binary32 bound of `expected`, whose two
 * terms are `terms`. */
bool spiral_entry_within_bound(const double actual[9],
                               const double expected[9],
                               const double terms[9][2])
{
  for (int i = 0; i < 9; i++) {
    const double bound = F32_SPIRAL_ENTRY_FACTOR *
                         (std::fabs(terms[i][0]) + std::fabs(terms[i][1]));
    if (!(std::fabs(actual[i] - expected[i]) <= bound)) {
      return false;
    }
  }
  return true;
}

/* A material with one diffuse lobe of weight 1. */
KernelPainterlyLobe diffuse_lobe()
{
  KernelPainterlyLobe lobe{};
  lobe.kind = LOBE_DIFFUSE;
  lobe.weight = make_double3(1.0);
  return lobe;
}

/* One triangle (0,1,2) with an optional corner normal block. */
void add_triangle_mesh(PainterlyScene &scene,
                       const bool with_corner_normals,
                       const int material,
                       int &mesh_index)
{
  const std::vector<float> vertices = {0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f};
  const std::vector<uint32_t> triangles = {0, 1, 2};
  const std::vector<int> tri_material = {material};
  std::vector<float> normals;
  if (with_corner_normals) {
    normals = {0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 1.0f};
  }
  mesh_index = scene.add_mesh(vertices, triangles, tri_material, normals);
}

}  // namespace

TEST_CASE("painterly integrator: the SPEC §8 socket defaults")
{
  PainterlyIntegrator integrator;

  CHECK(integrator.get_chain() == CHAIN_ROW);
  CHECK(integrator.get_lane_length() == 16);
  CHECK(integrator.get_seed() == 0u);
  CHECK_FALSE(integrator.get_seed_per_frame());
  CHECK(integrator.get_passes() == 1024);
  CHECK(integrator.get_spiral_frame() == SPIRAL_FRAME_CAMERA);
  CHECK(integrator.get_spiral_rotation() == make_float3(0.0f, 0.0f, 0.0f));
  CHECK(integrator.get_u2_mode() == U2_SAME);
  CHECK(integrator.get_k0_phase_lock_bits() == 0);
  CHECK(integrator.get_alpha() == 0.0f);
  CHECK(integrator.get_max_depth() == 20);
  CHECK(integrator.get_diffuse_gain() == 1.0f);
  CHECK(integrator.get_emission_gain() == 2.0f);
  CHECK(integrator.get_continue_after_emitter());
  CHECK(integrator.get_ray_epsilon() == 1e-4f);
  CHECK(integrator.get_two_sided());
  CHECK(integrator.get_emission_scale() == 1.0f);
  CHECK(integrator.get_ghost_lights());
  CHECK(integrator.get_output_mode() == OUTPUT_DISPLAY_REFERRED);
  CHECK(integrator.get_exposure() == 1.0f);
  CHECK(integrator.get_jitter() == 1.0f / 1400.0f);
}

TEST_CASE("painterly integrator: set and get round trip every socket")
{
  PainterlyIntegrator integrator;

  integrator.set_chain(CHAIN_LANE);
  CHECK(integrator.get_chain() == CHAIN_LANE);
  integrator.set_lane_length(5);
  CHECK(integrator.get_lane_length() == 5);
  integrator.set_seed(7u);
  CHECK(integrator.get_seed() == 7u);
  integrator.set_seed_per_frame(true);
  CHECK(integrator.get_seed_per_frame());
  integrator.set_passes(32);
  CHECK(integrator.get_passes() == 32);
  integrator.set_spiral_frame(SPIRAL_FRAME_SMALLPAINT);
  CHECK(integrator.get_spiral_frame() == SPIRAL_FRAME_SMALLPAINT);
  integrator.set_spiral_rotation(make_float3(0.5f, -0.25f, 2.0f));
  CHECK(integrator.get_spiral_rotation() == make_float3(0.5f, -0.25f, 2.0f));
  integrator.set_u2_mode(U2_INDEPENDENT);
  CHECK(integrator.get_u2_mode() == U2_INDEPENDENT);
  integrator.set_k0_phase_lock_bits(22);
  CHECK(integrator.get_k0_phase_lock_bits() == 22);
  integrator.set_alpha(0.5f);
  CHECK(integrator.get_alpha() == 0.5f);
  integrator.set_max_depth(3);
  CHECK(integrator.get_max_depth() == 3);
  integrator.set_diffuse_gain(0.1f);
  CHECK(integrator.get_diffuse_gain() == 0.1f);
  integrator.set_emission_gain(1.0f);
  CHECK(integrator.get_emission_gain() == 1.0f);
  integrator.set_continue_after_emitter(false);
  CHECK_FALSE(integrator.get_continue_after_emitter());
  integrator.set_ray_epsilon(0.25f);
  CHECK(integrator.get_ray_epsilon() == 0.25f);
  integrator.set_two_sided(false);
  CHECK_FALSE(integrator.get_two_sided());
  integrator.set_emission_scale(2.0f);
  CHECK(integrator.get_emission_scale() == 2.0f);
  integrator.set_ghost_lights(false);
  CHECK_FALSE(integrator.get_ghost_lights());
  integrator.set_output_mode(OUTPUT_SCENE_LINEAR);
  CHECK(integrator.get_output_mode() == OUTPUT_SCENE_LINEAR);
  integrator.set_exposure(0.5f);
  CHECK(integrator.get_exposure() == 0.5f);
  integrator.set_jitter(0.0f);
  CHECK(integrator.get_jitter() == 0.0f);
}

TEST_CASE("painterly integrator: the UI info names the sockets in order")
{
  const NodeType *type = PainterlyIntegrator::get_node_type();
  REQUIRE(type != nullptr);
  CHECK(type->name == ustring("painterly_integrator"));
  /* D15: never "integrator", which Cycles registers in the same registry (M6). */
  CHECK(type->inputs.size() == size_t(NUM_SOCKETS));

  const std::vector<PainterlySocketUIInfo> &info = painterly_integrator_ui_info();
  REQUIRE(info.size() == size_t(NUM_SOCKETS));

  for (int i = 0; i < NUM_SOCKETS; i++) {
    CHECK(type->inputs[size_t(i)].name == ustring(SOCKET_NAMES[i]));
    CHECK(std::string(info[size_t(i)].name) == SOCKET_NAMES[i]);
  }
  /* One entry per socket: the two name sets are equal. */
  std::vector<std::string> socket_names;
  for (const SocketType &socket : type->inputs) {
    socket_names.push_back(socket.name.string());
  }
  std::vector<std::string> info_names;
  for (const PainterlySocketUIInfo &entry : info) {
    info_names.push_back(std::string(entry.name));
  }
  CHECK(socket_names == info_names);
}

TEST_CASE("painterly integrator: device_update fills every kernel-consumed field")
{
  PainterlyIntegrator integrator;
  integrator.set_chain(CHAIN_LANE);
  integrator.set_lane_length(5);
  integrator.set_seed(9u);
  integrator.set_u2_mode(U2_INDEPENDENT);
  integrator.set_k0_phase_lock_bits(3);
  integrator.set_alpha(0.5f);
  integrator.set_max_depth(4);
  integrator.set_diffuse_gain(0.25f);
  integrator.set_emission_gain(8.0f);
  integrator.set_continue_after_emitter(false);
  integrator.set_ray_epsilon(0.125f);
  integrator.set_two_sided(false);

  KernelPainterlyIntegrator kernel{};
  integrator.device_update(kernel);

  CHECK(kernel.chain == CHAIN_LANE);
  CHECK(kernel.lane_length == 5);
  CHECK(kernel.seed == 9u);
  CHECK(kernel.u2_mode == U2_INDEPENDENT);
  CHECK(kernel.k0_phase_lock_bits == 3);
  /* Floats become doubles with double(float): exact for every float value. */
  CHECK(kernel.alpha == double(0.5f));
  CHECK(kernel.max_depth == 4);
  CHECK(kernel.diffuse_gain == double(0.25f));
  CHECK(kernel.emission_gain == double(8.0f));
  CHECK(kernel.continue_after_emitter == 0);
  CHECK(kernel.ray_epsilon == double(0.125f));
  CHECK(kernel.two_sided == 0);
  /* device_update does not touch the spiral frame: PainterlyScene::device_update computes F. */
}

TEST_CASE("painterly scene: object ids are auto-assigned from the call count")
{
  PainterlyScene scene;
  const int material = scene.add_material({diffuse_lobe()}, make_double3(0.0));

  const int sphere = scene.add_sphere(make_double3(0.0), 1.0, material, SPHERE_GHOST, -1, nullptr);
  const int plane = scene.add_plane(make_double3(0.0, 0.0, 1.0), 1.0, material, -1);
  CHECK(sphere == 0);
  CHECK(plane == 1);
  CHECK(scene.analytic[0].object_id == 0);
  CHECK(scene.analytic[1].object_id == 1);

  /* The running count of add_sphere/add_plane/add_object calls: the third call gets 2. */
  const std::vector<float> vertices = {0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f};
  const std::vector<uint32_t> triangles = {0, 1, 2};
  const std::vector<int> tri_material = {material};
  const int mesh = scene.add_mesh(vertices, triangles, tri_material, {});
  const int object = scene.add_object(mesh, IDENTITY_3X4_FLOAT, -1);
  CHECK(object == 0);
  CHECK(scene.objects[0].object_id == 2);

  /* An explicit id is stored as given, and the count keeps running. */
  scene.add_sphere(make_double3(1.0), 1.0, material, SPHERE_GHOST, 9, nullptr);
  CHECK(scene.analytic[2].object_id == 9);
  scene.add_plane(make_double3(0.0, 1.0, 0.0), 1.0, material, -1);
  CHECK(scene.analytic[3].object_id == 4);

  scene.clear();
  CHECK(scene.materials.empty());
  CHECK(scene.analytic.empty());
  CHECK(scene.meshes.empty());
  CHECK(scene.objects.empty());
  CHECK(scene.add_plane(make_double3(0.0, 0.0, 1.0), 1.0, 0, -1) == 0);
  CHECK(scene.analytic[0].object_id == 0);
}

TEST_CASE("painterly scene: device_update flattens the materials and the meshes")
{
  PainterlyScene scene;
  const int material_a = scene.add_material({diffuse_lobe()}, make_double3(1.0, 2.0, 3.0));
  KernelPainterlyLobe mirror{};
  mirror.kind = LOBE_MIRROR;
  mirror.weight = make_double3(1.0);
  const int material_b = scene.add_material({diffuse_lobe(), mirror}, make_double3(0.0));
  scene.add_sphere(make_double3(0.0), 1.0, material_a, SPHERE_GHOST, -1, nullptr);
  scene.add_plane(make_double3(0.0, 0.0, 1.0), 1.0, material_b, -1);

  int flat_mesh = -1;
  int normal_mesh = -1;
  add_triangle_mesh(scene, false, material_a, flat_mesh);
  add_triangle_mesh(scene, true, material_b, normal_mesh);
  scene.add_object(flat_mesh, IDENTITY_3X4_FLOAT, -1);
  scene.add_object(normal_mesh, IDENTITY_3X4_FLOAT, -1);

  PainterlyDeviceScene ds;
  scene.device_update(ds);

  /* Lobes are flattened in material order, indexed by lobe_offset / num_lobes. */
  CHECK(ds.materials.size() == 2u);
  CHECK(ds.materials[0].lobe_offset == 0);
  CHECK(ds.materials[0].num_lobes == 1);
  CHECK(ds.materials[1].lobe_offset == 1);
  CHECK(ds.materials[1].num_lobes == 2);
  CHECK(ds.lobes.size() == 3u);
  CHECK(ds.lobes[2].kind == LOBE_MIRROR);
  CHECK(same_vec(ds.materials[0].emission, make_double3(1.0, 2.0, 3.0)));
  /* Constant lobes: svm_offset == -1 for every material (painterly/kernel/types.h). */
  for (const KernelPainterlyMaterial &material : ds.materials) {
    CHECK(material.svm_offset == -1);
  }

  CHECK(ds.analytic.size() == 2u);
  CHECK(ds.analytic[0].type == ANALYTIC_SPHERE);
  CHECK(ds.analytic[1].type == ANALYTIC_PLANE);

  /* tri_material: one int per triangle of every mesh, indexed by mesh.tri_offset + prim. */
  CHECK(ds.meshes.size() == 2u);
  CHECK(ds.meshes[0].tri_offset == 0);
  CHECK(ds.meshes[0].num_tris == 1);
  CHECK(ds.meshes[0].has_corner_normals == 0);
  CHECK(ds.meshes[1].tri_offset == 1);
  CHECK(ds.meshes[1].num_tris == 1);
  CHECK(ds.meshes[1].has_corner_normals == 1);
  REQUIRE(ds.tri_material.size() == 2u);
  CHECK(ds.tri_material[0] == material_a);
  CHECK(ds.tri_material[1] == material_b);

  /* tri_corner_normals: PAINTERLY_TRIANGLE_CORNERS * PAINTERLY_POINT_FLOATS floats per triangle of
   * every mesh, zeros for a mesh without corner normals. */
  const size_t per_triangle = size_t(PAINTERLY_TRIANGLE_CORNERS) * size_t(PAINTERLY_POINT_FLOATS);
  REQUIRE(ds.tri_corner_normals.size() == 2u * per_triangle);
  for (size_t i = 0; i < per_triangle; i++) {
    CHECK(ds.tri_corner_normals[i] == 0.0f);
  }
  /* The second mesh's normals are (0, 0, 1) at each of its three corners. */
  for (size_t i = 0; i < per_triangle; i++) {
    const float expected = (i % size_t(PAINTERLY_POINT_FLOATS) == 2u) ? 1.0f : 0.0f;
    CHECK(ds.tri_corner_normals[per_triangle + i] == expected);
  }

  /* The globals view points at the arrays, with their sizes, and at the BVH. */
  const PainterlyGlobalsCPU globals = ds.globals();
  CHECK(globals.data == &ds.data);
  CHECK(globals.num_materials == 2);
  CHECK(globals.num_lobes == 3);
  CHECK(globals.num_analytic == 2);
  CHECK(globals.num_meshes == 2);
  CHECK(globals.num_objects == 2);
  CHECK(globals.materials == ds.materials.data());
  CHECK(globals.tri_material == ds.tri_material.data());
  CHECK(globals.tri_corner_normals == ds.tri_corner_normals.data());
  /* The scene has triangles, so Embree was built. */
  CHECK(globals.bvh != nullptr);
}

TEST_CASE("painterly scene: tri_corner_normals stays null without corner normals")
{
  PainterlyScene scene;
  const int material = scene.add_material({diffuse_lobe()}, make_double3(0.0));
  int mesh = -1;
  add_triangle_mesh(scene, false, material, mesh);
  scene.add_object(mesh, IDENTITY_3X4_FLOAT, -1);

  PainterlyDeviceScene ds;
  scene.device_update(ds);
  CHECK(ds.tri_corner_normals.empty());
  CHECK(ds.globals().tri_corner_normals == nullptr);
  /* An analytic-only scene builds no BVH. */
  scene.clear();
  scene.add_material({diffuse_lobe()}, make_double3(0.0));
  scene.add_plane(make_double3(0.0, 0.0, 1.0), 1.0, 0, -1);
  scene.device_update(ds);
  CHECK(ds.globals().bvh == nullptr);
}

TEST_CASE("painterly scene: normal_to_world is painterly_normal_matrix of object_to_world")
{
  PainterlyScene scene;
  const int material = scene.add_material({diffuse_lobe()}, make_double3(0.0));
  int mesh = -1;
  add_triangle_mesh(scene, false, material, mesh);
  /* A rotation, a translation, a scale and a mirroring (negative determinant) transform. */
  const float transforms[4][12] = {
      {1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f},
      {0.0f, -1.0f, 0.0f, 2.0f, 1.0f, 0.0f, 0.0f, -3.0f, 0.0f, 0.0f, 1.0f, 0.5f},
      {2.0f, 0.0f, 0.0f, 0.0f, 0.0f, 3.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.5f, 0.0f},
      {1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, -1.0f, 0.0f}};
  for (const float *tfm : transforms) {
    scene.add_object(mesh, tfm, -1);
  }

  PainterlyDeviceScene ds;
  scene.device_update(ds);
  REQUIRE(ds.objects.size() == 4u);
  for (size_t i = 0; i < ds.objects.size(); i++) {
    double expected[9];
    painterly_normal_matrix(transforms[i], expected);
    /* Bitwise: the two routes are the same function on the same float transform. */
    CHECK(std::memcmp(ds.objects[i].normal_to_world, expected, sizeof(expected)) == 0);
  }
}

TEST_CASE("painterly scene: an invalid mesh or material index is rejected")
{
  PainterlyScene scene;
  const int material = scene.add_material({diffuse_lobe()}, make_double3(0.0));

  /* vertices must be 3 floats per vertex. */
  CHECK_THROWS_AS(scene.add_mesh({0.0f, 0.0f}, {0, 1, 2}, {material}, {}), std::invalid_argument);
  /* triangles must be 3 indices per triangle. */
  CHECK_THROWS_AS(scene.add_mesh({0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f}, {0, 1}, {material}, {}),
                  std::invalid_argument);
  /* tri_material must have one entry per triangle. */
  CHECK_THROWS_AS(
      scene.add_mesh({0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f}, {0, 1, 2}, {}, {}),
      std::invalid_argument);
  /* corner_normals must have 9 floats per triangle. */
  CHECK_THROWS_AS(scene.add_mesh({0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f},
                                 {0, 1, 2},
                                 {material},
                                 {0.0f, 0.0f, 1.0f}),
                  std::invalid_argument);
  /* A triangle index outside the vertex array. */
  CHECK_THROWS_AS(
      scene.add_mesh(
          {0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f}, {0, 1, 3}, {material}, {}),
      std::invalid_argument);

  /* A material needs at least one lobe, and a glass lobe needs ior > 0. */
  CHECK_THROWS_AS(scene.add_material({}, make_double3(0.0)), std::invalid_argument);
  KernelPainterlyLobe glass{};
  glass.kind = LOBE_GLASS;
  glass.weight = make_double3(1.0);
  glass.ior = 0.0;
  CHECK_THROWS_AS(scene.add_material({glass}, make_double3(0.0)), std::invalid_argument);
  KernelPainterlyLobe unknown{};
  unknown.kind = 99;
  unknown.weight = make_double3(1.0);
  CHECK_THROWS_AS(scene.add_material({unknown}, make_double3(0.0)), std::invalid_argument);

  /* A material index outside the material list, at device_update time. */
  scene.add_plane(make_double3(0.0, 0.0, 1.0), 1.0, 7, -1);
  PainterlyDeviceScene ds;
  CHECK_THROWS_AS(scene.device_update(ds), std::invalid_argument);
}

TEST_CASE("painterly scene: a singular object transform is rejected only with triangles")
{
  PainterlyScene scene;
  const int material = scene.add_material({diffuse_lobe()}, make_double3(0.0));
  int mesh = -1;
  add_triangle_mesh(scene, false, material, mesh);
  int empty_mesh = scene.add_mesh({}, {}, {}, {});
  /* A zero-scaled object_to_world: the 3x3 part is singular. */
  const float singular[12] = {
      0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f};

  /* An object whose mesh has triangles: rejected, as painterly_embree_scene_create rejects it. */
  scene.add_object(mesh, singular, -1);
  PainterlyDeviceScene ds;
  CHECK_THROWS_AS(scene.device_update(ds), std::invalid_argument);

  /* A mesh without triangles cannot be hit, so its transform is never read: accepted, with a zero
   * normal_to_world. */
  scene.clear();
  const int only_material = scene.add_material({diffuse_lobe()}, make_double3(0.0));
  empty_mesh = scene.add_mesh({}, {}, {}, {});
  scene.add_object(empty_mesh, singular, -1);
  scene.add_plane(make_double3(0.0, 0.0, 1.0), 1.0, only_material, -1);
  PainterlyDeviceScene ds2;
  scene.device_update(ds2);
  REQUIRE(ds2.objects.size() == 1u);
  for (const double entry : ds2.objects[0].normal_to_world) {
    CHECK(entry == 0.0);
  }
  CHECK(ds2.globals().bvh == nullptr);
}

TEST_CASE("painterly scene: the spiral frame F of the four spiral_frame cases")
{
  PainterlyScene scene;
  const int material = scene.add_material({diffuse_lobe()}, make_double3(0.0));
  scene.add_plane(make_double3(0.0, 0.0, 1.0), 1.0, material, -1);
  scene.set_camera_smallpaint(8, 8);
  PainterlyDeviceScene ds;

  /* smallpaint: F = I (SPEC §1). */
  scene.integrator.set_spiral_frame(SPIRAL_FRAME_SMALLPAINT);
  scene.device_update(ds);
  CHECK(same_matrix_exact(ds.data.integrator.spiral_frame, IDENTITY_3X3));

  /* world with e = 0: F = R(0) = I exactly. */
  scene.integrator.set_spiral_frame(SPIRAL_FRAME_WORLD);
  scene.device_update(ds);
  CHECK(same_matrix_exact(ds.data.integrator.spiral_frame, IDENTITY_3X3));

  /* camera with the smallpaint camera and e = 0: R_cam->world = M_s->cam^T, so
   * F = M_s->cam^T * M_s->cam = I exactly (D19). */
  scene.integrator.set_spiral_frame(SPIRAL_FRAME_CAMERA);
  scene.device_update(ds);
  CHECK(same_matrix_exact(ds.data.integrator.spiral_frame, IDENTITY_3X3));

  /* camera with an identity camera and e = 0: F = M_s->cam exactly. */
  double identity_4x4[16] = {0.0};
  for (int i = 0; i < 4; i++) {
    identity_4x4[4 * i + i] = 1.0;
  }
  scene.set_camera_perspective(
      8, 8, identity_4x4, IDENTITY_3X4, PainterlyCameraFit::FIT_HORIZONTAL);
  scene.device_update(ds);
  CHECK(same_matrix_exact(ds.data.integrator.spiral_frame, M_S_TO_CAM));

  /* camera with an axis-permutation camera_to_world and e = 0: F = P * M_s->cam exactly. */
  scene.set_camera_orthographic(
      8, 8, identity_4x4, PERMUTATION_3X4, PainterlyCameraFit::FIT_VERTICAL);
  scene.device_update(ds);
  CHECK(same_matrix_exact(ds.data.integrator.spiral_frame, PERMUTATION_TIMES_M_S_TO_CAM));

  /* object with an axis-permutation rotation and e = 0: F = R_obj exactly. */
  scene.set_spiral_object(PERMUTATION_3X3);
  scene.integrator.set_spiral_frame(SPIRAL_FRAME_OBJECT);
  scene.device_update(ds);
  CHECK(same_matrix_exact(ds.data.integrator.spiral_frame, PERMUTATION_3X3));

  /* object with no spiral object set: rejected (SPEC §1). */
  scene.clear();
  scene.add_material({diffuse_lobe()}, make_double3(0.0));
  scene.add_plane(make_double3(0.0, 0.0, 1.0), 1.0, 0, -1);
  scene.integrator.set_spiral_frame(SPIRAL_FRAME_OBJECT);
  PainterlyDeviceScene ds3;
  CHECK_THROWS_AS(scene.device_update(ds3), std::invalid_argument);
}

TEST_CASE("painterly scene: the spiral frame of a general nonzero rotation")
{
  /* One general nonzero e. Axis permutations are tested through the matrices above, never through
   * e: euler_to_transform evaluates cosf/sinf in float, so even an e of multiples of pi/2 is not
   * exact (cosf(float(pi/2)) = -4.37e-8). */
  const float3 euler = make_float3(0.3f, 0.5f, 0.7f);
  PainterlyScene scene;
  scene.add_material({diffuse_lobe()}, make_double3(0.0));
  scene.add_plane(make_double3(0.0, 0.0, 1.0), 1.0, 0, -1);
  scene.integrator.set_spiral_frame(SPIRAL_FRAME_WORLD);
  scene.integrator.set_spiral_rotation(euler);
  PainterlyDeviceScene ds;
  scene.device_update(ds);

  double expected[9];
  double terms[9][2];
  reference_euler_rotation(euler, expected, terms);
  CHECK(spiral_entry_within_bound(ds.data.integrator.spiral_frame, expected, terms));

  /* object with the same e and R_obj = I: F = R(e) as well. */
  scene.set_spiral_object(IDENTITY_3X3);
  scene.integrator.set_spiral_frame(SPIRAL_FRAME_OBJECT);
  scene.device_update(ds);
  CHECK(spiral_entry_within_bound(ds.data.integrator.spiral_frame, expected, terms));
}

TEST_CASE("painterly camera: device_update stores the jitter in the units of SPEC §7")
{
  /* The socket's default fraction: 1/1400 of the fitted image side. */
  const double jitter = double(1.0f / 1400.0f);
  double identity_4x4[16] = {0.0};
  for (int i = 0; i < 4; i++) {
    identity_4x4[4 * i + i] = 1.0;
  }

  /* smallpaint camera: image-plane units, 2 * jitter, exact. */
  {
    PainterlyCamera camera;
    camera.set_smallpaint(400, 400);
    KernelPainterlyCamera kernel{};
    camera.device_update(kernel, jitter);
    CHECK(kernel.type == PAINTERLY_CAMERA_SMALLPAINT);
    CHECK(kernel.width == 400);
    CHECK(kernel.height == 400);
    const double expected = 2.0 * jitter;
    CHECK(same_bits(kernel.jitter, expected));
    /* The reference 1/700 image-plane units: 2 * float32(1/1400). */
    CHECK(same_bits(kernel.jitter, 2.0 * double(1.0f / 1400.0f)));
    /* The smallpaint camera stores M_s->cam^T with translation 0 (D19). */
    CHECK(std::memcmp(kernel.camera_to_world,
                      M_S_TO_CAM_TRANSPOSE_3X4,
                      sizeof(M_S_TO_CAM_TRANSPOSE_3X4)) == 0);
    for (const double entry : kernel.raster_to_camera) {
      CHECK(entry == 0.0);
    }
  }

  /* Perspective and orthographic: raster pixels, jitter * F, with F the fitted image side. */
  {
    PainterlyCamera camera;
    camera.set_projective(PAINTERLY_CAMERA_PERSPECTIVE,
                          320,
                          200,
                          identity_4x4,
                          IDENTITY_3X4,
                          PainterlyCameraFit::FIT_HORIZONTAL);
    KernelPainterlyCamera kernel{};
    camera.device_update(kernel, jitter);
    CHECK(kernel.type == PAINTERLY_CAMERA_PERSPECTIVE);
    CHECK(same_bits(kernel.jitter, jitter * 320.0));

    camera.set_projective(PAINTERLY_CAMERA_PERSPECTIVE,
                          320,
                          200,
                          identity_4x4,
                          IDENTITY_3X4,
                          PainterlyCameraFit::FIT_VERTICAL);
    camera.device_update(kernel, jitter);
    CHECK(same_bits(kernel.jitter, jitter * 200.0));

    camera.set_projective(PAINTERLY_CAMERA_ORTHOGRAPHIC,
                          320,
                          200,
                          identity_4x4,
                          IDENTITY_3X4,
                          PainterlyCameraFit::FIT_VERTICAL);
    camera.device_update(kernel, jitter);
    CHECK(kernel.type == PAINTERLY_CAMERA_ORTHOGRAPHIC);
    CHECK(same_bits(kernel.jitter, jitter * 200.0));
  }
}

TEST_CASE("painterly background: add_sun normalizes the direction and stores cos(angle/2)")
{
  PainterlyBackground background;
  background.radiance = make_double3(0.5);
  const int index = background.add_sun(
      make_double3(0.0, 0.0, 4.0), 0.5, make_double3(1.0, 2.0, 3.0));
  CHECK(index == 0);

  KernelPainterlyBackground kernel{};
  std::vector<KernelPainterlySun> suns;
  background.device_update(kernel, suns);
  CHECK(same_vec(kernel.radiance, make_double3(0.5)));
  CHECK(kernel.num_suns == 1);
  REQUIRE(suns.size() == 1u);
  CHECK(same_vec(suns[0].direction, make_double3(0.0, 0.0, 1.0)));
  CHECK(suns[0].cos_half_angle == std::cos(0.25));
  CHECK(same_vec(suns[0].radiance, make_double3(1.0, 2.0, 3.0)));
}

CCL_NAMESPACE_END
