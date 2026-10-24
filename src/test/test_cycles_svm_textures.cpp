/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* Cycles' texture and texture-coordinate SVM nodes (card T6.6), run through the generated
 * svm_eval_nodes() of cycles_svm on hand-encoded byte code (cycles_svm_test_support.h, T6.3).
 *
 * Every expected value is an evaluation of the upstream formula that does not run the code
 * under test:
 * - by hand, in the comment next to it, when the inputs make every intermediate result exactly
 *   representable in float32. No operation rounds then, so neither the order of operations, nor
 *   the SSE code paths, nor FMA contraction can change the result;
 * - otherwise by a reference function in this file that repeats the upstream formula operation
 *   by operation. A reference function may call util/ helpers (util/hash.h, util/math*.h,
 *   vendored by card T3.2) but never a kernel/svm/ function. Its C library calls take their
 *   arguments through opaque(), so that the compiler cannot evaluate them at compile time, which
 *   may round differently from the run-time call that the kernel makes.
 * check_equal() compares inside the VM with exact equality (T6.3). Evaluation draws no random
 * number: lcg_state is 0 (painterly_svm_test_shader_data, T6.3). */

#include "cycles_svm_test_scene.h"

#include <cfloat>
#include <cmath>

#include <doctest/doctest.h>

CCL_NAMESPACE_BEGIN

