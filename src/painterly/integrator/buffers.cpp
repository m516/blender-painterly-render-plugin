/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "painterly/integrator/buffers.h"

#include <stdexcept>

CCL_NAMESPACE_BEGIN

void PainterlyRenderBuffers::reset(const int width, const int height)
{
  if (width < 0 || height < 0) {
    throw std::invalid_argument("PainterlyRenderBuffers::reset: negative size");
  }
  this->width = width;
  this->height = height;
  const size_t pixels = size_t(width) * size_t(height);
  combined.assign(pixels * size_t(PAINTERLY_CHANNELS), 0.0);
  k_consumed.assign(pixels, 0);
  object_id.assign(pixels, PAINTERLY_OBJECT_ID_MISS);
  passes_done = 0;
}

CCL_NAMESPACE_END
