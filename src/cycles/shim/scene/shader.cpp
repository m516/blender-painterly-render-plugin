/* Shim: replaces Cycles scene/shader.cpp without devices, OSL, OCIO or lookup tables */

/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: the ShaderManager constructor computes only rgb_to_y.
 * get_attribute_id() (both overloads) and linear_rgb_to_gray() are byte-for-byte copies of
 * scene/shader.cpp:483-502 and 894-897. Shader::set_graph() is scene/shader.cpp:283-312 without
 * the displacement hash (lines 290-293 and 296-305). */

#include "scene/shader.h"
#include "scene/shader_graph.h"
#include "scene/shader_nodes.h"

#include "util/transform.h"

CCL_NAMESPACE_BEGIN

/* Shader */

Shader::~Shader() = default;

/* scene/shader.cpp:283-312 without lines 290-293 and 296-305 (the displacement hash). */
void Shader::set_graph(unique_ptr<ShaderGraph> &&graph_)
{
  /* do this here already so that we can detect if mesh or object attributes
   * are needed, since the node attribute callbacks check if their sockets
   * are connected but proxy nodes should not count */
  if (graph_) {
    graph_->remove_proxy_nodes();
  }

  /* assign graph */
  graph = std::move(graph_);

  /* Store info here before graph optimization to make sure that
   * nodes that get optimized away still count. */
  has_volume_connected = (graph->output()->input("Volume")->link != nullptr);
}

/* Shader Manager */

ShaderManager::ShaderManager()
{
  /* Upstream's constructor calls init_xyz_transforms() (scene/shader.cpp:455-460, 995-1023).
   * Built without OCIO, ColorSpaceManager::get_xyz_to_scene_linear_rgb() returns
   * get_xyz_to_rec709() (util/colorspace.cpp:739, 792), the matrix below
   * (util/colorspace.cpp:687-703). This shim keeps only rgb_to_y, the Y row of its inverse
   * (scene/shader.cpp:1018-1019). */
  const Transform xyz_to_rgb = make_transform(3.2404542f,
                                              -1.5371385f,
                                              -0.4985314f,
                                              0.0f,
                                              -0.9692660f,
                                              1.8760108f,
                                              0.0415560f,
                                              0.0f,
                                              0.0556434f,
                                              -0.2040259f,
                                              1.0572252f,
                                              0.0f);
  const Transform rgb_to_xyz = transform_inverse(xyz_to_rgb);
  rgb_to_y = make_float3(rgb_to_xyz.y);
}

ShaderManager::~ShaderManager() = default;

uint64_t ShaderManager::get_attribute_id(ustring name)
{
  const thread_scoped_spin_lock lock(attribute_lock_);

  /* get a unique id for each name, for SVM attribute lookup */
  const AttributeIDMap::iterator it = unique_attribute_id.find(name);

  if (it != unique_attribute_id.end()) {
    return it->second;
  }

  const uint64_t id = ATTR_STD_NUM + unique_attribute_id.size();
  unique_attribute_id[name] = id;
  return id;
}

uint64_t ShaderManager::get_attribute_id(AttributeStandard std)
{
  return (uint64_t)std;
}

float ShaderManager::linear_rgb_to_gray(const float3 c)
{
  return dot(c, rgb_to_y);
}

CCL_NAMESPACE_END
