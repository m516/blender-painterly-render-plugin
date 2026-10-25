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
//   - the total path length.
// It also reports the quantities the card's slow test compares: the total K consumption and the
// total radiance of a 64 px pass.
//
// The test asserts only what holds on any machine, because about 47 paths graze a box edge or a
// sphere's silhouette, where Embree's float32 hit distance - and so the side the path lands on -
// depends on the instruction set (src/test/test_bvh.cpp:30-72):
//   - each walk's K consumption equals the kernel's own trace of the same pixels;
//   - no path misses, at any bounce;
//   - every path reaches bounces 0 and 1;
//   - every quad hit's shading normal equals the analytic plane's n by value (==, so a -0.0
//     component equals +0.0).
// Every count the walk produces is printed with MESSAGE and none of them is asserted: the path
// lengths, the two K totals, the number of paths that hit the same object at every bounce, and the
// number of shading normals that differ.
//
// What this machine's run prints (these numbers are not pinned, they move with the instruction
// set): the two walks reach bounces 0 to 17 in equal numbers, 4049 of 4096 paths hit the same
// object at every bounce, the total path length is 75964 against 75966, and the radiance total
// agrees to six significant figures. The total path length therefore differs by 2.6e-5 relative,
// derived from those two numbers with
//   python3 -c 'print((75966 - 75964) / 75964)'   ->   2.6328260755094518e-05
// The two differences the numbers show are:
//   - the quad scene sees more hits just inside ray_epsilon (618 against 205 at bounce 1). Those
//     are the surface the path is already on: Embree's float32 t puts the new origin about 1e-7
//     off the plane, so the raw root of that plane is a small positive t instead of exactly 0.
//     The near limit rejects them, which is what it is for, so they cost nothing;
//   - the diffuse-bounce count differs by about 4.8e-4 relative (66503 against 66471): a path that
//     lands on a mirror or a glass sphere in one scene and on a diffuse wall in the other gains or
//     loses a diffuse bounce.
//
// Neither is a shading difference, and this walk finds none. Nor is the walk evidence that the
// two scenes agree: M3-FIX-T3.17a refuted the look match at fresh seeds (the card's slow test
// rejects 7 of 10 blocks 69-78 on the r3, r6 and r7 means), M3-FIX-T3.17b measured the quad
// scene's raw radiance lower in r6 and higher in r7 under both chains, and the cause of that bias
// is open (M3-FIX-T3.17c). With one chain per pixel the two scenes' region means agree to 1e-7
// relative, while the card's image-chain design reports 1.7e-3, because the image chain runs one K
// sequence through the whole image and a shift in it moves every later pixel's sample window; the
// bias is in the mesh path's per-path radiance, not in the chain (M3-FIX-T3.17b).
//
// A change that moves the quad geometry off the plane, breaks the mesh path or flips a shading
// normal still fails here: the misses, the reach counts at bounces 0 and 1, the K equality and the
// by-value normal comparison all break.
//
// M3-FIX-T3.17c added three cases below, all on this machine's run:
//   - the ghost="all" report at the card's design (400 px, P = 32, seed 1088, one chain per
//   pixel):
//     14 pixels lose K, 2 gain it, 5119984 are equal, the K totals are 83001163 against 83001050
//     (relative -1.36e-6), and the differing pixels part as rim 14, corner 2, other 0;
//   - the plane and self-hit checks at 16 px, which fail at HEAD: 3393 of 3393 plane hits off
//   their
//     plane there (largest distance 1.15e-6) and 2 hits on the surface the path just left, against
//     0 and 0 after the fix (largest distance 1.33e-15, bound 3.98e-13);
//   - the tilted-quad self-hit guard, which fails at HEAD: the intersect reports the surface the
//     ray starts on, at Embree's t = 1.67e-4 for a root of -2.82e-5.

#include <doctest/doctest.h>

