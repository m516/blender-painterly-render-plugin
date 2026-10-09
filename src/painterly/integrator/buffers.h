/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* The film buffers of one render (SPEC §7, §8). PainterlyPathTrace (path_trace.h) fills them. The
 * pixel of (row, col) is p = row * width + col, with row 0 at the top (SPEC §0). */

#include <cstdint>
#include <vector>

CCL_NAMESPACE_BEGIN

/* RGB: three channels per pixel (SPEC §7). A count, not a tuning value. */
constexpr int PAINTERLY_CHANNELS = 3;

/* The object id of a miss, as painterly_primary_object_id returns it (kernel/integrator/path.h).
 */
constexpr int32_t PAINTERLY_OBJECT_ID_MISS = -1;

struct PainterlyRenderBuffers {
  int width = 0, height = 0;
  std::vector<double> combined;     /* H*W*3 sums: channel c of pixel p is combined[3 * p + c]. */
  std::vector<uint64_t> k_consumed; /* H*W: K draws of the pixel, summed over its passes. */
  std::vector<int32_t>
      object_id;       /* H*W: object of the unjittered primary hit, or the miss value. */
  int passes_done = 0; /* Passes [0, passes_done) are in combined (SPEC §7). */

  /* Sizes the buffers to width x height, clears the sums and sets passes_done = 0. Throws
   * std::invalid_argument for a negative size. */
  void reset(int width, int height);
};

CCL_NAMESPACE_END
