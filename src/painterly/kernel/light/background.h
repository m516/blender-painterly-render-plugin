/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* The world radiance seen by a ray that escapes the scene (SPEC §6). The function is a pure
 * function of its arguments and of the device scene. */

#include "painterly/kernel/globals.h"
#include "painterly/util/math_double3.h"

CCL_NAMESPACE_BEGIN

/* Constant world radiance plus every sun whose angular disk contains normalize(d), summed in sun
 * order (SPEC §6): a sun is hit iff dot(normalize(d), sun.direction) >= sun.cos_half_angle. The
 * result is before emission_gain, which the path applies. */
ccl_device_inline double3 painterly_background_radiance(PainterlyGlobals kg, const double3 d)
{
  const KernelPainterlyBackground &background = kg->data->background;
  const double3 dir = normalize(d);
  double3 L = background.radiance;
  for (int i = 0; i < background.num_suns; i++) {
    const KernelPainterlySun &sun = kg->suns[i];
    if (dot(dir, sun.direction) >= sun.cos_half_angle) {
      L = L + sun.radiance;
    }
  }
  return L;
}

CCL_NAMESPACE_END