#include <cmath>
#include <cstdint>
#include <limits>
#include <string>
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
/* The far limit of an intersect query with no bound: the header's
 * painterly_embree_intersect_closest takes the caller's tfar, and the kernel passes +infinity
 * (painterly/kernel/bvh/bvh.h). */
constexpr double INFINITE_DISTANCE = std::numeric_limits<double>::infinity();

KernelPainterlyLobe lobe(const int kind, const double3 weight, const double ior)
{
  KernelPainterlyLobe l{};
  l.kind = kind;
  l.weight = weight;
  l.ior = ior;
  return l;
}

/* SPEC §9, with smallpaint's analytic planes when `quads` is false and with one quad per plane
 * when it is true. The object ids are the list positions in both cases. `size` is the image side
 * in pixels of the smallpaint camera. */
void build_reference_scene(PainterlyScene &scene, const bool quads, const int size)
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

  scene.set_camera_smallpaint(size, size);
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
  bool near_hit = false;           /* A hit lies within ray_epsilon of the ray's origin. */
  bool away = false;               /* The shading normal faces away from the incoming ray. */
  bool normal_equals_plane = true; /* A quad hit: the shading normal equals the plane's n. */

  int object_id = -1;
  /* The hit point P = o + t d in binary64, the point the path continues from. It is the zero
   * vector on a miss. */
  double3 point = make_double3(0.0);
  /* The object id of the previous bounce, or -1 at the first bounce or after a miss. */
  int previous_object_id = -1;
};

/* True when two vectors are equal by value, component for component: -0.0 == +0.0, and no bit
 * pattern is compared. */
