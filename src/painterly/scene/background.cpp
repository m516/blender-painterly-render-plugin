/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "painterly/scene/background.h"

#include <cmath>

#include "painterly/util/math_double3.h"

CCL_NAMESPACE_BEGIN

int PainterlyBackground::add_sun(const double3 direction,
                                 const double angle,
                                 const double3 sun_radiance)
{
  KernelPainterlySun sun{};
  sun.direction = normalize(direction);
  /* Half the angular diameter, the definition of an angular disk (SPEC §6). */
  sun.cos_half_angle = std::cos(0.5 * angle);
  sun.radiance = sun_radiance;
  suns.push_back(sun);
  return int(suns.size()) - 1;
}

void PainterlyBackground::device_update(KernelPainterlyBackground &background,
                                        std::vector<KernelPainterlySun> &out_suns) const
{
  background.radiance = radiance;
  background.num_suns = int(suns.size());
  out_suns = suns;
}

CCL_NAMESPACE_END
