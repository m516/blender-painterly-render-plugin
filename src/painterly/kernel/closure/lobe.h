/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* Lobe selection for a hit (SPEC §6). A material with several lobes picks one per hit. The choice
 * uses only the stateless RNG, never the sequence counter K (SPEC §2). Every function is a pure
 * function of its arguments. */

#include "painterly/kernel/globals.h"
#include "painterly/kernel/sample/sampler.h"
#include "painterly/kernel/types.h"
#include "painterly/util/math_double3.h"

CCL_NAMESPACE_BEGIN

/* Rec.709 luma coefficients: Y = 0.2126 R + 0.7152 G + 0.0722 B (ITU-R BT.709). They define
 * luminance, so they are not tuning values. SPEC §6. */
constexpr double PAINTERLY_LUMA_RED = 0.2126;
constexpr double PAINTERLY_LUMA_GREEN = 0.7152;
constexpr double PAINTERLY_LUMA_BLUE = 0.0722;

/* Rec.709 luminance of a lobe weight (SPEC §6). */
ccl_device_inline double painterly_luminance(const double3 w)
{
  return w.x * PAINTERLY_LUMA_RED + w.y * PAINTERLY_LUMA_GREEN + w.z * PAINTERLY_LUMA_BLUE;
}

/* SPEC §6. One lobe: returned unchanged, with p = 1 and no RNG draw, so it is bit-exact. Several
 * lobes: lobe k is chosen with probability p_k = lum(w_k) / sum_j lum(w_j), from u =
 * rng_unit(seed, PURPOSE_CLOSURE, depth, row, col, pass). When every luminance is 0 the choice is
 * uniform. The returned weight is w_k / p_k. */
ccl_device_inline KernelPainterlyLobe painterly_select_lobe(
    PainterlyGlobals kg, const KernelPainterlyMaterial &m, int row, int col, int pass, int depth)
{
  const KernelPainterlyLobe *lobes = kg->lobes + m.lobe_offset;
  if (m.num_lobes == 1) {
    return lobes[0];
  }

  /* The total is summed in lobe order, and the cumulative sums below use the same order, so the
   * final cumulative sum equals the total bit for bit. */
  double total = 0.0;
  for (int k = 0; k < m.num_lobes; k++) {
    total = total + painterly_luminance(lobes[k].weight);
  }

  const uint seed = kg->data->integrator.seed;
  const double u = painterly_rng_unit(
      seed, PURPOSE_CLOSURE, uint(depth), uint(row), uint(col), uint(pass));

  KernelPainterlyLobe chosen;
  double p;
  if (total == 0.0) {
    /* Uniform choice. u < 1 (SPEC §2), so floor(u * N) lies in [0, N). */
    const int k = int(u * m.num_lobes);
    chosen = lobes[k];
    p = 1.0 / m.num_lobes;
  }
  else {
    /* u < 1 and the rounding of u * total is monotonic, so x < total: the search below always
     * stops at some lobe k with lum(w_k) > 0. */
    const double x = u * total;
    int k = m.num_lobes - 1;
    double cumulative = 0.0;
    for (int i = 0; i < m.num_lobes; i++) {
      cumulative = cumulative + painterly_luminance(lobes[i].weight);
      if (x < cumulative) {
        k = i;
        break;
      }
    }
    chosen = lobes[k];
    p = painterly_luminance(chosen.weight) / total;
  }

  chosen.weight = chosen.weight / p;
  return chosen;
}

CCL_NAMESPACE_END