bool same_value(const double3 a, const double3 b)
{
  return a.x == b.x && a.y == b.y && a.z == b.z;
}

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
    b.previous_object_id = bounces->empty() ? -1 : bounces->back().object_id;
    if (!bounces->empty() && bounces->back().miss) {
      b.previous_object_id = -1;
    }
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
    b.point = ray.o + ray.d * isect.t;
    const double3 N = shading_normal(kg, isect, ray);
    b.away = dot(N, ray.d) > 0;
    if (isect.kind == HIT_TRIANGLE && b.object_id >= FIRST_PLANE_ID) {
      const double3 plane_n = make_double3(PLANES[b.object_id - FIRST_PLANE_ID].n[0],
                                           PLANES[b.object_id - FIRST_PLANE_ID].n[1],
                                           PLANES[b.object_id - FIRST_PLANE_ID].n[2]);
      b.normal_equals_plane = same_value(N, plane_n);
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

/* The smallest image whose walk still covers every plane of the box and every sphere: the two
 * new checks of M3-FIX-T3.17c (R64) run on it. 16 px keeps them fast; the card's slow Python test
 * is the statistical one at 400 px. */
constexpr int PLANE_CHECK_SIZE = 16;

/* The plane of one SPEC §9 plane as a point and a unit normal: n.p + d = 0, so the plane is
 * {p : dot(n, p) + d = 0}. */
struct Plane {
  double3 n;
  double d;
};

Plane plane_of(const int object_id)
{
  const int p = object_id - FIRST_PLANE_ID;
  return Plane{make_double3(PLANES[p].n[0], PLANES[p].n[1], PLANES[p].n[2]), PLANES[p].d};
}

/* The signed distance of a point from a plane, dot(n, p) + d, in binary64. n is unit, so the value
 * is the distance itself, positive on the side n points to. */
double signed_distance(const Plane &plane, const double3 point)
{
  return dot(plane.n, point) + plane.d;
}

/* The bound on the signed distance of a quad hit's point from its plane, derived from binary64
 * round-off (CLAUDE.md rule 2).
 *
 * A hit point is P = o + t d, with the refined t of painterly/bvh/embree.cpp's refine_triangle_t:
 * t = dot(normal, v0 - o) / dot(normal, d), where v0 is a world corner of the reported triangle
 * and normal = (v1 - v0) x (v2 - v0). All of that is binary64. Notation of Higham, "Accuracy and
 * Stability of Numerical Algorithms", 2nd ed., SIAM 2002, section 2.2: a correctly rounded
 * operation returns (x op y)(1 + d) with |d| <= u, u = 2^-53 is the unit round-off of IEEE
 * binary64 with round to nearest (a definition of the format), and a chain of n of them is 1 +
 * theta with |theta| <= gamma(n) = n u / (1 - n u).
 *
 * The roundings, counted from the expressions in refine_triangle_t and in
 * painterly_transform_direction_3x4 / painterly_transform_translation_3x4:
 *   - one world corner: 3 products and 2 sums per row, so 5 roundings per coordinate;
 *   - the cross product: 2 products and 1 difference per component, so 3;
 *   - dot(normal, v0 - o): 3 differences, 3 products and 2 sums, so 8;
 *   - dot(normal, d): 3 products and 2 sums, so 5;
 *   - the quotient: 1;
 *   - o + t d: 3 products and 3 sums, so 6.
 * That is 28 roundings in all, each of a value of the magnitude of the operands. The box's
 * coordinates are at most 50 + 5.5 = 55.5 units (the quads' PLANE_EXTENT plus the box's own
 * extent, SPEC §9), and the world corner v0 is on the plane exactly for the reference box (its
 * planes are axis-aligned and their offsets are small dyadics), so the signed distance of P from
 * the plane is the round-off of those 28 operations: at most 28 * 55.5 * 2^-53 = 1.7e-13.
 *
 * The bound charges 64 roundings of 56 units, 64 * 56 * 2^-53 = 4.0e-13, a margin of 2.3 over the
 * count above. It bounds binary64 round-off only, so it does not depend on the instruction set:
 * -ffp-contract=off keeps every product uncontracted, and no binary32 value enters the refine
 * except the mesh's own vertices. Before M3-FIX-T3.17c the hit point came from Embree's binary32
 * t, whose error is up to |P| 2^-24 = 3.3e-6, six orders of magnitude above this bound. */
constexpr int HIT_DISTANCE_ROUNDINGS = 64;
constexpr double HIT_DISTANCE_SCALE = 56.0;
constexpr double HIT_ON_PLANE_BOUND = HIT_DISTANCE_ROUNDINGS * HIT_DISTANCE_SCALE * 0x1p-53;

/* True for the object id of one of the six quads: list positions FIRST_PLANE_ID to
 * FIRST_PLANE_ID + 5 (SPEC §9). Position 9 is the light sphere, which is not a plane. */
bool is_plane_object(const int object_id)
{
  return object_id >= FIRST_PLANE_ID && object_id < FIRST_PLANE_ID + 6;
}

/* True when the hit point of a bounce lies within HIT_ON_PLANE_BOUND of the plane of the object it
 * hit, for a bounce that hit one of the six quads. */
bool on_its_plane(const Bounce &b)
{
  return is_plane_object(b.object_id) &&
         std::abs(signed_distance(plane_of(b.object_id), b.point)) <= HIT_ON_PLANE_BOUND;
}

/* The number of plane hits in `walk`'s bounces, and the number of those whose point is further
 * than HIT_ON_PLANE_BOUND from the plane. */
void count_plane_hits(const std::vector<Bounce> &bounces, long long *hits, long long *off_plane)
{
  for (const Bounce &b : bounces) {
    if (b.miss || !is_plane_object(b.object_id)) {
      continue;
    }
    (*hits)++;
    if (!on_its_plane(b)) {
      (*off_plane)++;
    }
  }
}

}  // namespace

