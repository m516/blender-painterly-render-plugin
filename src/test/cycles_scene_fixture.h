/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* A Scene for tests of cycles_scene (card T6.4). Upstream's ShaderManager is abstract: its device
 * hooks device_free() and device_update_specific() are pure virtual (scene/shader.h:203,
 * 275-278). Painterly never runs Cycles' device update, so the test manager implements both as
 * no-ops. */

#include "scene/scene.h"
#include "scene/shader.h"

#include "util/unique_ptr.h"

CCL_NAMESPACE_BEGIN

class PainterlyTestShaderManager final : public ShaderManager {
 public:
  void device_free(Device * /*device*/, DeviceScene * /*dscene*/, Scene * /*scene*/) override {}

 protected:
  void device_update_specific(Device * /*device*/,
                              DeviceScene * /*dscene*/,
                              Scene * /*scene*/,
                              Progress & /*progress*/) override
  {
  }
};

/* A Scene whose shader_manager is a PainterlyTestShaderManager. */
inline unique_ptr<Scene> painterly_test_scene()
{
  unique_ptr<Scene> scene = make_unique<Scene>();
  scene->shader_manager = make_unique<PainterlyTestShaderManager>();
  return scene;
}

CCL_NAMESPACE_END
