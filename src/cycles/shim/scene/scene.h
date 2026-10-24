/* Shim: replaces Cycles scene/scene.h without managers other than shader_manager */

/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: class Scene keeps only its shader_manager member. */

#pragma once

#define PAINTERLY_SHIM_SCENE_SCENE_H 1

#include "scene/shader.h"

#include "util/unique_ptr.h"

CCL_NAMESPACE_BEGIN

/* Upstream's Scene (scene/scene.h:133) reduced to its shader_manager (scene/scene.h:169), which
 * vendored code reads at scene/shader_graph.cpp:366, scene/svm.cpp:538, 543 and
 * scene/shader_nodes.cpp:2034. */
class Scene {
 public:
  unique_ptr<ShaderManager> shader_manager;
};

CCL_NAMESPACE_END
