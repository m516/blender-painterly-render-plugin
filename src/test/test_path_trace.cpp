// SPDX-License-Identifier: GPL-3.0-or-later
// Tests of the deterministic lane scheduler (T3.12): painterly/integrator/path_trace.h and
// painterly/util/thread_pool.h. The scene is the 32 x 32 smallpaint reference of SPEC §9
// (smallpaint_scene_fixture.h), which is analytic, so the results do not depend on the ISA. The
// buffers are compared bit for bit (memcmp compares representations, so -0.0 and +0.0 differ), and
// the pool is checked by counts. No tolerance appears.

#include <doctest/doctest.h>

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <utility>
#include <vector>

#include "painterly/integrator/buffers.h"
#include "painterly/integrator/path_trace.h"
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

CCL_NAMESPACE_END
