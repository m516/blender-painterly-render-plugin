/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 * SPDX-FileCopyrightText: 2026 The Painterly Authors
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: adapted from SVMShaderManager (scene/svm.cpp:37-153) and
 * the ShaderManager::device_update_* members (scene/shader.cpp:520-760); each function below
 * says what it leaves out. */

#pragma once

/* PainterlyShaderManager: Cycles' SVM shader manager for painterly (card T6.5). Header-only
 * until M6b gives painterly/scene a library.
 *
 * Cycles compiles shaders in SVMShaderManager (scene/svm.cpp:33-153) and in the
 * ShaderManager::device_update_* members (scene/shader.cpp:520-760). They need a Device, a
 * TaskPool, the LightManager and scene statistics, so they are not vendored (card T6.4). This
 * class ports them. Each function names the upstream lines it ports; code is upstream's except
 * where a comment says what is left out and why. SVMCompiler itself is vendored verbatim
 * (scene/svm.cpp:157-1279, fragments of cards T6.4 and T6.5). The BSDF lookup tables are
 * uploaded by ShaderManager::device_update_lookup_tables() of the shim (card T6.7). */

#include <algorithm>
#include <cassert>

#include "kernel/svm/node_types.h"
#include "kernel/types.h"
#include "scene/scene.h"
#include "scene/shader.h"
#include "scene/shader_graph.h"
#include "scene/shader_nodes.h"
#include "scene/svm.h"

#include "kernel/globals.h"

#include "util/array.h"
#include "util/log.h"
#include "util/progress.h"
#include "util/vector.h"

CCL_NAMESPACE_BEGIN

class PainterlyShaderManager final : public ShaderManager {
 public:
  /* The world shader, or nullptr. Cycles takes it from the scene's Background node
   * (scene->background->get_shader(scene), scene/svm.cpp:49), which the shim Scene does not
   * have. */
  const Shader *background_shader = nullptr;

  /* ShaderManager::device_update_pre (scene/shader.cpp:520-598): numbers the shaders, finalizes
   * their graphs and records what each graph contains. */
  void device_update_pre(Device * /*device*/,
                         DeviceScene *dscene,
                         Scene *scene,
                         Progress & /*progress*/)
  {
    /* Upstream returns unless need_update() (:527). Painterly keeps no update flags and prepares
     * every shader on every call; ShaderGraph::finalize() changes a graph only once
     * (scene/shader_graph.cpp:381). */
    uint id = 0;
    for (Shader *shader : scene->shaders) {
      shader->id = id++;
    }

    /* :536-541 assert Cycles' default shaders, which the shim Scene does not have. */

    /* Preprocess shader graph. */
    bool has_volumes = false;

    for (Shader *shader : scene->shaders) {
      /* Upstream preprocesses only shaders whose is_modified() is true (:547). The shim Shader
       * is not a Node and keeps no modified flags. */
      ShaderNode *output = shader->graph->output();
      shader->has_bump_from_displacement = (shader->get_displacement_method() != DISPLACE_TRUE) &&
                                           output->input("Surface")->link &&
                                           output->input("Displacement")->link;
      shader->has_bssrdf_bump = shader->has_bump_from_displacement;

      shader->graph->finalize(scene,
                              shader->has_bump_from_displacement,
                              shader->get_displacement_method() == DISPLACE_BOTH);

      shader->has_surface = output->input("Surface")->link != nullptr;
      shader->has_surface_transparent = false;
      shader->has_surface_raytrace = false;
      shader->has_surface_bssrdf = false;
      shader->has_surface_spatial_varying = false;
      shader->has_volume = output->input("Volume")->link != nullptr;
      shader->has_volume_spatial_varying = false;
      shader->has_volume_attribute_dependency = false;
      shader->has_displacement = output->input("Displacement")->link != nullptr;
      shader->has_bump_from_surface = false;

      /* Determine both properties. */
      shader->has_light_path_node = false;
      shader->has_aov_output_node = false;
      shader->has_time_dependency = false;
      for (ShaderNode *node : shader->graph->nodes) {
        if (node->special_type == SHADER_SPECIAL_TYPE_LIGHT_PATH) {
          /* TODO: check if the light path node is linked to the volume output. */
          shader->has_light_path_node = true;
        }
        else if (node->special_type == SHADER_SPECIAL_TYPE_OUTPUT_AOV) {
          shader->has_aov_output_node = true;
        }
        else if (node->special_type == SHADER_SPECIAL_TYPE_SCENE_TIME) {
          shader->has_time_dependency = true;
        }
      }

      if (shader->reference_count()) {
        has_volumes |= shader->has_volume;
      }
    }

    /* Set this early as it is needed by volume rendering passes. Upstream also tags the scene
     * (:594-595), which painterly does not track. */
    KernelIntegrator *kintegrator = &dscene->data.integrator;
    kintegrator->use_volumes = has_volumes;
  }

  /* ShaderManager::device_update_post (scene/shader.cpp:600-610) without the copies to a
   * device. */
  void device_update_post(Device *device, DeviceScene *dscene, Scene *scene, Progress &progress)
  {
    device_update_specific(device, dscene, scene, progress);
  }

