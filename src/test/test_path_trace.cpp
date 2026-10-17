/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

// Tests of the deterministic lane scheduler (T3.12): painterly/integrator/path_trace.h and
// painterly/util/thread_pool.h. The scene is the 32 x 32 smallpaint reference of SPEC §9
// (smallpaint_scene_fixture.h), which is analytic, so the results do not depend on the ISA. The
// buffers are compared bit for bit (memcmp compares representations, so -0.0 and +0.0 differ), and
// the pool is checked by counts. No tolerance appears.
//
// T3.20 adds the robustness tests of TQ.1 F1-F8: lane lengths of at least the width, cancellation,
// the argument checks, render_object_id, the hit record of painterly_scene_intersect after an
// analytic hit beats a triangle, and the unknown-lobe fail-safe of painterly_trace_pixel.

#include <doctest/doctest.h>

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <stdexcept>
#include <utility>
#include <vector>

#include "painterly/bvh/embree.h"
#include "painterly/integrator/buffers.h"
#include "painterly/integrator/path_trace.h"
#include "painterly/kernel/bvh/bvh.h"
#include "painterly/kernel/integrator/path.h"
#include "painterly/kernel/sample/sampler.h"
#include "painterly/util/thread_pool.h"
#include "smallpaint_scene_fixture.h"

CCL_NAMESPACE_BEGIN

namespace {

using Fixture = SmallpaintSceneFixture;
using Batches = std::vector<std::pair<int, int>>;

// The render covers passes [0, PASSES) (T3.12 card: 0..4).
constexpr int PASSES = 4;
// Thread counts of the determinism test (T3.12 card).
constexpr int THREAD_COUNTS[] = {1, 2, 7};
// The image chain has no lane length, but the fixture needs one of at least 1.
constexpr int NO_LANE_LENGTH = 1;
// Items of the pool test. A count larger than every thread count, so that each worker claims
// several.
constexpr int64_t POOL_ITEMS = 1000;

struct ChainCase {
  const char *name;
  int chain;
  int lane_length;
};

// The chains of the T3.12 card. lane:5 leaves a last lane of 2 pixels (32 = 6 * 5 + 2), and
// lane:16 gives two lanes per row.
const ChainCase CHAIN_CASES[] = {
    {"image", CHAIN_IMAGE, NO_LANE_LENGTH},
    {"row", CHAIN_ROW, NO_LANE_LENGTH},
    {"lane:5", CHAIN_LANE, 5},
    {"lane:16", CHAIN_LANE, 16},
};

// One call that renders all passes, or one call per pass with the last two passes together.
Batches one_batch()
{
  return {{0, PASSES}};
}

Batches split_batches()
{
  return {{0, 1}, {1, 2}, {2, PASSES}};
}

// Renders the scene on a pool of `threads` threads, in the given batches of passes.
PainterlyRenderBuffers render_scene(const Fixture &scene,
                                    const int threads,
                                    const Batches &batches)
{
  PainterlyThreadPool pool(threads);
  PainterlyRenderBuffers buffers;
  buffers.reset(Fixture::WIDTH, Fixture::HEIGHT);
  PainterlyPathTrace trace(scene.globals, buffers, pool);
  const std::atomic<bool> never_cancelled{false};
  for (const auto &[begin, end] : batches) {
    CHECK(trace.render_passes(begin, end, never_cancelled));
  }
  return buffers;
}

// True when the film sums and the K counts of the two renders hold the same bits.
bool bit_identical(const PainterlyRenderBuffers &a, const PainterlyRenderBuffers &b)
{
  return a.combined.size() == b.combined.size() && a.k_consumed.size() == b.k_consumed.size() &&
         std::memcmp(a.combined.data(), b.combined.data(), a.combined.size() * sizeof(double)) ==
             0 &&
         std::memcmp(a.k_consumed.data(),
                     b.k_consumed.data(),
                     a.k_consumed.size() * sizeof(uint64_t)) == 0;
}

}  // namespace