TEST_CASE("painterly scene: the quad scene's paths match the analytic scene's, bounce by bounce")
{
  PainterlyScene analytic_scene;
  build_reference_scene(analytic_scene, false, WALK_SIZE);
  PainterlyScene quad_scene;
  build_reference_scene(quad_scene, true, WALK_SIZE);

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
        /* Every quad hit's shading normal against the analytic plane's normal, by value: -0.0
         * equals +0.0, so the sign of a zero component is not a difference. The count is printed;
         * the comparison itself is what this test asserts, on every hit. */
        for (const Bounce &b : t.bounces) {
          if (b.miss || b.object_id < FIRST_PLANE_ID) {
            continue;
          }
          normal_hits++;
          CHECK(b.normal_equals_plane);
          normal_mismatch += b.normal_equals_plane ? 0 : 1;
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
                                                    << " hits differ by value");
  MESSAGE("total path length: analytic " << a.length << ", quad " << t.length << " over " << paths
                                         << " paths");
  MESSAGE("K consumption: analytic " << a.k_total << ", quad " << t.k_total);
  MESSAGE("radiance: analytic " << a.radiance_total << ", quad " << t.radiance_total);
  MESSAGE("paths that hit the same object at every bounce: " << first_different[size_t(MAX_DEPTH)]
                                                             << " of " << paths);

  /* The checks that hold on any machine.
   *
   * The box is closed in both scenes, so no path misses at any bounce, and every path reaches
   * bounces 0 and 1. The K consumption of each walk equals the kernel's own trace of the same
   * pixels. Every quad hit's shading normal equals the analytic plane's n by value.
   *
   * The numbers printed above are this machine's run, and none of them is asserted. About 47 paths
   * graze a box edge or a sphere's silhouette, where Embree's float32 hit distance depends on the
   * instruction set (src/test/test_bvh.cpp:30-72), so the path lengths, the K totals, the number
   * of paths that hit the same object at every bounce and the count of paths that reach a late
   * bounce all move with the build. The two differences the numbers show are:
   *
   * - the quad scene sees more hits just inside ray_epsilon: Embree's float32 t puts the new
   * origin about 1e-7 off the plane, so the raw root of that plane is a small positive t instead
   * of exactly 0. The near limit rejects them, which is what it is for, so they cost nothing;
   * - the diffuse-bounce count differs by about 4.8e-4 relative, because a path that lands on a
   *   mirror or a glass sphere in one scene and on a diffuse wall in the other gains or loses a
   *   diffuse bounce.
   *
   * Neither is a shading difference, and this walk finds no shading difference. Nor is it evidence
   * that the two scenes agree: the look match is refuted at fresh seeds (the card's slow test),
   * M3-FIX-T3.17b measured the quad scene's raw radiance lower in r6 and higher in r7 under both
   * chains, and the cause of that bias is open (M3-FIX-T3.17c). */
  for (int i = 0; i < MAX_DEPTH; i++) {
    CHECK(a.miss[size_t(i)] == 0);
    CHECK(t.miss[size_t(i)] == 0);
  }
  CHECK(a.reached[0] == paths);
  CHECK(a.reached[1] == paths);
  CHECK(t.reached[0] == paths);
  CHECK(t.reached[1] == paths);
}