namespace {

/* run_program_and_check() of card T6.3 for a caller-supplied ShaderData, with the expected
 * number of fetches from kernel arrays other than svm_nodes. */
void run_and_check(KernelGlobalsCPU &globals,
                   PainterlySvmTestProgram &program,
                   ShaderData &sd,
                   const int other_arrays)
{
  program.add_node(NODE_END);
  const PainterlySvmTrace trace = painterly_svm_test_run_shader_data(globals, program, sd);
  CHECK(program.fetched_trace(trace.svm_nodes) == program.expected_trace(0));
  CHECK(trace.other_arrays == other_arrays);
  CHECK(program.failed_checks(trace.svm_nodes) == "");
}

/* A program for shader 0 whose jump entry points at the first node added (T6.3). */
PainterlySvmTestProgram new_program()
{
  PainterlySvmTestProgram program;
  const int start = program.size();
  program.set_jump(0, start, start, start);
  return program;
}

/* Writes `value` to stack slots slot..slot+2. */
void add_vector(PainterlySvmTestProgram &program, const SVMStackOffset slot, const float3 value)
{
  program.add_node(NODE_VALUE_V, SVMNodeValueV{.out_offset = slot, .value = value});
}

SVMInputFloat c(const float value)
{
  return painterly_svm_input_constant(value);
}

SVMInputFloat3 c3(const float x, const float y, const float z)
{
  return painterly_svm_input_constant3(x, y, z);
}

float opaque(const float x)
{
  volatile float copy = x;
  return copy;
}

float3 opaque3(const float3 v)
{
  return make_float3(opaque(v.x), opaque(v.y), opaque(v.z));
}

/* ---- Reference functions ---- */

/* svm_gradient() (kernel/svm/gradient.h:14-57) for NODE_BLEND_RADIAL,
 * NODE_BLEND_QUADRATIC_SPHERE and NODE_BLEND_SPHERICAL, then saturatef() (gradient.h:65). */
float gradient_reference(const float3 p, const NodeGradientType type)
{
  const float x = opaque(p.x);
  const float y = opaque(p.y);
  const float z = opaque(p.z);
  if (type == NODE_BLEND_RADIAL) {
    return saturatef(atan2f(y, x) / M_2PI_F + 0.5f);
  }
  const float r = fmaxf(0.999999f - sqrtf(x * x + y * y + z * z), 0.0f);
  return saturatef((type == NODE_BLEND_QUADRATIC_SPHERE) ? r * r : r);
}

/* svm_magic() (kernel/svm/magic.h:14-100) for depth 2. */
float3 magic_depth2_reference(const float3 p_in, const float scale_in, const float distortion_in)
{
  const float3 p = opaque3(p_in);
  const float scale = opaque(scale_in);
  float distortion = opaque(distortion_in);

  const float px = fmodf(p.x * scale, M_2PI_F);
  const float py = fmodf(p.y * scale, M_2PI_F);
  const float pz = fmodf(p.z * scale, M_2PI_F);

  float x = sinf((px + py + pz) * 5.0f);
  float y = cosf((-px + py - pz) * 5.0f);
  float z = -cosf((-px - py + pz) * 5.0f);

  /* n > 0 */
  x *= distortion;
  y *= distortion;
  z *= distortion;
  y = -cosf(x - y + z);
  y *= distortion;
  /* n > 1 */
  x = cosf(x - y - z);
  x *= distortion;

  /* distortion != 0 */
  distortion *= 2.0f;
  x /= distortion;
  y /= distortion;
  z /= distortion;

  return make_float3(0.5f - x, 0.5f - y, 0.5f - z);
}

/* svm_wave() (kernel/svm/wave.h:15-77) with distortion 0, which skips wave.h:63-65. */
float wave_reference(const NodeWaveType type,
                     const NodeWaveBandsDirection bands_dir,
                     const NodeWaveRingsDirection rings_dir,
                     const NodeWaveProfile profile,
                     const float3 p_in,
                     const float phase_in)
{
  float3 p = opaque3(p_in);
  const float phase = opaque(phase_in);

  p = (p + 0.000001f) * 0.999999f;

  float n;
  if (type == NODE_WAVE_BANDS) {
    if (bands_dir == NODE_WAVE_BANDS_DIRECTION_X) {
      n = p.x * 20.0f;
    }
    else if (bands_dir == NODE_WAVE_BANDS_DIRECTION_Y) {
      n = p.y * 20.0f;
    }
    else if (bands_dir == NODE_WAVE_BANDS_DIRECTION_Z) {
      n = p.z * 20.0f;
    }
    else {
      n = (p.x + p.y + p.z) * 10.0f;
    }
  }
  else {
    float3 rp = p;
    if (rings_dir == NODE_WAVE_RINGS_DIRECTION_X) {
      rp *= make_float3(0.0f, 1.0f, 1.0f);
    }
    else if (rings_dir == NODE_WAVE_RINGS_DIRECTION_Y) {
      rp *= make_float3(1.0f, 0.0f, 1.0f);
    }
    else if (rings_dir == NODE_WAVE_RINGS_DIRECTION_Z) {
      rp *= make_float3(1.0f, 1.0f, 0.0f);
    }
    n = len(rp) * 20.0f;
  }

  n += phase;

  if (profile == NODE_WAVE_PROFILE_SIN) {
    return 0.5f + 0.5f * sinf(n - M_PI_2_F);
  }
  if (profile == NODE_WAVE_PROFILE_SAW) {
    n /= M_2PI_F;
    return n - floorf(n);
  }
  n /= M_2PI_F;
  return fabsf(n - floorf(n + 0.5f)) * 2.0f;
}

/* brick_noise() (kernel/svm/brick.h:14-21). */
float brick_noise_reference(uint n)
{
  n = (n + 1013) & 0x7fffffff;
  n = (n >> 13) ^ n;
  const uint nn = (n * (n * n * 60493 + 19990303) + 1376312589) & 0x7fffffff;
  return 0.5f * ((float)nn / 1073741824.0f);
}

/* A brick's color in svm_node_tex_brick() (kernel/svm/brick.h:100-107) when the point is not in
 * the mortar (f = 0): (1 - tint) * color1 + tint * color2, then times (1 - 0) plus mortar times
 * 0, which changes nothing. */
float3 brick_color_reference(const uint noise_input,
                             const float bias,
                             const float3 color1,
                             const float3 color2)
{
  const float tint = saturatef(brick_noise_reference(noise_input) + bias);
  const float facm = 1.0f - tint;
  return make_float3(facm * color1.x + tint * color2.x,
                     facm * color1.y + tint * color2.y,
                     facm * color1.z + tint * color2.z);
}

/* grad3() of kernel/svm/noise.h:142-149. */
float grad3_reference(const int hash, const float x, const float y, const float z)
{
  const int h = hash & 15;
  const float u = h < 8 ? x : y;
  const float vt = ((h == 12) || (h == 14)) ? x : z;
  const float v = h < 4 ? y : vt;
  return ((h & 1) ? -u : u) + ((h & 2) ? -v : v);
}

/* grad1() of kernel/svm/noise.h:28-33. */
float grad1_reference(const int hash, const float x)
{
  const int h = hash & 15;
  const float g = 1 + (h & 7);
  return ((h & 8) ? -g : g) * x;
}

/* perlin_3d() (kernel/svm/noise.h:181-207) at (X + 0.5, Y + 0.5, Z + 0.5). There fade() is
 * exactly 0.5, every corner gradient is a sum of two of +-0.5, and each corner weighs 1/8, so the
 * result is a multiple of 1/8 and exact in any order of operations, including the SSE order of
 * noise.h:433-454 that the kernel compiles. */
float perlin_3d_half_integer_reference(const int X, const int Y, const int Z)
{
  float sum = 0.0f;
  for (int dz = 0; dz <= 1; dz++) {
    for (int dy = 0; dy <= 1; dy++) {
      for (int dx = 0; dx <= 1; dx++) {
        const uint hash = hash_uint3(uint(X + dx), uint(Y + dy), uint(Z + dz));
        sum += grad3_reference(int(hash), 0.5f - dx, 0.5f - dy, 0.5f - dz);
      }
    }
  }
  return sum * 0.125f;
}

/* perlin_1d() (kernel/svm/noise.h:35-42) at X + 0.5: fade() is 0.5, so the mix is the mean of
 * the two gradients, exact in any order. */
float perlin_1d_half_integer_reference(const int X)
{
  return (grad1_reference(int(hash_uint(uint(X))), 0.5f) +
          grad1_reference(int(hash_uint(uint(X + 1))), -0.5f)) *
         0.5f;
}

/* voronoi_f1() (kernel/svm/voronoi.h:479-510) with the Chebychev metric (voronoi.h:57-95), as
 * fractal_voronoi_x_fx() (voronoi.h:939-992) runs it for detail 0 and scale 1: one octave, the
 * position divided by 1. Only per-component operations and max occur, so the result is the same
 * in any order. The search visits the cells in upstream's order and keeps the first minimum. */
struct VoronoiReference {
  float distance;
  float3 color;
  float3 position;
};

VoronoiReference voronoi_f1_chebychev_reference(const float3 coord_in, const float randomness)
{
  const float3 coord = opaque3(coord_in);
  const float3 cell_position_f = floor(coord);
  const float3 local_position = coord - cell_position_f;
  const int3 cell_position = make_int3(cell_position_f);

  float min_distance = FLT_MAX;
  int3 target_offset = make_int3(0);
  float3 target_position = make_float3(0.0f, 0.0f, 0.0f);
  for (int k = -1; k <= 1; k++) {
    for (int j = -1; j <= 1; j++) {
      for (int i = -1; i <= 1; i++) {
        const int3 cell_offset = make_int3(i, j, k);
        const float3 point_position = make_float3(cell_offset) +
                                      hash_int3_to_float3(cell_position + cell_offset) *
                                          randomness;
        const float distance_to_point = reduce_max(fabs(point_position - local_position));
        if (distance_to_point < min_distance) {
          target_offset = cell_offset;
          min_distance = distance_to_point;
          target_position = point_position;
        }
      }
    }
  }

  VoronoiReference result;
  result.distance = reduce_max(fabs(target_position - local_position));
  result.color = hash_int3_to_float3(cell_position + target_offset);
  result.position = target_position + cell_position_f;
  return result;
}

SVMNodeAttr attr_node(const AttributeStandard attr, const SVMStackOffset out_offset)
{
  return SVMNodeAttr{.attr = attr,
                     .out_offset = out_offset,
                     .output_type = NODE_ATTR_OUTPUT_FLOAT3,
                     .bump_offset = NODE_BUMP_OFFSET_CENTER,
                     .store_derivatives = 0,
                     .bump_filter_width = 0.0f};
}

SVMNodeTexCoord tex_coord_node(const NodeTexCoord type, const SVMStackOffset out_offset)
{
  return SVMNodeTexCoord{.texco_type = type,
                         .bump_offset = NODE_BUMP_OFFSET_CENTER,
                         .store_derivatives = 0,
                         .out_offset = out_offset,
                         .bump_filter_width = 0.0f};
}

SVMNodeGeometry geometry_node(const NodeGeometry type, const SVMStackOffset out_offset)
{
  return SVMNodeGeometry{.geom_type = type,
                         .bump_offset = NODE_BUMP_OFFSET_CENTER,
                         .store_derivatives = 0,
                         .out_offset = out_offset,
                         .bump_filter_width = 0.0f};
}

}  // namespace