TEST_CASE(
    "painterly lane scheduler: sums and K counts are bit-identical across threads and batching")
{
  for (const ChainCase &c : CHAIN_CASES) {
    INFO("chain=", c.name);
    const Fixture scene(c.chain, c.lane_length);
    const PainterlyRenderBuffers reference = render_scene(scene, 1, one_batch());

    // The reference must not be trivially zero, or the comparison would prove nothing.
    CHECK(reference.passes_done == PASSES);
    uint64_t draws = 0;
    for (const uint64_t k : reference.k_consumed) {
      draws += k;
    }
    CHECK(draws > 0);
    CHECK(std::any_of(
        reference.combined.begin(), reference.combined.end(), [](double v) { return v != 0.0; }));

    for (const int threads : THREAD_COUNTS) {
      for (const bool batched : {false, true}) {
        INFO("threads=", threads, " batched=", batched);
        const PainterlyRenderBuffers other = render_scene(
            scene, threads, batched ? split_batches() : one_batch());
        CHECK(other.passes_done == PASSES);
        CHECK(bit_identical(reference, other));
      }
    }
  }
}

TEST_CASE("painterly thread pool: every index runs once, on a worker below num_threads")
{
  CHECK(PainterlyThreadPool(0).num_threads() >= 1);
  for (const int threads : THREAD_COUNTS) {
    INFO("threads=", threads);
    PainterlyThreadPool pool(threads);
    CHECK(pool.num_threads() == threads);

    bool called_for_empty = false;
    pool.parallel_for(0, [&](int64_t, int) { called_for_empty = true; });
    CHECK_FALSE(called_for_empty);

    // Each index is written by exactly one call, so the vectors need no atomics.
    std::vector<int> hits(POOL_ITEMS, 0);
    std::vector<int> worker_of(POOL_ITEMS, -1);
    pool.parallel_for(POOL_ITEMS, [&](int64_t index, int worker) {
      hits[size_t(index)] += 1;
      worker_of[size_t(index)] = worker;
    });
    const auto ran_once = [](int h) { return h == 1; };
    CHECK(std::all_of(hits.begin(), hits.end(), ran_once));
    CHECK(std::all_of(worker_of.begin(), worker_of.end(), [threads](int worker) {
      return worker >= 0 && worker < threads;
    }));
  }
}

namespace {

// Lane lengths of at least the width (TQ.1 F1). WIDTH gives one lane that is the whole row,
// WIDTH + 1 one lane longer than the row, and the largest int is where ceil(width / lane_length)
// overflowed before the lane length was clamped to the width.
constexpr int LONG_LANE_LENGTHS[] = {
    Fixture::WIDTH, Fixture::WIDTH + 1, std::numeric_limits<int>::max()};

// The chains of the cancel test (TQ.1 F3): the single-threaded image chain, and lane:5 as in
// CHAIN_CASES.
const ChainCase CANCEL_CASES[] = {
    {"image", CHAIN_IMAGE, NO_LANE_LENGTH},
    {"lane:5", CHAIN_LANE, 5},
};

// One past the last PainterlyLobeKind (painterly/kernel/types.h), so that no case of the lobe
// switch in painterly_trace_pixel matches it (TQ.1 F6).
constexpr int UNKNOWN_LOBE_KIND = LOBE_TRANSPARENT + 1;

// A triangle behind the back wall of the reference scene (the plane z = -5.5, SPEC §9), around
// the -z axis, in world coordinates (TQ.1 F5). A scene parameter. Every coordinate is exact in
// binary32.
const float BEHIND_WALL_VERTICES[9] = {-1.0f, -1.0f, -6.0f, 1.0f, -1.0f, -6.0f, 0.0f, 1.0f, -6.0f};
const uint32_t BEHIND_WALL_TRIANGLE[3] = {0, 1, 2};
// The identity object_to_world: row-major 3x4, the last column is the translation.
const float IDENTITY_OBJECT_TO_WORLD[12] = {
    1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f};

// True when every sum and every K count still holds the 0 that reset() wrote.
bool sums_untouched(const PainterlyRenderBuffers &buffers)
{
  return std::all_of(buffers.combined.begin(),
                     buffers.combined.end(),
                     [](double v) { return v == 0.0; }) &&
         std::all_of(buffers.k_consumed.begin(), buffers.k_consumed.end(), [](uint64_t k) {
           return k == 0;
         });
}

}  // namespace

