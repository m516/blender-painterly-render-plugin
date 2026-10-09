/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* The film accumulation of smallpaint (SPEC §7). A pixel's sum is taken over its passes in
 * increasing pass order. The function is a pure function of its arguments. */

#include "painterly/util/types_double3.h"

CCL_NAMESPACE_BEGIN

/* sum += L per channel, in pass order (SPEC §7; smallpaint_painterly.cpp:295-297). Each channel is
 * one double addition, so a pixel's sum depends only on the order of its passes. */
ccl_device_inline void painterly_film_accumulate(double *pixel_sum_rgb, double3 L)
{
  pixel_sum_rgb[0] = pixel_sum_rgb[0] + L.x;
  pixel_sum_rgb[1] = pixel_sum_rgb[1] + L.y;
  pixel_sum_rgb[2] = pixel_sum_rgb[2] + L.z;
}

CCL_NAMESPACE_END