TEST_CASE("cycles svm textures: TexCoord outputs of an identity object")
{
  KernelGlobalsCPU globals;
  const PainterlySvmTestScene scene;
  scene.bind(globals);
  PainterlySvmTestProgram program = new_program();

  program.add_node(NODE_ATTR, attr_node(ATTR_STD_GENERATED, 20));
  program.add_node(NODE_ATTR, attr_node(ATTR_STD_UV, 23));
  program.add_node(NODE_TEX_COORD, tex_coord_node(NODE_TEXCO_NORMAL, 26));
  program.add_node(NODE_TEX_COORD, tex_coord_node(NODE_TEXCO_OBJECT, 29));
  program.add_node(NODE_TEX_COORD, tex_coord_node(NODE_TEXCO_OBJECT_WITH_TRANSFORM, 32));
  /* The PackedTransform after the node (kernel/svm/tex_coord.h:108; TextureCoordinateNode::compile
   * appends it with add_node_data, scene/shader_nodes.cpp:4196-4199): rows x, y, z. */
  program.expect_fetches(program.size(), 1);
  program.add_data_float4(make_float4(1.0f, 0.0f, 0.0f, -0.5f));
  program.add_data_float4(make_float4(0.0f, 1.0f, 0.0f, -0.25f));
  program.add_data_float4(make_float4(0.0f, 0.0f, 1.0f, -0.125f));
  program.add_node(NODE_TEX_COORD, tex_coord_node(NODE_TEXCO_CAMERA, 35));
  program.add_node(NODE_TEX_COORD, tex_coord_node(NODE_TEXCO_WINDOW, 38));
  program.add_node(NODE_TEX_COORD, tex_coord_node(NODE_TEXCO_REFLECTION, 41));

  /* Triangle 1 has vertices (3, 1, 2): (1 - u - v) G3 + u G1 + v G2 with (u, v) = (0.25, 0.5). */
  program.check_equal3(20, make_float3(0.25f, 0.5f, 0.25f), "Generated");
  /* Corners 3, 4, 5: 0.25 (0.5, 0.5) + 0.25 (1, 0.5) + 0.5 (0.5, 1), and z = 0. */
  program.check_equal3(23, make_float3(0.625f, 0.75f, 0.0f), "UV");
  /* N through the transposed identity, normalized: unchanged. */
  program.check_equal3(26, make_float3(0.0f, 0.0f, 1.0f), "Normal");
  /* P through the identity inverse transform. */
  program.check_equal3(29, make_float3(1.5f, 2.25f, 4.125f), "Object");
  /* P through the node's own transform. */
  program.check_equal3(32, make_float3(1.0f, 2.0f, 4.0f), "Object with transform");
  /* P through worldtocamera, a translation by (0, 0, -8). */
  program.check_equal3(35, make_float3(1.5f, 2.25f, -3.875f), "Camera");
  /* worldtondc maps x and y to 0.5 x + 0.5 with w = 1; z is set to 0 (tex_coord.h:142-146). */
  program.check_equal3(38, make_float3(1.25f, 1.625f, 0.0f), "Window");
  /* -reflect(wi, N) = -(wi - 2 N dot(wi, N)) = -((0.5, 0, 0.5) - (0, 0, 1)). */
  program.check_equal3(41, make_float3(-0.5f, 0.0f, 0.5f), "Reflection");

  ShaderData sd = scene.surface(0, 1);
  /* Generated 6: attributes_map and objects (find_attribute), tri_vindex, three attributes_float3.
   * UV 5: attributes_map, objects, three attributes_float2. Normal 1 and Object 1: objects. */
  run_and_check(globals, program, sd, 13);
}

