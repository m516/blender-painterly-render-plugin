/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* The one ray helper of the bitwise tests (TQ.2 F7). test_analytic.cpp and test_bounce.cpp both
 * turn a test Triple into the ray their kernel function takes, and the two copies were identical,
 * so they live here once. bitwise.h provides the Triple and to_double3(), and
 * painterly/kernel/globals.h the PainterlyRay.
 *
 * Like bitwise.h, everything here is in an unnamed namespace, so each translation unit that
 * includes the header gets its own copy with internal linkage, and the function is inline, so a
 * file that does not call it gets no unused-function warning. */

#include "painterly/kernel/globals.h"

#include "bitwise.h"

CCL_NAMESPACE_BEGIN

namespace {

/* A ray from a test Triple. The direction is kept as it is: PainterlyRay's direction is
 * unnormalized and t is parametric along it (SPEC §4). */
inline PainterlyRay make_ray(const Triple &origin, const Triple &direction)
{
  return PainterlyRay{to_double3(origin), to_double3(direction)};
}

}  // namespace

CCL_NAMESPACE_END
