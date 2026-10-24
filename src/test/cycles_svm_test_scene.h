/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* A minimal Cycles scene for SVM tests whose nodes read geometry (card T6.6): the kernel arrays
 * that the Texture Coordinate, Attribute and Geometry nodes read, in Cycles' layout, and the
 * ShaderData of a surface hit and of a background evaluation. Card T6.6, "Minimal
 * KernelGlobalsCPU", lists what each array holds and which upstream code reads it.
 *
 * It includes cycles_svm_test_support.h (card T6.3) first, which must precede every kernel/svm/
 * header. A test source includes this header in its place.
 *
 * One definition rule: svm_eval_nodes() and the kernel/svm/ functions it calls are ccl_device*,
 * which is static on CPU (util/defines.h:25-27 and, for ccl_device_inline and
 * ccl_device_forceinline, :32-33 on MSVC, :48-49 on GCC and Clang). So each translation unit
 * compiles its own copies, which expand the redefined macro. Everything this header defines is in
 * an unnamed namespace for the same reason (cycles_svm_test_support.h, card T6.3): each test
 * translation unit gets its own scene, run function and trace, which call only that unit's
 * svm_eval_nodes(), and no definition with external linkage refers to a static function. Later
 * cards include this header from another translation unit, so the rule holds for them too. */

#include "cycles_svm_test_support.h"

CCL_NAMESPACE_BEGIN
namespace {

/* The kernel data that the Texture Coordinate, Attribute and Geometry nodes read, in Cycles'
 * layout: two objects with one mesh each. Object 0 has identity transforms and the attributes
 * Generated (per vertex) and UV (per corner) on two triangles. Object 1 is translated by
 * (1, 2, 4) and has no attribute; the translation makes the object transform observable. */
struct PainterlySvmTestScene {
  KernelObject objects[2] = {};
  uint object_flag[2] = {0, 0};
  /* Per mesh: one entry per attribute and ATTR_PRIM_TYPES (2) slots each, the second slot of
   * every pair (subdivision) zero, then a terminator pair {ATTR_STD_NONE, element 0}
   * (scene/geometry_attributes.cpp:90-133, 206-236). Mesh of object 0 at 0, of object 1 at 6. */
  AttributeMap attributes_map[8] = {};
  /* Generated, per vertex (ATTR_ELEMENT_VERTEX). */
  packed_float3 attributes_float3[4];
  /* UV, per corner (ATTR_ELEMENT_CORNER): corner k of triangle t is entry 3t + k. */
  float2 attributes_float2[6];
  /* The vertices of each triangle. */
  packed_uint3 tri_vindex[2];

  PainterlySvmTestScene()
  {
    objects[0].tfm = transform_identity();
    objects[0].itfm = transform_identity();
    objects[0].attribute_map_offset = 0;
    objects[1].tfm = transform_translate(1.0f, 2.0f, 4.0f);
    objects[1].itfm = transform_translate(-1.0f, -2.0f, -4.0f);
    objects[1].attribute_map_offset = 6;

    attributes_map[0] = AttributeMap{
        ATTR_STD_GENERATED, 0, ATTR_ELEMENT_VERTEX, NODE_ATTR_FLOAT3, 0};
    attributes_map[2] = AttributeMap{ATTR_STD_UV, 0, ATTR_ELEMENT_CORNER, NODE_ATTR_FLOAT2, 0};

    attributes_float3[0] = make_float3(0.0f, 0.0f, 0.0f);
    attributes_float3[1] = make_float3(1.0f, 0.0f, 0.0f);
    attributes_float3[2] = make_float3(0.0f, 1.0f, 0.0f);
    attributes_float3[3] = make_float3(0.0f, 0.0f, 1.0f);

    attributes_float2[0] = make_float2(0.0f, 0.0f);
    attributes_float2[1] = make_float2(1.0f, 0.0f);
    attributes_float2[2] = make_float2(0.0f, 1.0f);
    attributes_float2[3] = make_float2(0.5f, 0.5f);
    attributes_float2[4] = make_float2(1.0f, 0.5f);
    attributes_float2[5] = make_float2(0.5f, 1.0f);

    tri_vindex[0] = packed_uint3(0, 1, 2);
    tri_vindex[1] = packed_uint3(3, 1, 2);
  }

