/* Shim: replaces Cycles scene/shader.h without devices, OSL, OCIO or lookup tables */

/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: Shader and ShaderManager keep only the members that
 * vendored code and PainterlyShaderManager use. Shader is not a Node: its sockets are plain
 * members with upstream's getters, and it keeps its own reference count. */

#pragma once

#define PAINTERLY_SHIM_SCENE_SHADER_H 1

#include "kernel/types.h"
#include "scene/attribute.h"

#include "util/map.h"
#include "util/param.h"
#include "util/thread.h"
#include "util/types.h"
#include "util/unique_ptr.h"

CCL_NAMESPACE_BEGIN

class Device;
class DeviceScene;
class Progress;
class Scene;
class ShaderGraph;

/* scene/shader.h:42-63, verbatim. */

enum VolumeSampling {
  VOLUME_SAMPLING_DISTANCE = 0,
  VOLUME_SAMPLING_EQUIANGULAR = 1,
  VOLUME_SAMPLING_MULTIPLE_IMPORTANCE = 2,

  VOLUME_NUM_SAMPLING,
};

enum VolumeInterpolation {
  VOLUME_INTERPOLATION_LINEAR = 0,
  VOLUME_INTERPOLATION_CUBIC = 1,

  VOLUME_NUM_INTERPOLATION,
};

enum DisplacementMethod {
  DISPLACE_BUMP = 0,
  DISPLACE_TRUE = 1,
  DISPLACE_BOTH = 2,

  DISPLACE_NUM_METHODS,
};

/* Upstream's Shader (scene/shader.h:71-173) reduced to the members that vendored code and
 * PainterlyShaderManager (card T6.5) use. Upstream's Shader is a Node: its sockets
 * (scene/shader.h:82-89) are plain members here, with the defaults of NODE_DEFINE(Shader)
 * (scene/shader.cpp:51-77) and getters of upstream's names. The other members start with the
 * values of upstream's constructor (scene/shader.cpp:84-122). */
class Shader {
 public:
  ustring name;

  /* shader graph */
  unique_ptr<ShaderGraph> graph;

  bool use_transparent_shadow = true;
  bool use_bump_map_correction = true;
  VolumeSampling volume_sampling_method = VOLUME_SAMPLING_MULTIPLE_IMPORTANCE;
  int volume_interpolation_method = VOLUME_INTERPOLATION_LINEAR;
  DisplacementMethod displacement_method = DISPLACE_BUMP;

  bool get_use_transparent_shadow() const
  {
    return use_transparent_shadow;
  }
  bool get_use_bump_map_correction() const
  {
    return use_bump_map_correction;
  }
  VolumeSampling get_volume_sampling_method() const
  {
    return volume_sampling_method;
  }
  int get_volume_interpolation_method() const
  {
    return volume_interpolation_method;
  }
  DisplacementMethod get_displacement_method() const
  {
    return displacement_method;
  }

  bool has_volume_connected = false;

  /* information about shader after compiling */
  bool has_surface = false;
  bool has_surface_transparent = false;
  bool has_surface_raytrace = false;
  bool has_volume = false;
  bool has_displacement = false;
  bool has_surface_bssrdf = false;
  bool has_bump_from_surface = false;
  bool has_bump_from_displacement = false;
  bool has_bssrdf_bump = false;
  bool has_surface_spatial_varying = false;
  bool has_volume_spatial_varying = false;
  bool has_volume_attribute_dependency = false;
  bool has_light_path_node = false;
  bool has_aov_output_node = false;
  bool has_time_dependency = false;

  /* determined before compiling (scene/shader.cpp:115: id = -1) */
  uint id = ~0u;

  /* Defined in scene/shader.cpp, where ShaderGraph is complete. */
  ~Shader();

  /* Upstream estimates the emission for light sampling (scene/shader.cpp:124-281), with
   * BackgroundNode, PrincipledBsdfNode, LightFalloffNode, IESLightNode, AddClosureNode and
   * MixClosureNode. Painterly samples no lights and has no MIS (SPEC §6), so the call in
   * SVMCompiler::compile (scene/svm.cpp:1235) does nothing. */
  void estimate_emission() {}

  /* scene/shader.cpp:283-312 without the displacement hash: painterly has no true
   * displacement. */
  void set_graph(unique_ptr<ShaderGraph> &&graph);

  /* Return true when either of the surface or displacement socket of the output node is linked.
   * This should be used to ensure that surface attributes are also requested even when only the
   * displacement socket is linked. */
  bool has_surface_link() const
  {
    return has_surface || has_displacement;
  }

  /* Node's reference count (graph/node.h:184-197, 209). Cycles' geometry, lights and background
   * reference the shaders they use, and SVMCompiler::compile_type compiles the closures of a
   * shader only while it is referenced (scene/svm.cpp:1104). */
  int reference_count() const
  {
    return ref_count;
  }
  void reference()
  {
    ref_count += 1;
  }
  void dereference()
  {
    ref_count -= 1;
  }

 private:
  int ref_count{0};
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