TEST_CASE("painterly lane scheduler: a lane_length of at least the width equals the row chain")
{
  // SPEC §3: a lane of L >= width pixels is the whole row, with lane_in_row 0, so its K0 is the
  // row chain's K0 and the two chains are the same.
  const Fixture row_scene(CHAIN_ROW, NO_LANE_LENGTH);
  const PainterlyRenderBuffers row = render_scene(row_scene, 1, one_batch());
  CHECK(std::any_of(row.combined.begin(), row.combined.end(), [](double v) { return v != 0.0; }));

  for (const int lane_length : LONG_LANE_LENGTHS) {
    const Fixture scene(CHAIN_LANE, lane_length);
    for (const int threads : THREAD_COUNTS) {
      INFO("lane_length=", lane_length, " threads=", threads);
      const PainterlyRenderBuffers lane = render_scene(scene, threads, one_batch());
      CHECK(lane.passes_done == PASSES);
      CHECK(bit_identical(row, lane));
    }
  }
}

TEST_CASE(
    "painterly lane scheduler: a cancel set before the call returns false and writes nothing")
{
  for (const ChainCase &c : CANCEL_CASES) {
    const Fixture scene(c.chain, c.lane_length);
    for (const int threads : THREAD_COUNTS) {
      INFO("chain=", c.name, " threads=", threads);
      PainterlyThreadPool pool(threads);
      PainterlyRenderBuffers buffers;
      buffers.reset(Fixture::WIDTH, Fixture::HEIGHT);
      PainterlyPathTrace trace(scene.globals, buffers, pool);
      const std::atomic<bool> cancelled{true};
      CHECK_FALSE(trace.render_passes(0, PASSES, cancelled));
      CHECK(buffers.passes_done == 0);
      // Cancellation is checked before every unit (T3.12 card), so no pixel was written.
      CHECK(sums_untouched(buffers));
    }
  }
}

TEST_CASE("painterly lane scheduler: render_passes and render_object_id check order and size")
{
  const Fixture scene(CHAIN_ROW, NO_LANE_LENGTH);
  PainterlyThreadPool pool(1);
  PainterlyRenderBuffers buffers;
  buffers.reset(Fixture::WIDTH, Fixture::HEIGHT);
  PainterlyPathTrace trace(scene.globals, buffers, pool);
  const std::atomic<bool> never_cancelled{false};

  // pass_begin must equal passes_done, which is 0 on fresh buffers, and 0 <= begin <= end.
  CHECK_THROWS_AS(trace.render_passes(1, 2, never_cancelled), std::invalid_argument);
  CHECK_THROWS_AS(trace.render_passes(-1, 0, never_cancelled), std::invalid_argument);
  CHECK_THROWS_AS(trace.render_passes(1, 0, never_cancelled), std::invalid_argument);
  CHECK(buffers.passes_done == 0);
  CHECK(sums_untouched(buffers));

  // Buffers that no longer have the camera's size are rejected by both calls.
  buffers.reset(Fixture::WIDTH + 1, Fixture::HEIGHT);
  CHECK_THROWS_AS(trace.render_passes(0, 1, never_cancelled), std::invalid_argument);
  CHECK_THROWS_AS(trace.render_object_id(), std::invalid_argument);
}