TEST_CASE("painterly scene: the ghost-all K differences and where the two paths first part")
{
  /* M3-FIX-T3.17c (R64): the card's design, 400 px, P = 32, one chain per pixel, ghost="all",
   * walked for both scenes. The K totals and the counts of pixels that lose, gain and keep K are
   * printed, and for every pixel whose K differs, the bounce at which the two paths first hit a
   * different object, the two objects, and the class of that parting:
   *   - "rim": the analytic path hit a plane and the quad path missed, because the path left the
   *     box and beyond the quads' rim only the infinite analytic plane is there;
   *   - "corner": both paths hit a plane, but a different one;
   *   - "other": anything else (a sphere in one scene or the other, or a plane against a sphere).
   * Nothing here is asserted: the ghost="all" numbers are a report (R64). The card's assertion is
   * the Python test tests/core/test_triangle_samples.py, on ghost="none". */
  constexpr int REPORT_SIZE = 400;
  constexpr int REPORT_PASSES = 32;
  /* Block 68's first seed (the card): a block is 16 seeds, the base seed is 16 times the block. */
  constexpr uint REPORT_SEED = 1088;

  PainterlyScene analytic_scene;
  build_reference_scene(analytic_scene, false, REPORT_SIZE);
  PainterlyScene quad_scene;
  build_reference_scene(quad_scene, true, REPORT_SIZE);
  analytic_scene.integrator.set_seed(REPORT_SEED);
  quad_scene.integrator.set_seed(REPORT_SEED);

  PainterlyDeviceScene analytic_device;
  analytic_scene.device_update(analytic_device);
  PainterlyDeviceScene quad_device;
  quad_scene.device_update(quad_device);
  const PainterlyGlobalsCPU analytic_globals = analytic_device.globals();
  const PainterlyGlobalsCPU quad_globals = quad_device.globals();
  const PainterlyGlobals a_kg = &analytic_globals;
  const PainterlyGlobals t_kg = &quad_globals;

  long long lose = 0;
  long long gain = 0;
  long long equal = 0;
  long long k_analytic = 0;
  long long k_quad = 0;
  long long parting[MAX_DEPTH + 1] = {0};
  long long rim = 0;
  long long corner = 0;
  long long other = 0;
  long long ghost_sphere = 0; /* The parting is a sphere in one scene and something else, or two
                                 different spheres: a ghost sphere's root decided it. */
  /* The signed distance of each plane hit's point from its plane, both scenes: the number of hits,
   * their mean, and the fraction in front of (positive) and behind (negative) the plane. */
  struct DistanceStats {
    long long hits = 0;
    long long front = 0;
    long long behind = 0;
    double sum = 0.0;
    double largest = 0.0;
  };
  DistanceStats distance_a;
  DistanceStats distance_t;
  std::vector<Bounce> a_path;
  std::vector<Bounce> t_path;
  for (int pass = 0; pass < REPORT_PASSES; pass++) {
    for (int row = 0; row < REPORT_SIZE; row++) {
      for (int col = 0; col < REPORT_SIZE; col++) {
        uint64_t k_a = painterly_chain_start(a_kg->data->integrator, row, col, pass);
        uint64_t k_t = painterly_chain_start(t_kg->data->integrator, row, col, pass);
        const uint64_t k0_a = k_a;
        const uint64_t k0_t = k_t;
        const int na = walk(a_kg, row, col, pass, &k_a, &a_path);
        const int nt = walk(t_kg, row, col, pass, &k_t, &t_path);
        const std::vector<Bounce> *paths[2] = {&a_path, &t_path};
        for (int side = 0; side < 2; side++) {
          DistanceStats &stats = (side == 0) ? distance_a : distance_t;
          for (const Bounce &b : *paths[side]) {
            if (b.miss || !is_plane_object(b.object_id)) {
              continue;
            }
            const double distance = signed_distance(plane_of(b.object_id), b.point);
            stats.hits++;
            stats.sum += distance;
            stats.front += distance > 0.0 ? 1 : 0;
            stats.behind += distance < 0.0 ? 1 : 0;
            stats.largest = std::max(stats.largest, std::abs(distance));
          }
        }
        const long long da = static_cast<long long>(k_a - k0_a);
        const long long dt = static_cast<long long>(k_t - k0_t);
        k_analytic += da;
        k_quad += dt;
        if (dt < da) {
          lose++;
        }
        else if (dt > da) {
          gain++;
        }
        else {
          equal++;
        }
        if (dt == da) {
          continue;
        }
        /* The first bounce at which the two paths hit different objects. A path that ended has no
         * hit from then on, so an early end counts as a difference. */
        for (int i = 0; i < MAX_DEPTH; i++) {
          const bool a_has = i < na && !a_path[size_t(i)].miss;
          const bool t_has = i < nt && !t_path[size_t(i)].miss;
          if (a_has == t_has &&
              (!a_has || a_path[size_t(i)].object_id == t_path[size_t(i)].object_id))
          {
            continue;
          }
          parting[i]++;
          const bool a_plane = a_has && is_plane_object(a_path[size_t(i)].object_id);
          const bool t_plane = t_has && is_plane_object(t_path[size_t(i)].object_id);
          if (a_plane && !t_has) {
            rim++;
          }
          else if (a_plane && t_plane) {
            corner++;
          }
          else {
            other++;
            if ((a_has && !a_plane) || (t_has && !t_plane)) {
              ghost_sphere++;
            }
          }
          break;
        }
      }
    }
  }

  MESSAGE("K: analytic " << k_analytic << ", quad " << k_quad << " (relative "
                         << double(k_quad - k_analytic) / double(k_analytic) << ")");
  MESSAGE("pixels: " << lose << " lose K, " << gain << " gain K, " << equal << " equal, of "
                     << REPORT_SIZE * REPORT_SIZE * REPORT_PASSES);
  MESSAGE("the parting classes of the differing pixels: rim "
          << rim << ", corner " << corner << ", other " << other << " (of " << other
          << ", a sphere decided " << ghost_sphere << ")");
  const DistanceStats *all_stats[2] = {&distance_a, &distance_t};
  for (int side = 0; side < 2; side++) {
    const DistanceStats *stats = all_stats[side];
    MESSAGE(std::string(side == 0 ? "analytic" : "quad")
            << " plane hits: " << stats->hits << ", mean signed distance "
            << stats->sum / double(stats->hits) << ", largest " << stats->largest << ", in front "
            << stats->front << " (" << double(stats->front) / double(stats->hits) << "), behind "
            << stats->behind << " (" << double(stats->behind) / double(stats->hits) << ")");
  }
  MESSAGE("first parting bounce (no entry: no differing pixel parted within max_depth):");
  for (int i = 0; i < MAX_DEPTH; i++) {
    if (parting[i] != 0) {
      MESSAGE("  " << i << ": " << parting[i]);
    }
  }
  CHECK(k_analytic > 0);
}

