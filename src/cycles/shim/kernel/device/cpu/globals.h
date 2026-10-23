/* Shim: replaces Cycles kernel/device/cpu/globals.h without the profiler, OSL or path guiding */

/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: upstream's kernel_array, the KernelGlobalsCPU members and the
 * kernel_data_* macros (kernel/device/cpu/globals.h:29-54, 102-106), without ProfilingState,
 * ThreadKernelGlobalsCPU, OSL and path guiding; KernelGlobals is const KernelGlobalsCPU *. */

#pragma once

#define PAINTERLY_SHIM_KERNEL_DEVICE_CPU_GLOBALS_H 1

#include "kernel/types.h"
#include "util/types_image.h"

/* The one configuration this shim supports: cycles_kernel's definition set (T6.1). */
#if defined(WITH_OSL) || defined(__OSL__) || defined(WITH_PATH_GUIDING) || \
    defined(__PATH_GUIDING__) || defined(WITH_EMBREE) || defined(__EMBREE__) || \
    defined(__KERNEL_GPU__)
#  error "kernel/device/cpu/globals.h shim: no OSL, path guiding, Embree or GPU kernels"
#endif
#ifndef __MAX_CLOSURE__
#  error "kernel/device/cpu/globals.h shim: link cycles_kernel, which defines __MAX_CLOSURE__"
#endif

CCL_NAMESPACE_BEGIN

/* Array for kernel data, with size to be able to assert on invalid data access. */
template<typename T> struct kernel_array {
  const ccl_always_inline T &fetch(const int index) const
  {
    kernel_assert(index >= 0 && index < width);
    return data[index];
  }

  ccl_always_inline void write(const int index, const T &value) const
  {
    data[index] = value;
  }

  T *data = nullptr;
  int width = 0;
};

/* Constant globals shared between all threads. Upstream's KernelGlobalsCPU without the profiler
 * state; painterly has no ThreadKernelGlobalsCPU. */
struct KernelGlobalsCPU {
#define KERNEL_DATA_ARRAY(type, name) kernel_array<const type> name;
#define KERNEL_DATA_ARRAY_WRITABLE(type, name) kernel_array<type> name;
#include "kernel/data_arrays.h"

  KernelData data = {};

  KernelImageLoadRequestedCPU image_load_requested_cpu;
};

using KernelGlobals = const KernelGlobalsCPU *;

/* Abstraction macros */
#define kernel_data_fetch(name, index) (kg->name.fetch(index))
#define kernel_data_write(name, index, value) (kg->name.write(index, value))
#define kernel_data_array(name) (kg->name.data)
#define kernel_data (kg->data)

CCL_NAMESPACE_END