TEST_CASE("cycles svm textures: TexCoord of a translated object without attributes")
{
  KernelGlobalsCPU globals;
  const PainterlySvmTestScene scene;
  scene.bind(globals);
  PainterlySvmTestProgram program = new_program();

  program.add_node(NODE_ATTR, attr_node(ATTR_STD_GENERATED, 20));
  program.add_node(NODE_TEX_COORD, tex_coord_node(NODE_TEXCO_OBJECT, 23));

  /* No Generated attribute: P through itfm (kernel/svm/attribute.h:86-90), P - (1, 2, 4). */
  program.check_equal3(20, make_float3(0.5f, 0.25f, 0.125f), "Generated fallback");
  program.check_equal3(23, make_float3(0.5f, 0.25f, 0.125f), "Object");

  ShaderData sd = scene.surface(1, 0);
  /* Generated 3: attributes_map and objects (find_attribute finds the terminator), objects
   * (itfm). Object 1: objects. */
  run_and_check(globals, program, sd, 4);
}

TEST_CASE("cycles svm textures: Geometry for the background")
{
  KernelGlobalsCPU globals;
  const PainterlySvmTestScene scene;
  scene.bind(globals);
  PainterlySvmTestProgram program = new_program();

  /* TextureCoordinateNode::compile emits these for Generated and Reflection when
   * compiler.background is set (scene/shader_nodes.cpp:4085-4095, 4233-4243). */
  program.add_node(NODE_GEOMETRY, geometry_node(NODE_GEOM_P, 20));
  program.add_node(NODE_GEOMETRY, geometry_node(NODE_GEOM_I, 23));

  program.check_equal3(20, make_float3(1.5f, 2.25f, 4.125f), "P");
  program.check_equal3(23, make_float3(0.5f, 0.0f, 0.5f), "I");

  ShaderData sd = scene.background();
  run_and_check(globals, program, sd, 0);
}

TEST_CASE("cycles svm textures: derivative variants store the value without derivatives")
{
  KernelGlobalsCPU globals;
  const PainterlySvmTestScene scene;
  scene.bind(globals);
  PainterlySvmTestProgram program = new_program();

  /* add_node(..., use_derivatives = true) emits these (scene/svm.cpp:440-453). With zero ray
   * differentials and store_derivatives = 0 they store the same values as the plain cases. */
  program.add_node(NODE_GEOMETRY_DERIVATIVE, geometry_node(NODE_GEOM_P, 20));
  program.add_node(NODE_TEX_COORD_DERIVATIVE, tex_coord_node(NODE_TEXCO_NORMAL, 23));
  program.add_node(NODE_ATTR_DERIVATIVE, attr_node(ATTR_STD_GENERATED, 26));

  program.check_equal3(20, make_float3(1.5f, 2.25f, 4.125f), "P");
  /* safe_normalize of a unit axis with zero derivatives (tex_coord.h:208-210). */
  program.check_equal3(23, make_float3(0.0f, 0.0f, 1.0f), "Normal");
  program.check_equal3(26, make_float3(0.25f, 0.5f, 0.25f), "Generated");

  ShaderData sd = scene.surface(0, 1);
  /* Normal 1, Generated 6 (as in the identity-object test case). */
  run_and_check(globals, program, sd, 7);
}