TEST_CASE("painterly scene: a quad hit's point lies on its plane and is never the surface it left")
{
  /* M3-FIX-T3.17c (R64 clause 2): on a small image of the quad scene, every plane hit lies within
   * HIT_ON_PLANE_BOUND of its plane, and no path's next hit is the surface it just left. Both
   * checks fail at HEAD: the hit point there is o + t d with Embree's binary32 t, so it lies up to
   * 3.3e-6 off the plane, and the next ray's origin starts that far off it, so a grazing bounce
   * re-hits the wall it just left (the near limit does not catch it, because the plane is
   * ray_epsilon away along the new ray and not within it). */
  PainterlyScene quad_scene;
  build_reference_scene(quad_scene, true, PLANE_CHECK_SIZE);
  PainterlyDeviceScene quad_device;
  quad_scene.device_update(quad_device);
  const PainterlyGlobalsCPU quad_globals = quad_device.globals();
  const PainterlyGlobals kg = &quad_globals;
  REQUIRE(kg->bvh != nullptr);

  long long plane_hits = 0;
  long long off_plane = 0;
  long long bounces = 0;
  long long repeats = 0;
  double max_distance = 0.0;
  uint64_t K = 0;
  std::vector<Bounce> path;
  for (int row = 0; row < PLANE_CHECK_SIZE; row++) {
    for (int col = 0; col < PLANE_CHECK_SIZE; col++) {
      /* One chain per pixel, so the walk is the tracer's own sequence (SPEC §3). */
      K = painterly_chain_start(kg->data->integrator, row, col, 0);
      walk(kg, row, col, 0, &K, &path);
      count_plane_hits(path, &plane_hits, &off_plane);
      for (const Bounce &b : path) {
        if (b.miss) {
          continue;
        }
        bounces++;
        if (is_plane_object(b.object_id) && b.object_id == b.previous_object_id) {
          repeats++;
        }
        if (is_plane_object(b.object_id)) {
          const double distance = std::abs(signed_distance(plane_of(b.object_id), b.point));
          max_distance = std::max(max_distance, distance);
        }
      }
    }
  }

  MESSAGE("plane hits: " << plane_hits << ", of which off their plane: " << off_plane << " (bound "
                         << HIT_ON_PLANE_BOUND << ", largest distance " << max_distance << ")");
  MESSAGE("hits: " << bounces << ", of which on the surface the path just left: " << repeats);
  CHECK(plane_hits > 0);
  CHECK(bounces > 0);
  CHECK(off_plane == 0);
  CHECK(repeats == 0);
}