  /* SVMShaderManager::device_free and ShaderManager::device_free_common (scene/svm.cpp:148-153,
   * scene/shader.cpp:750-760). */
  void device_free(Device * /*device*/, DeviceScene *dscene, Scene *scene) override
  {
    device_free_lookup_tables(scene);
    dscene->shaders.clear();
    dscene->svm_nodes.clear();
  }

  /* Points the kernel arrays that shader evaluation reads at `dscene`, and copies its KernelData
   * (card T6.7): svm_nodes (the byte code), shaders (KernelShader::flags) and lookup_table (the
   * BSDF and thin-film tables that kernel_data.tables indexes). Cycles' CPU device does the same
   * in CPUDevice::global_alloc() and const_copy_to() (device/cpu/device_impl.cpp:178-216). M6b's
   * PainterlyScene binds the other arrays. `globals` keeps pointers into `dscene`. */
  static void bind_kernel_globals(const DeviceScene &dscene, KernelGlobalsCPU &globals)
  {
    globals.svm_nodes.data = reinterpret_cast<const uint *>(dscene.svm_nodes.data());
    globals.svm_nodes.width = int(dscene.svm_nodes.size());
    globals.shaders.data = dscene.shaders.data();
    globals.shaders.width = int(dscene.shaders.size());
    globals.lookup_table.data = dscene.lookup_table.data();
    globals.lookup_table.width = int(dscene.lookup_table.size());
    globals.data = dscene.data;
  }

 protected:
  /* SVMShaderManager::device_update_specific (scene/svm.cpp:57-146). */
  void device_update_specific(Device *device,
                              DeviceScene *dscene,
                              Scene *scene,
                              Progress &progress) override
  {
    /* Upstream returns unless need_update() (:62-64), and times and logs the update (:66-70,
     * :74-76, :144-145). Painterly updates every time and keeps no statistics. */
    const int num_shaders = scene->shaders.size();

    /* test if we need to update */
    device_free(device, dscene, scene);

    /* Build all shaders, one after the other: upstream compiles them in parallel on a TaskPool
     * (:81-89), into the same per-shader arrays. */
    vector<array<int>> shader_svm_nodes(num_shaders);
    for (int i = 0; i < num_shaders; i++) {
      device_update_shader(scene, scene->shaders[i], progress, &shader_svm_nodes[i]);
    }

    if (progress.get_cancel()) {
      return;
    }

    /* The global node list contains a jump table (one jump node per shader)
     * followed by the nodes of all shaders. */
    const int jump_node_size = 1 + sizeof(SVMNodeShaderJump) / sizeof(int);
    int svm_nodes_size = num_shaders * jump_node_size;
    for (int i = 0; i < num_shaders; i++) {
      /* Since we're not copying the local jump node, the size ends up lower. */
      svm_nodes_size += shader_svm_nodes[i].size() - jump_node_size;
    }

    /* A host array: resize() where upstream allocates a device_vector (:104). */
    int *svm_nodes = dscene->svm_nodes.resize(svm_nodes_size);

    int node_offset = num_shaders * jump_node_size;
    for (int i = 0; i < num_shaders; i++) {
      Shader *shader = scene->shaders[i];

      /* Upstream clears the shader's modified flags and tags the LightManager for shaders that
       * emit (:110-113). The shim Shader keeps no such flags, and painterly samples no lights
       * (SPEC §6). */

      /* Update the global jump table.
       * Each compiled shader starts with a jump node that has offsets local
       * to the shader, so copy those and add the offset into the global node list. */
      const int base = shader->id * jump_node_size;
      svm_nodes[base + 0] = NODE_SHADER_JUMP;
      *reinterpret_cast<SVMNodeShaderJump *>(&svm_nodes[base + 1]) = SVMNodeShaderJump{
          .offset_surface = shader_svm_nodes[i][1] - jump_node_size + node_offset,
          .offset_volume = shader_svm_nodes[i][2] - jump_node_size + node_offset,
          .offset_displacement = shader_svm_nodes[i][3] - jump_node_size + node_offset};
      node_offset += shader_svm_nodes[i].size() - jump_node_size;
    }

    /* Copy the nodes of each shader into the correct location. */
    int *dst = svm_nodes + num_shaders * jump_node_size;
    for (int i = 0; i < num_shaders; i++) {
      const int shader_size = shader_svm_nodes[i].size() - jump_node_size;

      std::copy_n(&shader_svm_nodes[i][jump_node_size], shader_size, dst);
      dst += shader_size;
    }

    if (progress.get_cancel()) {
      return;
    }

    device_update_common(device, dscene, scene, progress);

    /* Upstream resets its update flags here (:142). */
  }

  /* SVMShaderManager::device_update_shader (scene/svm.cpp:37-55). */
  void device_update_shader(Scene *scene,
                            Shader *shader,
                            Progress &progress,
                            array<int> *svm_nodes)
  {
    if (progress.get_cancel()) {
      return;
    }
    assert(shader->graph);

    SVMCompiler::Summary summary;
    SVMCompiler compiler(scene, progress);
    compiler.background = (shader == background_shader);
    compiler.compile(shader, *svm_nodes, 0, &summary);

    LOG_DEBUG << "Compilation summary:\n"
              << "Shader name: " << shader->name << "\n"
              << summary.full_report();
  }