TEST_CASE("painterly lane scheduler: the constructor accepts the knob domain and rejects the rest")
{
  PainterlyThreadPool pool(1);
  PainterlyRenderBuffers buffers;
  buffers.reset(Fixture::WIDTH, Fixture::HEIGHT);
  // Each block changes one knob of the row-chain fixture and restores it.
  Fixture scene(CHAIN_ROW, NO_LANE_LENGTH);
  KernelPainterlyIntegrator &p = scene.data.integrator;

  // k0_phase_lock_bits: the domain is [0, PAINTERLY_K0_BITS] (TQ.1 F4). -1 and
  // PAINTERLY_K0_BITS + 1 are the nearest values outside it.
  p.k0_phase_lock_bits = -1;
  CHECK_THROWS_AS(PainterlyPathTrace(scene.globals, buffers, pool), std::invalid_argument);
  p.k0_phase_lock_bits = PAINTERLY_K0_BITS + 1;
  CHECK_THROWS_AS(PainterlyPathTrace(scene.globals, buffers, pool), std::invalid_argument);
  p.k0_phase_lock_bits = PAINTERLY_K0_BITS;
  CHECK_NOTHROW(PainterlyPathTrace(scene.globals, buffers, pool));
  p.k0_phase_lock_bits = 0;
  CHECK_NOTHROW(PainterlyPathTrace(scene.globals, buffers, pool));

  // max_depth >= 1, as the oracle's --max-depth and the T3.13 socket (TQ.1 F8).
  p.max_depth = 0;
  CHECK_THROWS_AS(PainterlyPathTrace(scene.globals, buffers, pool), std::invalid_argument);
  p.max_depth = 1;
  CHECK_NOTHROW(PainterlyPathTrace(scene.globals, buffers, pool));
  p.max_depth = Fixture::MAX_DEPTH;

  // An unknown chain, and a lane_length below 1 for CHAIN_LANE. Any lane_length >= 1 is valid,
  // the largest int included (TQ.1 F1).
  p.chain = CHAIN_LANE + 1;
  CHECK_THROWS_AS(PainterlyPathTrace(scene.globals, buffers, pool), std::invalid_argument);
  p.chain = CHAIN_LANE;
  p.lane_length = 0;
  CHECK_THROWS_AS(PainterlyPathTrace(scene.globals, buffers, pool), std::invalid_argument);
  p.lane_length = std::numeric_limits<int>::max();
  CHECK_NOTHROW(PainterlyPathTrace(scene.globals, buffers, pool));
  p.chain = CHAIN_ROW;
  p.lane_length = NO_LANE_LENGTH;

  // Buffers that do not have the camera's size.
  buffers.reset(Fixture::WIDTH, Fixture::HEIGHT + 1);
  CHECK_THROWS_AS(PainterlyPathTrace(scene.globals, buffers, pool), std::invalid_argument);
}

TEST_CASE("painterly lane scheduler: render_object_id is painterly_primary_object_id per pixel")
{
  const Fixture scene(CHAIN_ROW, NO_LANE_LENGTH);
  for (const int threads : THREAD_COUNTS) {
    INFO("threads=", threads);
    PainterlyThreadPool pool(threads);
    PainterlyRenderBuffers buffers;
    buffers.reset(Fixture::WIDTH, Fixture::HEIGHT);
    PainterlyPathTrace trace(scene.globals, buffers, pool);
    trace.render_object_id();

    int mismatches = 0;
    for (int row = 0; row < Fixture::HEIGHT; row++) {
      for (int col = 0; col < Fixture::WIDTH; col++) {
        const size_t pixel = size_t(row) * size_t(Fixture::WIDTH) + size_t(col);
        if (buffers.object_id[pixel] != painterly_primary_object_id(scene.kg(), row, col)) {
          mismatches++;
        }
      }
    }
    CHECK(mismatches == 0);
    // The reference scene is closed (SPEC §9), so no pixel keeps the miss value of reset().
    CHECK(std::none_of(buffers.object_id.begin(), buffers.object_id.end(), [](int32_t id) {
      return id == PAINTERLY_OBJECT_ID_MISS;
    }));
    // render_object_id leaves the sums and passes_done alone.
    CHECK(buffers.passes_done == 0);
    CHECK(sums_untouched(buffers));
  }
}

