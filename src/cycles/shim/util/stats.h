/* Shim: replaces Cycles util/stats.h without Blender's intern/atomic */
/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: the counters are std::atomic<size_t> instead of the atomic
 * helpers of Blender's intern/atomic (upstream includes util/atomic.h, which is outside the pinned
 * intern/cycles root). The static_init constructor is constexpr, so that the static global_stats
 * in vendored guarded_allocator.cpp stays constant-initialized, as upstream intends. */

#pragma once

#include <atomic>
#include <cassert>
#include <cstddef>

CCL_NAMESPACE_BEGIN

class Stats {
 public:
  enum static_init_t { static_init = 0 };

  Stats() : mem_used(0), mem_peak(0) {}
  constexpr explicit Stats(static_init_t /*unused*/) {}

  void mem_alloc(const size_t size)
  {
    const size_t used = mem_used.fetch_add(size) + size;
    /* Raise the peak to used. The loop ends when another thread has stored a peak of at least
     * used, or when this thread has stored used itself. */
    size_t peak = mem_peak.load();
    while (peak < used && !mem_peak.compare_exchange_weak(peak, used)) {
    }
  }

  void mem_free(const size_t size)
  {
    assert(mem_used >= size);
    mem_used.fetch_sub(size);
  }

  std::atomic<size_t> mem_used;
  std::atomic<size_t> mem_peak;
};

CCL_NAMESPACE_END
