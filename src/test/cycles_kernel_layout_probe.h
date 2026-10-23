/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* Layout fingerprint of the vendored Cycles kernel types, recorded per translation unit.
 * Translation units that disagree compile different KernelData or ShaderData layouts, an ODR
 * violation. test_cycles_kernel_layout.cpp compares one recorded in painterly_tests with one
 * recorded in the library painterly_test_kernel_layout_probe. */

#include <cstddef>

#include "kernel/globals.h"
#include "kernel/types.h"

CCL_NAMESPACE_BEGIN

struct PainterlyKernelLayout {
  size_t max_closure; /* MAX_CLOSURE (kernel/types.h:829-833). */
  /* Bit i is set iff the i-th of these is defined: __OBJECT_MOTION__, __HAIR__, __POINTCLOUD__,
   * __VOLUME__, __SUBSURFACE__, __SHADER_RAYTRACE__, __RAY_DIFFERENTIALS__, __DPDU__, __SVM__,
   * __EMBREE__, __OSL__, __PATH_GUIDING__, __KERNEL_FEATURES__. */
  size_t features;
  size_t shader_closure_size, shader_closure_align;
  size_t shader_data_size, shader_data_align;
  /* offsetof(ShaderData, m) for m = P, N, Ng, wi, type, shader, flag, object_flag, num_closure,
   * num_closure_left, prim, u, v, object, time, ray_length, ray_P, ray_dP, lcg_state,
   * closure_emission_background, closure_transparent_extinction, closure (always last). */
  size_t shader_data_offsets[22];
  size_t kernel_data_size, kernel_data_align;
  /* offsetof(KernelData, m) for m = kernel_features, max_closures, max_shaders,
   * volume_stack_size, cam, bake, tables, light_link_sets, scene_time, background, bvh, film,
   * integrator, image, svm_usage. */
  size_t kernel_data_offsets[15];
  /* sizeof of KernelCamera, KernelFilm, KernelIntegrator, KernelBackground, KernelTables,
   * KernelSVMUsage, KernelObject, KernelShader. */
  size_t kernel_struct_sizes[8];
  size_t kernel_globals_size; /* sizeof(KernelGlobalsCPU), shim kernel/device/cpu/globals.h. */

  bool operator==(const PainterlyKernelLayout &other) const = default;
};

/* `static` on purpose: every translation unit that calls it keeps its own copy and records its
 * own layout. A function with external linkage would be merged by the linker, and the test would
 * compare one translation unit with itself. */
static inline PainterlyKernelLayout painterly_kernel_layout_record()
{
  size_t features = 0;
#ifdef __OBJECT_MOTION__
  features |= size_t(1) << 0;
#endif
#ifdef __HAIR__
  features |= size_t(1) << 1;
#endif
#ifdef __POINTCLOUD__
  features |= size_t(1) << 2;
#endif
#ifdef __VOLUME__
  features |= size_t(1) << 3;
#endif
#ifdef __SUBSURFACE__
  features |= size_t(1) << 4;
#endif
#ifdef __SHADER_RAYTRACE__
  features |= size_t(1) << 5;
#endif
#ifdef __RAY_DIFFERENTIALS__
  features |= size_t(1) << 6;
#endif
#ifdef __DPDU__
  features |= size_t(1) << 7;
#endif
#ifdef __SVM__
  features |= size_t(1) << 8;
#endif
#ifdef __EMBREE__
  features |= size_t(1) << 9;
#endif
#ifdef __OSL__
  features |= size_t(1) << 10;
#endif
#ifdef __PATH_GUIDING__
  features |= size_t(1) << 11;
#endif
#ifdef __KERNEL_FEATURES__
  features |= size_t(1) << 12;
#endif
  return PainterlyKernelLayout{
      .max_closure = MAX_CLOSURE,
      .features = features,
      .shader_closure_size = sizeof(ShaderClosure),
      .shader_closure_align = alignof(ShaderClosure),
      .shader_data_size = sizeof(ShaderData),
      .shader_data_align = alignof(ShaderData),
      .shader_data_offsets = {offsetof(ShaderData, P),
                              offsetof(ShaderData, N),
                              offsetof(ShaderData, Ng),
                              offsetof(ShaderData, wi),
                              offsetof(ShaderData, type),
                              offsetof(ShaderData, shader),
                              offsetof(ShaderData, flag),
                              offsetof(ShaderData, object_flag),
                              offsetof(ShaderData, num_closure),
                              offsetof(ShaderData, num_closure_left),
                              offsetof(ShaderData, prim),
                              offsetof(ShaderData, u),
                              offsetof(ShaderData, v),
                              offsetof(ShaderData, object),
                              offsetof(ShaderData, time),
                              offsetof(ShaderData, ray_length),
                              offsetof(ShaderData, ray_P),
                              offsetof(ShaderData, ray_dP),
                              offsetof(ShaderData, lcg_state),
                              offsetof(ShaderData, closure_emission_background),
                              offsetof(ShaderData, closure_transparent_extinction),
                              offsetof(ShaderData, closure)},
      .kernel_data_size = sizeof(KernelData),
      .kernel_data_align = alignof(KernelData),
      .kernel_data_offsets = {offsetof(KernelData, kernel_features),
                              offsetof(KernelData, max_closures),
                              offsetof(KernelData, max_shaders),
                              offsetof(KernelData, volume_stack_size),
                              offsetof(KernelData, cam),
                              offsetof(KernelData, bake),
                              offsetof(KernelData, tables),
                              offsetof(KernelData, light_link_sets),
                              offsetof(KernelData, scene_time),
                              offsetof(KernelData, background),
                              offsetof(KernelData, bvh),
                              offsetof(KernelData, film),
                              offsetof(KernelData, integrator),
                              offsetof(KernelData, image),
                              offsetof(KernelData, svm_usage)},
      .kernel_struct_sizes = {sizeof(KernelCamera),
                              sizeof(KernelFilm),
                              sizeof(KernelIntegrator),
                              sizeof(KernelBackground),
                              sizeof(KernelTables),
                              sizeof(KernelSVMUsage),
                              sizeof(KernelObject),
                              sizeof(KernelShader)},
      .kernel_globals_size = sizeof(KernelGlobalsCPU),
  };
}

/* Defined in cycles_kernel_layout_probe.cpp (library painterly_test_kernel_layout_probe). */
PainterlyKernelLayout painterly_kernel_layout_probe();

CCL_NAMESPACE_END
