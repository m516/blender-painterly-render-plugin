/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "painterly/integrator/buffers.h"

#include <stdexcept>

CCL_NAMESPACE_BEGIN

void PainterlyRenderBuffers::reset(const int new_width, const int new_height)
{
  if (new_width < 0 || new_height < 0) {
    throw std::invalid_argument("PainterlyRenderBuffers::reset: negative size");
  }
  width = new_width;
  height = new_height;
  const size_t pixels = size_t(width) * size_t(height);
  combined.assign(pixels * size_t(PAINTERLY_CHANNELS), 0.0);
  k_consumed.assign(pixels, 0);
  object_id.assign(pixels, PAINTERLY_OBJECT_ID_MISS);
  passes_done = 0;
}

CCL_NAMESPACE_END
