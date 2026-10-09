/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "painterly/integrator/path_trace.h"

#include <algorithm>
#include <stdexcept>
#include <string>

#include "painterly/kernel/film/write.h"
#include "painterly/kernel/sample/sampler.h"

CCL_NAMESPACE_BEGIN

namespace {

/* The number of lanes in one row (SPEC §3). ROW is one lane of the whole row. LANE is
 * ceil(width / lane_length) lanes, the last one possibly shorter. */
int lanes_per_row(const KernelPainterlyIntegrator &p, const int width)
{
  if (p.chain == CHAIN_ROW) {
    return 1;
  }
  return (width + p.lane_length - 1) / p.lane_length;
}

/* The pixels of one lane (SPEC §3). ROW is the whole row, and LANE is lane_length pixels in global
 * image coordinates. */
int pixels_per_lane(const KernelPainterlyIntegrator &p, const int width)
{
  return p.chain == CHAIN_ROW ? width : p.lane_length;
}

void accumulate_pixel(PainterlyRenderBuffers &buffers,
                      const int row,
                      const int col,
                      const PainterlyPathResult &result)
{
  const int64_t pixel = int64_t(row) * buffers.width + col;
  painterly_film_accumulate(&buffers.combined[size_t(PAINTERLY_CHANNELS * pixel)],
                            result.radiance);
  buffers.k_consumed[size_t(pixel)] += result.k_consumed;
}

}  // namespace

PainterlyPathTrace::PainterlyPathTrace(const PainterlyGlobalsCPU &kg,
                                       PainterlyRenderBuffers &buffers,
                                       PainterlyThreadPool &pool)
    : kg_(&kg), buffers_(buffers), pool_(pool)
{
  const KernelPainterlyIntegrator &p = kg.data->integrator;
  if (p.chain != CHAIN_IMAGE && p.chain != CHAIN_ROW && p.chain != CHAIN_LANE) {
    throw std::invalid_argument("PainterlyPathTrace: unknown chain " + std::to_string(p.chain));
  }
  if (p.chain == CHAIN_LANE && p.lane_length < 1) {
    throw std::invalid_argument("PainterlyPathTrace: lane_length must be >= 1 for CHAIN_LANE");
  }
  if (p.max_depth < 0) {
    throw std::invalid_argument("PainterlyPathTrace: max_depth must be >= 0");
  }
  check_buffers();
  /* Each worker sizes its own scratch in place. Copying one vector into all of them would also
   * copy it through the allocator, and GCC 13 warns about that copy (-Wstringop-overread). */
  scratch_.resize(size_t(pool.num_threads()));
  for (std::vector<PainterlyPathVertex> &worker_scratch : scratch_) {
    worker_scratch.resize(size_t(p.max_depth));
  }
}

void PainterlyPathTrace::check_buffers() const
{
  const KernelPainterlyCamera &cam = kg_->data->cam;
  const size_t pixels = size_t(buffers_.width) * size_t(buffers_.height);
  if (buffers_.width != cam.width || buffers_.height != cam.height ||
      buffers_.combined.size() != pixels * size_t(PAINTERLY_CHANNELS) ||
      buffers_.k_consumed.size() != pixels || buffers_.object_id.size() != pixels)
  {
    throw std::invalid_argument("PainterlyPathTrace: buffers must be reset to the camera's size");
  }
}

bool PainterlyPathTrace::render_passes(const int pass_begin,
                                       const int pass_end,
                                       const std::atomic<bool> &cancel)
{
  check_buffers();
  if (pass_begin < 0 || pass_end < pass_begin) {
    throw std::invalid_argument("render_passes: need 0 <= pass_begin <= pass_end");
  }
  if (pass_begin != buffers_.passes_done) {
    throw std::invalid_argument("render_passes: pass_begin " + std::to_string(pass_begin) +
                                " != passes_done " + std::to_string(buffers_.passes_done));
  }
  /* SPEC §3: K starts at 0 at the beginning of the render, and is never reset between passes. */
  if (pass_begin == 0) {
    image_chain_K_ = 0;
  }

  const KernelPainterlyIntegrator &p = kg_->data->integrator;
  const bool completed = (p.chain == CHAIN_IMAGE) ?
                             render_image_chain(pass_begin, pass_end, cancel) :
                             render_lanes(pass_begin, pass_end, cancel);
  if (completed) {
    buffers_.passes_done = pass_end;
  }
  return completed;
}

bool PainterlyPathTrace::render_image_chain(const int pass_begin,
                                            const int pass_end,
                                            const std::atomic<bool> &cancel)
{
  const int width = buffers_.width;
  const int height = buffers_.height;
  PainterlyPathVertex *scratch = scratch_[0].data();
  uint64_t K = image_chain_K_;
  for (int pass = pass_begin; pass < pass_end; pass++) {
    for (int row = 0; row < height; row++) {
      /* One unit is one row of one pass. The chain's K is kept across the unit boundaries. */
      if (cancel.load()) {
        image_chain_K_ = K;
        return false;
      }
      for (int col = 0; col < width; col++) {
        const PainterlyPathResult result = painterly_trace_pixel(kg_, row, col, pass, &K, scratch);
        accumulate_pixel(buffers_, row, col, result);
      }
    }
  }
  image_chain_K_ = K;
  return true;
}

bool PainterlyPathTrace::render_lanes(const int pass_begin,
                                      const int pass_end,
                                      const std::atomic<bool> &cancel)
{
  const KernelPainterlyIntegrator &p = kg_->data->integrator;
  const int width = buffers_.width;
  const int height = buffers_.height;
  const int per_row = lanes_per_row(p, width);
  const int lane_pixels = pixels_per_lane(p, width);
  std::atomic<bool> interrupted{false};

  /* A unit is one (row, lane_in_row). The unit index is row-major over the lanes. */
  pool_.parallel_for(int64_t(height) * per_row, [&](int64_t unit, int worker) {
    const int row = int(unit / per_row);
    const int lane = int(unit % per_row);
    PainterlyPathVertex *scratch = scratch_[worker].data();

    /* Cancellation is checked before the unit and between its passes (T3.12 card). */
    const auto stop_requested = [&] {
      if (cancel.load() || interrupted.load()) {
        interrupted.store(true);
        return true;
      }
      return false;
    };
    if (stop_requested()) {
      return;
    }

    const int col_begin = lane * lane_pixels;
    const int col_end = std::min(col_begin + lane_pixels, width);
    for (int pass = pass_begin; pass < pass_end; pass++) {
      if (stop_requested()) {
        return;
      }
      uint64_t K = painterly_chain_start(p, row, lane, pass);
      for (int col = col_begin; col < col_end; col++) {
        const PainterlyPathResult result = painterly_trace_pixel(kg_, row, col, pass, &K, scratch);
        accumulate_pixel(buffers_, row, col, result);
      }
    }
  });
  return !interrupted.load();
}

void PainterlyPathTrace::render_object_id()
{
  check_buffers();
  const int width = buffers_.width;
  pool_.parallel_for(buffers_.height, [&](int64_t row, int) {
    for (int col = 0; col < width; col++) {
      const int64_t pixel = row * width + col;
      buffers_.object_id[size_t(pixel)] = painterly_primary_object_id(kg_, int(row), col);
    }
  });
}

CCL_NAMESPACE_END