TEST_CASE("cycles svm textures: gradient")
{
  KernelGlobalsCPU globals;
  PainterlySvmTestProgram program = new_program();
  const float3 co = make_float3(0.25f, 0.5f, 0.75f);
  add_vector(program, 10, co);
  const NodeGradientType types[] = {NODE_BLEND_LINEAR,
                                    NODE_BLEND_QUADRATIC,
                                    NODE_BLEND_EASING,
                                    NODE_BLEND_DIAGONAL,
                                    NODE_BLEND_RADIAL,
                                    NODE_BLEND_QUADRATIC_SPHERE,
                                    NODE_BLEND_SPHERICAL};
  for (int i = 0; i < 7; i++) {
    program.add_node(
        NODE_TEX_GRADIENT,
        SVMNodeTexGradient{.gradient_type = types[i],
                           .co = 10,
                           .fac_offset = SVMStackOffset(20 + i),
                           .color_offset = (i == 0) ? SVMStackOffset(30) : SVM_STACK_INVALID});
  }

  program.check_equal(20, 0.25f, "linear: x");
  program.check_equal(21, 0.0625f, "quadratic: x^2");
  program.check_equal(22, 0.15625f, "easing: 3 x^2 - 2 x^3 = 0.1875 - 0.03125");
  program.check_equal(23, 0.375f, "diagonal: (x + y) / 2");
  program.check_equal(24, gradient_reference(co, NODE_BLEND_RADIAL), "radial");
  program.check_equal(25, gradient_reference(co, NODE_BLEND_QUADRATIC_SPHERE), "quadratic sphere");
  program.check_equal(26, gradient_reference(co, NODE_BLEND_SPHERICAL), "spherical");
  program.check_equal3(30, make_float3(0.25f, 0.25f, 0.25f), "linear color");

  ShaderData sd = painterly_svm_test_shader_data(0);
  run_and_check(globals, program, sd, 0);
}

TEST_CASE("cycles svm textures: checker")
{
  KernelGlobalsCPU globals;
  PainterlySvmTestProgram program = new_program();
  const SVMNodeTexChecker checker{.color1 = c3(0.25f, 0.5f, 1.0f),
                                  .color2 = c3(1.0f, 0.5f, 0.25f),
                                  .scale = c(2.0f),
                                  .co = 10,
                                  .color_offset = 20,
                                  .fac_offset = 23};
  add_vector(program, 10, make_float3(0.25f, 1.25f, 2.25f));
  program.add_node(NODE_TEX_CHECKER, checker);
  add_vector(program, 10, make_float3(0.75f, 1.25f, 2.25f));
  SVMNodeTexChecker second = checker;
  second.color_offset = 24;
  second.fac_offset = 27;
  program.add_node(NODE_TEX_CHECKER, second);

  /* Scaled to (0.5, 2.5, 4.5): cells 0, 2, 4. (0 % 2 == 2 % 2) is 1, which differs from 4 % 2 = 0
   * (kernel/svm/checker.h:14-26): Color2, Fac 0. */
  program.check_equal3(20, make_float3(1.0f, 0.5f, 0.25f), "first color");
  program.check_equal(23, 0.0f, "first fac");
  /* Scaled to (1.5, 2.5, 4.5): cells 1, 2, 4. (1 == 0) is 0, which equals 4 % 2: Color1, Fac 1. */
  program.check_equal3(24, make_float3(0.25f, 0.5f, 1.0f), "second color");
  program.check_equal(27, 1.0f, "second fac");

  ShaderData sd = painterly_svm_test_shader_data(0);
  run_and_check(globals, program, sd, 0);
}

