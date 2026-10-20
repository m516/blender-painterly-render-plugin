/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* PainterlyObject: an instance of a mesh. The transform is the float row-major 3x4 affine that
 * Blender exports and that Embree receives (painterly/bvh/embree.h); the kernel reads the object's
 * normal matrix instead (painterly/kernel/globals.h). */

/* CCL_NAMESPACE_BEGIN/END come from util/defines.h, through util/types.h as every other header of
 * src/painterly/scene/ gets them; the struct itself needs no other header. */
#include "util/types.h"

CCL_NAMESPACE_BEGIN

struct PainterlyObject {
  int mesh = 0;
  float object_to_world[12] = {
      1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f};
  int object_id = 0;
};

CCL_NAMESPACE_END