  /* Points the kernel arrays of `globals` at this scene, and sets the camera that the Camera and
   * Window coordinates read. */
  void bind(KernelGlobalsCPU &globals) const
  {
    globals.objects.data = objects;
    globals.objects.width = 2;
    globals.object_flag.data = object_flag;
    globals.object_flag.width = 2;
    globals.attributes_map.data = attributes_map;
    globals.attributes_map.width = 8;
    globals.attributes_float3.data = attributes_float3;
    globals.attributes_float3.width = 4;
    globals.attributes_float2.data = attributes_float2;
    globals.attributes_float2.width = 6;
    globals.tri_vindex.data = tri_vindex;
    globals.tri_vindex.width = 2;

    globals.data.cam.type = CAMERA_PERSPECTIVE;
    globals.data.cam.worldtocamera = transform_translate(0.0f, 0.0f, -8.0f);
    globals.data.cam.cameratoworld = transform_translate(0.0f, 0.0f, 8.0f);
    globals.data.cam.worldtondc.x = make_float4(0.5f, 0.0f, 0.0f, 0.5f);
    globals.data.cam.worldtondc.y = make_float4(0.0f, 0.5f, 0.0f, 0.5f);
    globals.data.cam.worldtondc.z = make_float4(0.0f, 0.0f, 0.0f, 0.0f);
    globals.data.cam.worldtondc.w = make_float4(0.0f, 0.0f, 0.0f, 1.0f);
  }

  /* A surface hit on triangle `prim` of `object` at barycentrics (u, v) = (0.25, 0.5), as
   * shader_setup_from_ray() fills ShaderData (kernel/geom/shader_data.h:57-74): object_flag is
   * copied from the object_flag array. No SHADER_SMOOTH_NORMAL bit, so normals are flat. */
  ShaderData surface(const int object, const int prim) const
  {
    ShaderData sd = painterly_svm_test_shader_data(0);
    sd.P = make_float3(1.5f, 2.25f, 4.125f);
    sd.N = make_float3(0.0f, 0.0f, 1.0f);
    sd.Ng = sd.N;
    sd.wi = make_float3(0.5f, 0.0f, 0.5f);
    sd.type = PRIMITIVE_TRIANGLE;
    sd.object = object;
    sd.object_flag = object_flag[object];
    sd.prim = prim;
    sd.u = 0.25f;
    sd.v = 0.5f;
    return sd;
  }

  /* A background evaluation: no object, no primitive. */
  ShaderData background() const
  {
    ShaderData sd = painterly_svm_test_shader_data(0);
    sd.P = make_float3(1.5f, 2.25f, 4.125f);
    sd.wi = make_float3(0.5f, 0.0f, 0.5f);
    sd.type = PRIMITIVE_NONE;
    sd.object = OBJECT_NONE;
    sd.prim = PRIM_NONE;
    return sd;
  }
};

/* painterly_svm_test_run() (cycles_svm_test_support.h, card T6.3) with a caller-supplied
 * ShaderData, for nodes that read ShaderData fields that painterly_svm_test_shader_data() leaves
 * zero. */
template<ShaderType type = SHADER_TYPE_SURFACE>
inline PainterlySvmTrace painterly_svm_test_run_shader_data(
    KernelGlobalsCPU &globals,
    const PainterlySvmTestProgram &program,
    ShaderData &sd,
    const PathRayVisibility path_visibility = PathRayVisibility(0))
{
  globals.svm_nodes.data = program.words().data();
  globals.svm_nodes.width = program.size();
  painterly_svm_trace() = PainterlySvmTrace{};
  const KernelGlobals kg = &globals;
  svm_eval_nodes<painterly_svm_test_node_feature_mask, type>(
      kg, nullptr, &sd, nullptr, path_visibility, uint32_t(0));
  return painterly_svm_trace();
}

}  // namespace
CCL_NAMESPACE_END