TEST_CASE("cycles svm textures: brick")
{
  KernelGlobalsCPU globals;
  PainterlySvmTestProgram program = new_program();
  const float3 color1 = make_float3(0.25f, 0.5f, 1.0f);
  const float3 color2 = make_float3(1.0f, 0.5f, 0.25f);
  SVMNodeTexBrick brick{.color1 = c3(color1.x, color1.y, color1.z),
                        .color2 = c3(color2.x, color2.y, color2.z),
                        .mortar = c3(0.0f, 0.125f, 0.25f),
                        .scale = c(1.0f),
                        .mortar_size = c(0.0625f),
                        .bias = c(0.0f),
                        .brick_width = c(0.5f),
                        .row_height = c(0.25f),
                        .mortar_smooth = c(0.0f),
                        .offset_amount = 0.5f,
                        .squash_amount = 1.0f,
                        .offset_frequency = 2,
                        .squash_frequency = 2,
                        .co = 10,
                        .color_offset = 20,
                        .fac_offset = 23};
  add_vector(program, 10, make_float3(0.375f, 0.375f, 0.0f));
  program.add_node(NODE_TEX_BRICK, brick);
  add_vector(program, 10, make_float3(0.375f, 0.125f, 0.0f));
  brick.color_offset = 24;
  brick.fac_offset = 27;
  program.add_node(NODE_TEX_BRICK, brick);
  add_vector(program, 10, make_float3(0.03125f, 0.375f, 0.0f));
  brick.color_offset = 28;
  brick.fac_offset = 31;
  program.add_node(NODE_TEX_BRICK, brick);

  /* svm_brick() (kernel/svm/brick.h:23-68). Row 1 (odd: no offset), brick 0, local
   * (x, y) = (0.375, 0.125): distance to the mortar 0.125 >= 0.0625. */
  program.check_equal3(
      20, brick_color_reference((1 << 16) + 0, 0.0f, color1, color2), "row 1 brick 0 color");
  program.check_equal(23, 0.0f, "row 1 brick 0 fac");
  /* Row 0 (even: offset 0.5 * 0.5 = 0.25), brick floor((0.375 + 0.25) / 0.5) = 1, local
   * (0.125, 0.125). */
  program.check_equal3(
      24, brick_color_reference((0 << 16) + 1, 0.0f, color1, color2), "row 0 brick 1 color");
  program.check_equal(27, 0.0f, "row 0 brick 1 fac");
  /* Row 1, brick 0, local x = 0.03125 < 0.0625 and Mortar Smooth 0: mortar 1, so the color is
   * the Mortar input exactly. */
  program.check_equal3(28, make_float3(0.0f, 0.125f, 0.25f), "mortar color");
  program.check_equal(31, 1.0f, "mortar fac");

  ShaderData sd = painterly_svm_test_shader_data(0);
  run_and_check(globals, program, sd, 0);
}

TEST_CASE("cycles svm textures: magic")
{
  KernelGlobalsCPU globals;
  PainterlySvmTestProgram program = new_program();
  add_vector(program, 10, make_float3(0.0f, 0.0f, 0.0f));
  program.add_node(NODE_TEX_MAGIC,
                   SVMNodeTexMagic{.scale = c(5.0f),
                                   .distortion = c(1.0f),
                                   .depth = 0,
                                   .co = 10,
                                   .color_offset = 20,
                                   .fac_offset = 23});
  const float3 p = make_float3(0.25f, 0.5f, 0.125f);
  add_vector(program, 10, p);
  program.add_node(NODE_TEX_MAGIC,
                   SVMNodeTexMagic{.scale = c(2.0f),
                                   .distortion = c(0.5f),
                                   .depth = 2,
                                   .co = 10,
                                   .color_offset = 24,
                                   .fac_offset = 27});

  /* At the origin with depth 0: (sin 0, cos 0, -cos 0) = (0, 1, -1), divided by 2 * distortion
   * = 2, subtracted from 0.5 (kernel/svm/magic.h:35-37, 92-99). Fac = (0.5 + 0 + 1) / 3, which
   * rounds to 0.5 in float. */
  program.check_equal3(20, make_float3(0.5f, 0.0f, 1.0f), "depth 0 color");
  program.check_equal(23, 0.5f, "depth 0 fac");
  const float3 color = magic_depth2_reference(p, 2.0f, 0.5f);
  program.check_equal3(24, color, "depth 2 color");
  program.check_equal(27, average(color), "depth 2 fac");

  ShaderData sd = painterly_svm_test_shader_data(0);
  run_and_check(globals, program, sd, 0);
}

