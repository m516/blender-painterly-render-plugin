/* Shim: replaces Cycles scene/scene.h without managers other than shader_manager */

/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: class Scene keeps only its shaders, shader_manager and
 * dscene members, and DeviceScene only its shader arrays and KernelData, held in host arrays. */

#pragma once

#define PAINTERLY_SHIM_SCENE_SCENE_H 1

#include "kernel/types.h"
#include "scene/shader.h"

#include "util/array.h"
#include "util/unique_ptr.h"
#include "util/unique_ptr_vector.h"

CCL_NAMESPACE_BEGIN

/* Upstream's DeviceScene (scene/devicescene.h:16-104) reduced to the shader arrays
 * (scene/devicescene.h:77-78) and the KernelData (:101). Painterly has no Device, so the arrays
 * are host arrays instead of device_vector. The SVMCompiler constructor writes data.svm_usage
 * (scene/svm.cpp:169); PainterlyShaderManager (card T6.5) writes the rest. */
class DeviceScene {
 public:
  array<int> svm_nodes;
  array<KernelShader> shaders;

  KernelData data = {};
};

/* Upstream's Scene (scene/scene.h:133) reduced to its shaders (scene/scene.h:158), its
 * shader_manager (:169), which vendored code reads at scene/shader_graph.cpp:366,
 * scene/svm.cpp:538, 543 and scene/shader_nodes.cpp:2034, and its dscene (:186), which
 * scene/svm.cpp:169 reads. */
class Scene {
 public:
  unique_ptr_vector<Shader> shaders;
  unique_ptr<ShaderManager> shader_manager;
  DeviceScene dscene;
};

CCL_NAMESPACE_END
