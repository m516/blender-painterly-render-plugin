/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* The lane scheduler of the painterly integrator (T3.12, SPEC §3, §7). It drives
 * painterly_trace_pixel over the chains of the knob `chain` and accumulates the film. Lanes are
 * independent, so the output does not depend on the number of threads or on how the passes are
 * batched (docs/architecture.md, "Determinism contract"). */

#include <atomic>
#include <cstdint>
#include <vector>

#include "painterly/integrator/buffers.h"
#include "painterly/kernel/globals.h"
#include "painterly/kernel/integrator/path.h"
#include "painterly/util/thread_pool.h"

CCL_NAMESPACE_BEGIN

class PainterlyPathTrace {
 public:
  /* Throws std::invalid_argument when the chain is unknown, lane_length < 1 for CHAIN_LANE,
   * max_depth < 0, or buffers do not have the camera's size. The buffers and the pool must outlive
   * this object. */
  PainterlyPathTrace(const PainterlyGlobalsCPU &kg,
                     PainterlyRenderBuffers &buffers,
                     PainterlyThreadPool &pool);

  /* Renders passes [pass_begin, pass_end) in SPEC §3 order and adds them to buffers (SPEC §7).
   *   pass_begin must equal buffers.passes_done, so that every pixel sums its passes in increasing
   *   order. Otherwise the call throws std::invalid_argument.
   *   CHAIN_IMAGE: one chain, single-threaded. K continues across calls, and it restarts at 0 when
   *   pass_begin is 0 (the start of a render).
   *   CHAIN_ROW and CHAIN_LANE: the units are (row, lane_in_row). Each unit runs all passes of the
   *   range for its lane on one worker, so each pixel is written by one unit only.
   * Returns true, with buffers.passes_done = pass_end, when every unit finished. Returns false
   * when `cancel` was observed by any unit. Then passes_done does not advance, and some pixels may
   * hold partial contributions. The caller must reset the buffers before it renders again. */
  bool render_passes(int pass_begin, int pass_end, const std::atomic<bool> &cancel);

  /* Fills buffers.object_id with the object of each unjittered primary hit, or
   * PAINTERLY_OBJECT_ID_MISS (painterly_primary_object_id). Parallel over rows. It does not touch
   * the sums or passes_done. */
  void render_object_id();

 private:
  void check_buffers() const;
  bool render_image_chain(int pass_begin, int pass_end, const std::atomic<bool> &cancel);
  bool render_lanes(int pass_begin, int pass_end, const std::atomic<bool> &cancel);

  const PainterlyGlobalsCPU *kg_;
  PainterlyRenderBuffers &buffers_;
  PainterlyThreadPool &pool_;
  /* Scratch of one path per worker: scratch_[worker] holds max_depth vertices (SPEC §6). */
  std::vector<std::vector<PainterlyPathVertex>> scratch_;
  /* The K of CHAIN_IMAGE, carried across render_passes calls (SPEC §3). */
  uint64_t image_chain_K_ = 0;
};

CCL_NAMESPACE_END