TEST_CASE("cycles svm textures: wave")
{
  KernelGlobalsCPU globals;
  PainterlySvmTestProgram program = new_program();
  const SVMNodeTexWave wave{.wave_type = NODE_WAVE_BANDS,
                            .bands_direction = NODE_WAVE_BANDS_DIRECTION_X,
                            .rings_direction = NODE_WAVE_RINGS_DIRECTION_X,
                            .profile = NODE_WAVE_PROFILE_SIN,
                            .scale = c(1.0f),
                            .distortion = c(0.0f),
                            .detail = c(2.0f),
                            .dscale = c(0.0f),
                            .droughness = c(0.5f),
                            .phase = c(0.0f),
                            .co = 10,
                            .color_offset = 20,
                            .fac_offset = 23};
  add_vector(program, 10, make_float3(0.25f, 0.0f, 0.0f));
  program.add_node(NODE_TEX_WAVE, wave);
  add_vector(program, 10, make_float3(0.5f, 0.25f, 0.375f));
  SVMNodeTexWave rings = wave;
  rings.wave_type = NODE_WAVE_RINGS;
  rings.profile = NODE_WAVE_PROFILE_SAW;
  rings.scale = c(2.0f);
  rings.phase = c(0.5f);
  rings.color_offset = SVM_STACK_INVALID;
  rings.fac_offset = 24;
  program.add_node(NODE_TEX_WAVE, rings);
  SVMNodeTexWave diagonal = wave;
  diagonal.bands_direction = NODE_WAVE_BANDS_DIRECTION_DIAGONAL;
  diagonal.profile = NODE_WAVE_PROFILE_TRI;
  diagonal.phase = c(0.25f);
  diagonal.color_offset = SVM_STACK_INVALID;
  diagonal.fac_offset = 25;
  program.add_node(NODE_TEX_WAVE, diagonal);

  /* The kernel scales co before svm_wave() (kernel/svm/wave.h:94); these products are exact. */
  const float bands = wave_reference(NODE_WAVE_BANDS,
                                     NODE_WAVE_BANDS_DIRECTION_X,
                                     NODE_WAVE_RINGS_DIRECTION_X,
                                     NODE_WAVE_PROFILE_SIN,
                                     make_float3(0.25f, 0.0f, 0.0f),
                                     0.0f);
  program.check_equal(23, bands, "bands x sine fac");
  program.check_equal3(20, make_float3(bands, bands, bands), "bands x sine color");
  program.check_equal(24,
                      wave_reference(NODE_WAVE_RINGS,
                                     NODE_WAVE_BANDS_DIRECTION_X,
                                     NODE_WAVE_RINGS_DIRECTION_X,
                                     NODE_WAVE_PROFILE_SAW,
                                     make_float3(1.0f, 0.5f, 0.75f),
                                     0.5f),
                      "rings x saw fac");
  program.check_equal(25,
                      wave_reference(NODE_WAVE_BANDS,
                                     NODE_WAVE_BANDS_DIRECTION_DIAGONAL,
                                     NODE_WAVE_RINGS_DIRECTION_X,
                                     NODE_WAVE_PROFILE_TRI,
                                     make_float3(0.5f, 0.25f, 0.375f),
                                     0.25f),
                      "bands diagonal triangle fac");

  ShaderData sd = painterly_svm_test_shader_data(0);
  run_and_check(globals, program, sd, 0);
}

TEST_CASE("cycles svm textures: noise")
{
  KernelGlobalsCPU globals;
  PainterlySvmTestProgram program = new_program();
  /* Scale 2 maps it to (1.5, 1.5, 1.5), the centre of cell (1, 1, 1). */
  add_vector(program, 10, make_float3(0.75f, 0.75f, 0.75f));
  const SVMNodeTexNoise noise{.dimensions = 3,
                              .noise_type = NODE_NOISE_FBM,
                              .normalize = 1,
                              .w = c(0.0f),
                              .scale = c(2.0f),
                              .detail = c(0.0f),
                              .roughness = c(0.5f),
                              .lacunarity = c(2.0f),
                              .offset = c(0.0f),
                              .gain = c(1.0f),
                              .distortion = c(0.0f),
                              .vector = 10,
                              .value_offset = 20,
                              .color_offset = SVM_STACK_INVALID};
  program.add_node(NODE_TEX_NOISE, noise);
  SVMNodeTexNoise two_octaves = noise;
  two_octaves.detail = c(1.0f);
  two_octaves.value_offset = 21;
  program.add_node(NODE_TEX_NOISE, two_octaves);
  SVMNodeTexNoise raw = noise;
  raw.normalize = 0;
  raw.value_offset = 22;
  program.add_node(NODE_TEX_NOISE, raw);
  SVMNodeTexNoise one_d = noise;
  one_d.dimensions = 1;
  one_d.w = c(0.25f);
  one_d.value_offset = 23;
  program.add_node(NODE_TEX_NOISE, one_d);

  /* snoise_3d() = noise_scale3(perlin_3d()) = 0.9820f * perlin (kernel/svm/noise.h:679-682,
   * 725-736). */
  const float t3 = 0.9820f * perlin_3d_half_integer_reference(1, 1, 1);
  /* noise_fbm() (kernel/svm/fractal_noise.h:63-86), one octave: sum = t3, maxamp = 1. */
  program.check_equal(20, 0.5f * t3 / 1.0f + 0.5f, "3D fBM detail 0");
  /* Two octaves: the second samples (3, 3, 3), a lattice point, where Perlin noise is 0, so
   * sum = t3 and maxamp = 1 + 0.5. */
  program.check_equal(21, 0.5f * t3 / 1.5f + 0.5f, "3D fBM detail 1");
  program.check_equal(22, t3, "3D fBM detail 0 not normalized");
  /* 1D at w * scale = 0.5: snoise_1d() = 0.25 * perlin (noise.h:669-672, 691-700). */
  const float t1 = 0.25f * perlin_1d_half_integer_reference(0);
  program.check_equal(23, 0.5f * t1 / 1.0f + 0.5f, "1D fBM detail 0");

  ShaderData sd = painterly_svm_test_shader_data(0);
  run_and_check(globals, program, sd, 0);
}