TEST_CASE("painterly scene intersect: an analytic hit that beats a triangle resets the record")
{
  Fixture scene(CHAIN_ROW, NO_LANE_LENGTH);
  const PainterlyEmbreeMeshInput wall_mesh = {BEHIND_WALL_VERTICES, 3, BEHIND_WALL_TRIANGLE, 1};
  const PainterlyEmbreeObjectInput wall_object = {0, IDENTITY_OBJECT_TO_WORLD};
  const std::unique_ptr<PainterlyEmbreeScene, void (*)(PainterlyEmbreeScene *)> bvh(
      painterly_embree_scene_create(&wall_mesh, 1, &wall_object, 1), painterly_embree_scene_free);
  scene.globals.bvh = bvh.get();

  // The ray from the camera along -z misses the four spheres and meets the back wall before the
  // triangle.
  const PainterlyRay ray = {make_double3(0.0), make_double3(0.0, 0.0, -1.0)};
  PainterlyIntersection triangle_hit;
  REQUIRE(painterly_embree_intersect_closest(scene.globals.bvh,
                                             ray,
                                             scene.data.integrator.ray_epsilon,
                                             std::numeric_limits<double>::infinity(),
                                             &triangle_hit));
  CHECK(triangle_hit.kind == HIT_TRIANGLE);

  PainterlyIntersection isect;
  REQUIRE(painterly_scene_intersect(scene.kg(), ray, &isect));
  CHECK(isect.kind == HIT_ANALYTIC);
  CHECK(isect.t < triangle_hit.t);
  // The triangle fields hold their defaults, not the beaten triangle's values.
  const PainterlyIntersection fresh{};
  CHECK(isect.prim == fresh.prim);
  CHECK(isect.u == fresh.u);
  CHECK(isect.v == fresh.v);
  CHECK(isect.Ng.x == fresh.Ng.x);
  CHECK(isect.Ng.y == fresh.Ng.y);
  CHECK(isect.Ng.z == fresh.Ng.z);
}

TEST_CASE("painterly path: an unknown lobe kind ends the path with the emission of its hit")
{
  // With max_depth = 1 every path records one vertex, at its first hit. The backward evaluation
  // adds a zero child radiance to that vertex's emission term (SPEC §6), and x + (+-0) == x
  // bit for bit, so each pass adds exactly the first hit's emission term.
  Fixture first_hit(CHAIN_ROW, NO_LANE_LENGTH);
  first_hit.data.integrator.max_depth = 1;
  const PainterlyRenderBuffers expected = render_scene(first_hit, 1, one_batch());
  CHECK(std::any_of(
      expected.combined.begin(), expected.combined.end(), [](double v) { return v != 0.0; }));

  // Every lobe of every material gets the unknown kind. The default case ends each path at its
  // first hit with that emission term, and no path draws from K.
  Fixture unknown(CHAIN_ROW, NO_LANE_LENGTH);
  for (KernelPainterlyLobe &lobe : unknown.lobes) {
    lobe.kind = UNKNOWN_LOBE_KIND;
  }
  const PainterlyRenderBuffers result = render_scene(unknown, 1, one_batch());
  CHECK(result.passes_done == PASSES);
  REQUIRE(result.combined.size() == expected.combined.size());
  CHECK(std::memcmp(result.combined.data(),
                    expected.combined.data(),
                    result.combined.size() * sizeof(double)) == 0);
  CHECK(std::all_of(
      result.k_consumed.begin(), result.k_consumed.end(), [](uint64_t k) { return k == 0; }));
}

CCL_NAMESPACE_END
