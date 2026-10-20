/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* PainterlyMaterial: a lobe mixture plus emission (SPEC §6). device_update flattens the lobes of
 * every material into one array, indexed by lobe_offset (painterly/kernel/types.h). */

#include <stdexcept>
#include <vector>

#include "painterly/kernel/types.h"
#include "painterly/util/math_double3.h"

CCL_NAMESPACE_BEGIN

struct PainterlyMaterial {
  std::vector<KernelPainterlyLobe> lobes;
  double3 emission = make_double3(0.0);

  /* Validates the material against the kernel's expectations (SPEC §6): at least one lobe, a known
   * kind, non-negative weights, and ior > 0 for glass. Throws std::invalid_argument with the
   * reason otherwise. A material built through add_material is already valid; the check exists for
   * callers that fill the struct directly. */
  void validate() const
  {
    if (lobes.empty()) {
      throw std::invalid_argument("PainterlyMaterial: a material needs at least one lobe");
    }
    for (const KernelPainterlyLobe &lobe : lobes) {
      if (lobe.kind != LOBE_DIFFUSE && lobe.kind != LOBE_MIRROR && lobe.kind != LOBE_GLASS &&
          lobe.kind != LOBE_TRANSPARENT)
      {
        throw std::invalid_argument("PainterlyMaterial: unknown lobe kind");
      }
      /* `!(w >= 0.0)` rather than `w < 0.0`: a NaN weight fails both comparisons, so only the
       * negated form rejects it, as the ior check below does. A NaN weight would poison every
       * radiance and the Rec.709 luminance the lobe choice divides by (SPEC §6). */
      if (!(lobe.weight.x >= 0.0) || !(lobe.weight.y >= 0.0) || !(lobe.weight.z >= 0.0)) {
        throw std::invalid_argument("PainterlyMaterial: negative or NaN lobe weight");
      }
      if (lobe.kind == LOBE_GLASS && !(lobe.ior > 0.0)) {
        throw std::invalid_argument("PainterlyMaterial: a glass lobe needs ior > 0");
      }
    }
  }
};

CCL_NAMESPACE_END