TEST_CASE("cycles svm textures: voronoi")
{
  KernelGlobalsCPU globals;
  PainterlySvmTestProgram program = new_program();
  add_vector(program, 10, make_float3(0.3125f, 0.3125f, 0.3125f));
  const SVMNodeTexVoronoi euclidean{.dimensions = 3,
                                    .feature = NODE_VORONOI_F1,
                                    .metric = NODE_VORONOI_EUCLIDEAN,
                                    .w = c(0.0f),
                                    .scale = c(4.0f),
                                    .detail = c(0.0f),
                                    .roughness = c(0.5f),
                                    .lacunarity = c(2.0f),
                                    .smoothness = c(5.0f),
                                    .exponent = c(0.5f),
                                    .randomness = c(0.0f),
                                    .normalize = 0,
                                    .coord = 10,
                                    .distance_offset = 20,
                                    .color_offset = 21,
                                    .position_offset = 24,
                                    .w_out_offset = 27,
                                    .radius_offset = 28};
  program.add_node(NODE_TEX_VORONOI, euclidean);
  const float3 coord = make_float3(0.75f, 1.25f, 2.5f);
  add_vector(program, 10, coord);
  SVMNodeTexVoronoi chebychev = euclidean;
  chebychev.metric = NODE_VORONOI_CHEBYCHEV;
  chebychev.scale = c(1.0f);
  chebychev.randomness = c(1.0f);
  chebychev.distance_offset = 30;
  chebychev.color_offset = 31;
  chebychev.position_offset = 34;
  chebychev.w_out_offset = 37;
  chebychev.radius_offset = 38;
  program.add_node(NODE_TEX_VORONOI, chebychev);

  /* Randomness 0 puts every feature point on its cell corner (kernel/svm/voronoi.h:492-494).
   * Scale 4 gives (1.25, 1.25, 1.25): cell (1, 1, 1), local (0.25, 0.25, 0.25), nearest corner
   * (0, 0, 0) at squared distance 0.1875. */
  program.check_equal(20, sqrtf(opaque(0.1875f)), "euclidean distance");
  program.check_equal3(21, hash_int3_to_float3(make_int3(1, 1, 1)), "euclidean color");
  /* The corner (1, 1, 1) divided by the scale (voronoi.h:989). */
  program.check_equal3(24, make_float3(0.25f, 0.25f, 0.25f), "euclidean position");
  /* W is the w of make_float4(position), which is 1, divided by the scale
   * (voronoi.h:474-477; util/types_float4.h:89-92). */
  program.check_equal(27, 0.25f, "euclidean w");
  program.check_equal(28, 0.0f, "euclidean radius");

  const VoronoiReference cell = voronoi_f1_chebychev_reference(coord, 1.0f);
  program.check_equal(30, cell.distance, "chebychev distance");
  program.check_equal3(31, cell.color, "chebychev color");
  program.check_equal3(34, cell.position, "chebychev position");
  program.check_equal(37, 1.0f, "chebychev w");
  program.check_equal(38, 0.0f, "chebychev radius");

  ShaderData sd = painterly_svm_test_shader_data(0);
  run_and_check(globals, program, sd, 0);
}

TEST_CASE("cycles svm textures: white noise")
{
  KernelGlobalsCPU globals;
  PainterlySvmTestProgram program = new_program();
  const float3 vector = make_float3(0.25f, 0.5f, 0.75f);
  program.add_node(NODE_TEX_WHITE_NOISE,
                   SVMNodeTexWhiteNoise{.dimensions = 3,
                                        .vector = c3(vector.x, vector.y, vector.z),
                                        .w = c(0.0f),
                                        .value_offset = 20,
                                        .color_offset = 21});
  program.add_node(NODE_TEX_WHITE_NOISE,
                   SVMNodeTexWhiteNoise{.dimensions = 1,
                                        .vector = c3(0.0f, 0.0f, 0.0f),
                                        .w = c(0.5f),
                                        .value_offset = 24,
                                        .color_offset = 25});

  /* kernel/svm/white_noise.h:13-65: a hash of the input's bits. */
  program.check_equal(20, hash_float3_to_float(vector), "3D value");
  program.check_equal3(21, hash_float3_to_float3(vector), "3D color");
  program.check_equal(24, hash_float_to_float(0.5f), "1D value");
  program.check_equal3(25, hash_float_to_float3(0.5f), "1D color");

  ShaderData sd = painterly_svm_test_shader_data(0);
  run_and_check(globals, program, sd, 0);
}

CCL_NAMESPACE_END