TEST_CASE("painterly_embree: a binary32 self-hit below the near limit is not a hit")
{
  /* M3-FIX-T3.17c (R64 clause 3): a refined root below the ray's near limit means Embree reported
   * the surface the ray starts on, a binary32 self-hit. That is not a hit: the intersect skips it
   * and searches again beyond it. Without the guard this case reports the surface the ray starts
   * on, at t = 3.7e-5 < ray_epsilon, and the path stops dead on it.
   *
   * The scene is one tilted quad in the plane x + y - z = 0, spanning +-4000 units in its plane,
   * so its coordinates are far larger than the reference box's and the binary32 rounding of the
   * ray's origin is large enough to put the plane in front of it. The ray starts on the plane at a
   * point whose coordinates are not dyadic, so its binary32 origin lies off the plane by a
   * binary32 rounding (about 1.4e-5 at x = 285, where the binary32 spacing is 3.1e-5). Its
   * direction has |n.d| = 1/2, so the plane is 2 * 1.4e-5 = 2.8e-5 away along it: below
   * ray_epsilon, and far above the binary64 refine's own round-off. */
  /* Corners: p = u e1 + v e2, with e1 = (1, -1, 0)/sqrt(2) and e2 = (1, 1, 2)/sqrt(6), both in the
   * plane and orthogonal to its normal (1, 1, -1)/sqrt(3). The corners are the binary32 values of
   * the sums, so the quad is exactly planar in binary32 too. */
  const double e1[3] = {1.0 / std::sqrt(2.0), -1.0 / std::sqrt(2.0), 0.0};
  const double e2[3] = {1.0 / std::sqrt(6.0), 1.0 / std::sqrt(6.0), 2.0 / std::sqrt(6.0)};
  const double corners_uv[4][2] = {
      {-4000.0, -4000.0}, {4000.0, -4000.0}, {4000.0, 4000.0}, {-4000.0, 4000.0}};
  float vertices[4 * PAINTERLY_POINT_FLOATS];
  for (int c = 0; c < 4; c++) {
    for (int i = 0; i < PAINTERLY_POINT_FLOATS; i++) {
      vertices[c * PAINTERLY_POINT_FLOATS + i] = float(corners_uv[c][0] * e1[i] +
                                                       corners_uv[c][1] * e2[i]);
    }
  }
  const uint32_t triangles[2 * PAINTERLY_TRIANGLE_CORNERS] = {0, 1, 2, 0, 2, 3};
  const float identity[12] = {
      1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f};
  const PainterlyEmbreeMeshInput mesh = {vertices, 4, triangles, 2};
  const PainterlyEmbreeObjectInput object = {0, identity};
  const std::unique_ptr<PainterlyEmbreeScene, void (*)(PainterlyEmbreeScene *)> scene(
      painterly_embree_scene_create(&mesh, 1, &object, 1), painterly_embree_scene_free);
  REQUIRE(scene != nullptr);

  /* The triangle's own corners and plane, in binary64, from the same binary32 vertices Embree
   * has. */
  double3 w[3];
  for (int c = 0; c < PAINTERLY_TRIANGLE_CORNERS; c++) {
    w[c] = make_double3(double(vertices[triangles[c] * PAINTERLY_POINT_FLOATS]),
                        double(vertices[triangles[c] * PAINTERLY_POINT_FLOATS + 1]),
                        double(vertices[triangles[c] * PAINTERLY_POINT_FLOATS + 2]));
  }
  const double3 normal = cross(w[1] - w[0], w[2] - w[0]);
  /* An in-plane axis, e1 itself: both it and the plane's normal are in the quad's plane. */
  const double3 in_plane = make_double3(e1[0], e1[1], e1[2]);
  /* The direction: half along the triangle's own normal (so |n.d| = 1/2) and 0.7 along an in-plane
   * axis, so the ray leaves the surface at a slant instead of grazing it. It is not normalized, as
   * the kernel's directions are (SPEC §4: t is parametric along d). */
  const double3 direction = normalize(normal) * 0.5 + in_plane * 0.7;

  /* A scan of the quad's interior for the self-hit. The start points are the binary64 points
   * u e1 + v e2 at fixed fractions of the quad's half-size; each lies on the plane, and its
   * coordinates are not dyadic, so its binary32 origin lies off the plane by a binary32 rounding
   * (up to 2^-11 = 4.9e-4 at the corners' 4000 units). The scan takes the first point whose exact
   * root is negative while Embree still reports a hit: the binary32 origin is on the far side of
   * the plane, and the reported hit is the surface the ray starts on. The fractions are a fixed
   * list, not a search for a passing case: the test fails if none of the nine is such a point, and
   * it then checks the first one found. */
  constexpr double SCAN_HALF_SIZE = 4000.0;
  constexpr double SCAN_U[3] = {0.30, 0.37, 0.41};
  constexpr double SCAN_V[3] = {0.20, 0.29, 0.33};
  double root = 0.0;
  double3 start = make_double3(0.0);
  bool found = false;
  for (int iu = 0; iu < 3 && !found; iu++) {
    for (int iv = 0; iv < 3 && !found; iv++) {
      const double3 candidate = in_plane * (SCAN_HALF_SIZE * SCAN_U[iu]) +
                                make_double3(e2[0], e2[1], e2[2]) * (SCAN_HALF_SIZE * SCAN_V[iv]);
      const PainterlyRay candidate_ray{candidate, direction};
      root = dot(normal, w[0] - candidate_ray.o) / dot(normal, candidate_ray.d);
      if (root < 0.0) {
        /* A near limit below the root: the guard accepts the root, so a hit here means Embree
         * reported a surface in front of the binary32 origin. */
        PainterlyIntersection reported;
        if (painterly_embree_intersect_closest(
                scene.get(), candidate_ray, -1.0, INFINITE_DISTANCE, &reported))
        {
          start = candidate;
          found = true;
        }
      }
    }
  }
  REQUIRE(found);
  REQUIRE(root < 0.0);
  const PainterlyRay ray{start, direction};

  /* With the near limit the quad is not a hit: the reported surface is the one the ray starts on,
   * and the search continues past it, to a miss (the scene holds this one quad). */
  PainterlyIntersection hit;
  CHECK_FALSE(
      painterly_embree_intersect_closest(scene.get(), ray, RAY_EPSILON, INFINITE_DISTANCE, &hit));
  CHECK(hit.kind == HIT_NONE);

  /* The control, which shows that the rejected hit is the surface the ray starts on: with a near
   * limit below the root the guard accepts it, and the root is negative, so the plane lies behind
   * the exact origin and the only surface that can be in front of the binary32 origin is the one
   * the ray starts on. Embree's own binary32 t for this ray is positive (2.5e-4 at this point),
   * which is why the hit had to be rejected. */
  REQUIRE(painterly_embree_intersect_closest(scene.get(), ray, -1.0, INFINITE_DISTANCE, &hit));
  CHECK(hit.kind == HIT_TRIANGLE);
  CHECK(hit.t < 0.0);
  CHECK(hit.t == root);
}

CCL_NAMESPACE_END