  /* ShaderManager::device_update_common (scene/shader.cpp:612-748), reduced to the members of
   * the shim Shader and ShaderManager. */
  void device_update_common(Device * /*device*/,
                            DeviceScene *dscene,
                            Scene *scene,
                            Progress & /*progress*/)
  {
    dscene->shaders.clear();

    if (scene->shaders.empty()) {
      return;
    }

    /* A host array: resize() where upstream allocates a device_vector (:623). */
    KernelShader *kshader = dscene->shaders.resize(scene->shaders.size());
    bool has_transparent_shadow = false;

    for (Shader *shader : scene->shaders) {
      uint flag = 0;

      /* Left out: SD_MIS_FRONT, SD_MIS_BACK and SD_HAS_EMISSION (:629-641) and
       * SD_HAS_CONSTANT_EMISSION (:690-693). They come from the emission estimate, which painterly
       * does not compute (Shader::estimate_emission, shim scene/shader.h). */
      if (shader->has_surface_transparent && shader->get_use_transparent_shadow()) {
        flag |= SD_HAS_TRANSPARENT_SHADOW;
      }
      if (shader->has_surface_raytrace) {
        flag |= SD_HAS_RAYTRACE;
      }
      if (shader->has_volume) {
        flag |= SD_HAS_VOLUME;
        /* todo: this could check more fine grained, to skip useless volumes
         * enclosed inside an opaque bsdf.
         */
        flag |= SD_HAS_TRANSPARENT_SHADOW;
      }
      /* in this case we can assume transparent surface */
      if (shader->has_volume_connected && !shader->has_surface) {
        flag |= SD_HAS_ONLY_VOLUME;
      }
      if (shader->has_volume && shader->has_volume_spatial_varying) {
        flag |= SD_HETEROGENEOUS_VOLUME;
      }
      if (shader->has_volume_attribute_dependency) {
        flag |= SD_NEED_VOLUME_ATTRIBUTES;
      }
      if (shader->has_bssrdf_bump) {
        flag |= SD_HAS_BSSRDF_BUMP;
      }
      if (shader->get_volume_sampling_method() == VOLUME_SAMPLING_EQUIANGULAR) {
        flag |= SD_VOLUME_EQUIANGULAR;
      }
      if (shader->get_volume_sampling_method() == VOLUME_SAMPLING_MULTIPLE_IMPORTANCE) {
        flag |= SD_VOLUME_MIS;
      }
      if (shader->get_volume_interpolation_method() == VOLUME_INTERPOLATION_CUBIC) {
        flag |= SD_VOLUME_CUBIC;
      }
      if (shader->has_bump_from_displacement) {
        flag |= SD_HAS_BUMP_FROM_DISPLACEMENT;
      }
      if (shader->has_bump_from_surface) {
        flag |= SD_HAS_BUMP_FROM_SURFACE;
      }
      if (shader->get_displacement_method() != DISPLACE_BUMP) {
        flag |= SD_HAS_DISPLACEMENT;
      }
      if (shader->get_use_bump_map_correction()) {
        flag |= SD_USE_BUMP_MAP_CORRECTION;
      }

      if (shader->has_light_path_node) {
        flag |= SD_HAS_LIGHT_PATH_NODE;
      }

      /* regular shader. Left out: pass_id, constant_emission and cryptomatte_id (:699-708),
       * which no painterly pass uses; they stay 0. */
      *kshader = KernelShader{};
      kshader->flags = flag;
      kshader++;

      has_transparent_shadow |= (flag & SD_HAS_TRANSPARENT_SHADOW) != 0;
    }

    /* lookup tables (:714-729): ShaderManager::device_update_lookup_tables() of the shim, which
     * includes scene/shader.tables. The caller runs it after device_update_post() (card T6.7). */

    /* integrator */
    KernelIntegrator *kintegrator = &dscene->data.integrator;
    kintegrator->transparent_shadows = has_transparent_shadow;
    /* Not upstream's place (card T6.7): Cycles' Integrator::device_update writes these from its
     * sockets "Reflective Caustics" and "Refractive Caustics", which default to true
     * (scene/integrator.cpp:119-120, 267-268). Painterly has no Cycles Integrator. Both stay true,
     * so that __CAUSTICS_TRICKS__ (kernel/features.h:138) never drops a glossy, glass or
     * refraction closure (kernel/svm/closure.h:280-285, 354-359, 565-571, 669-675, 742-748,
     * 785-796). */
    kintegrator->caustics_reflective = true;
    kintegrator->caustics_refractive = true;

    /* film: of the color space (:736-747), only rgb_to_y (:742). The shim ShaderManager keeps
     * no other color-space member (card T6.4); NODE_CONVERT reads rgb_to_y
     * (kernel/util/colorspace.h:34-37). */
    KernelFilm *kfilm = &dscene->data.film;
    kfilm->rgb_to_y = make_float4(rgb_to_y);
  }
};

CCL_NAMESPACE_END
