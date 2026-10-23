/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "kernel/globals.h"
#include "kernel/types.h"

#include "painterly/kernel/globals.h"
#include "painterly/kernel/types.h"

#include <iterator>
#include <type_traits>

#include <doctest/doctest.h>

CCL_NAMESPACE_BEGIN

/* kernel/svm/node_types_template.h has 78 SHADER_NODE_TYPE entries and 16
 * SHADER_NODE_TYPE_DERIVATIVE entries; each of the 16 declares two enumerators. */
static_assert(NODE_NUM == 78 + 2 * 16);

/* One int per node type (kernel/data_template.h:256-262) in a ccl_align(16) struct
 * (kernel/types.h:1320). */
static_assert(sizeof(KernelSVMUsage) == (NODE_NUM * sizeof(int) + 15) / 16 * 16);

/* The shim declares every data_arrays.h array, writable exactly where upstream says so. */
#define KERNEL_DATA_ARRAY(type, name) \
  static_assert(std::is_same_v<decltype(KernelGlobalsCPU::name), kernel_array<const type>>);
#define KERNEL_DATA_ARRAY_WRITABLE(type, name) \
  static_assert(std::is_same_v<decltype(KernelGlobalsCPU::name), kernel_array<type>>);
#include "kernel/data_arrays.h"

TEST_CASE("cycles kernel types: Cycles and painterly kernel types coexist")
{
  /* Each pair below collided before the painterly contracts were renamed (docs/plan.md,
   * "Naming (2026-10-09)"). */
  KernelData cycles_data = {};
  KernelPainterlyData painterly_data = {};
  Ray ray = {};
  PainterlyRay painterly_ray = {};
  KernelObject object = {};
  KernelPainterlyObject painterly_object = {};

  /* Enumerator 0 (kernel/types.h:539). */
  CHECK(cycles_data.cam.type == CAMERA_PERSPECTIVE);
  /* Enumerator 0. */
  CHECK(painterly_data.cam.type == PAINTERLY_CAMERA_SMALLPAINT);
  CHECK(ray.tmax == 0.0f);
  CHECK(painterly_ray.d.x == 0.0);
  CHECK(object.numverts == 0);
  CHECK(painterly_object.mesh == 0);
}

TEST_CASE("cycles kernel types: KernelGlobalsCPU arrays and the kernel_data macros")
{
  const uint nodes[] = {7, 11, 13};
  uint8_t access_state[] = {0, 0};

  KernelGlobalsCPU globals;
  globals.svm_nodes.data = nodes;
  globals.svm_nodes.width = int(std::size(nodes));
  globals.image_texture_tile_access_state.data = access_state;
  globals.image_texture_tile_access_state.width = int(std::size(access_state));
  globals.data.max_closures = MAX_CLOSURE;

  /* The macros read a variable named `kg`, as upstream's do. */
  const KernelGlobals kg = &globals;

  CHECK(kernel_data_fetch(svm_nodes, 2) == nodes[2]);
  CHECK(kernel_data_array(svm_nodes) == nodes);
  CHECK(kernel_data.max_closures == MAX_CLOSURE);

  kernel_data_write(image_texture_tile_access_state, 1, uint8_t(9));
  CHECK(access_state[1] == 9);
  CHECK(access_state[0] == 0);
}

CCL_NAMESPACE_END
