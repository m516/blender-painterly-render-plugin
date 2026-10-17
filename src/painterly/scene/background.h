/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* PainterlyBackground: the constant world radiance and the suns a ray that escapes the scene sees
 * (SPEC §6). device_update hands the kernel data to the device scene, which owns the arrays
 * (device_scene.h). */

#include <vector>

#include "painterly/kernel/types.h"
#include "painterly/util/types_double3.h"

CCL_NAMESPACE_BEGIN

class PainterlyBackground {
 public:
  double3 radiance = make_double3(0.0);
  /* Suns, in add_sun order. KernelPainterlySun::direction is unit and cos_half_angle is
   * cos(angle/2) (SPEC §6). */
  std::vector<KernelPainterlySun> suns;

  /* SPEC §6: a sun is the angular disk of `angle` radians around `direction`, and a ray hits it
   * iff dot(normalize(d), direction) >= cos(angle / 2). The direction is normalized here, and
   * cos(angle / 2) is stored, so the kernel's test is a plain dot product comparison. */
  int add_sun(const double3 direction, double angle, const double3 sun_radiance);

  void device_update(KernelPainterlyBackground &background,
                     std::vector<KernelPainterlySun> &out_suns) const;
};

CCL_NAMESPACE_END
