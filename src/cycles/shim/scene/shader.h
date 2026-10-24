/* Shim: replaces Cycles scene/shader.h without devices, OSL, OCIO or lookup tables */

/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: Shader and ShaderManager keep only the members that
 * vendored code uses. */

#pragma once

#define PAINTERLY_SHIM_SCENE_SHADER_H 1

#include "kernel/types.h"
#include "scene/attribute.h"

#include "util/map.h"
#include "util/param.h"
#include "util/thread.h"
#include "util/types.h"

CCL_NAMESPACE_BEGIN

class Device;
class DeviceScene;
class Progress;
class Scene;

/* Upstream's Shader (scene/shader.h:71-173) reduced to the members that vendored code reads:
 * name (scene/svm.cpp:233), has_volume (scene/shader_graph.cpp:159) and has_surface_link()
 * (scene/shader_graph.cpp:156, 164), which reads has_surface and has_displacement. */
class Shader {
 public:
  ustring name;

  bool has_surface = false;
  bool has_volume = false;
  bool has_displacement = false;

  bool has_surface_link() const
  {
    return has_surface || has_displacement;
  }
};

/* Upstream's ShaderManager (scene/shader.h:180-282) reduced to the members that vendored code
 * uses: use_osl() (scene/shader_graph.cpp:366), get_attribute_id() (scene/svm.cpp:538, 543) and
 * linear_rgb_to_gray() (scene/shader_nodes.cpp:2034). The destructor, device_free() and
 * device_update_specific() stay virtual, and the two device hooks pure virtual, as upstream,
 * because SVMShaderManager overrides them (scene/svm.h:32-38). */
class ShaderManager {
 public:
  virtual ~ShaderManager();

  virtual bool use_osl()
  {
    return false;
  }

  virtual void device_free(Device *device, DeviceScene *dscene, Scene *scene) = 0;

  /* get globally unique id for a type of attribute */
  virtual uint64_t get_attribute_id(ustring name);
  virtual uint64_t get_attribute_id(AttributeStandard std);

  float linear_rgb_to_gray(const float3 c);

 protected:
  ShaderManager();

  using AttributeIDMap = unordered_map<ustring, uint64_t>;
  AttributeIDMap unique_attribute_id;

  thread_spin_lock attribute_lock_;

  float3 rgb_to_y;

  virtual void device_update_specific(Device *device,
                                      DeviceScene *dscene,
                                      Scene *scene,
                                      Progress &progress) = 0;
};

CCL_NAMESPACE_END
