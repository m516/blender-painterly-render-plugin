/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* PainterlyAnalyticPrimitive: a sphere (ghost or exact) or a plane (SPEC §5, §9). Its kernel form
 * is KernelPainterlyAnalytic, which the device scene copies in list order. */

#include "painterly/kernel/types.h"
#include "painterly/util/types_double3.h"

CCL_NAMESPACE_BEGIN

struct PainterlyAnalyticPrimitive {
  PainterlyAnalyticType type = ANALYTIC_SPHERE;
  PainterlySphereIntersection intersection = SPHERE_GHOST;
  int material = 0;
  /* SPEC §9: the value written to the object_id buffer. */
  int object_id = 0;
  /* sphere: centre. plane: unit normal n. */
  double3 a = make_double3(0.0);
  /* sphere: radius. plane: d with n.p + d = 0. */
  double b = 0.0;
  /* Spot cone emission profile (SPEC §5). enabled == 0 means isotropic emission. */
  KernelPainterlySpotProfile spot = {0, make_double3(0.0), 1.0, 0.0};
};

CCL_NAMESPACE_END
