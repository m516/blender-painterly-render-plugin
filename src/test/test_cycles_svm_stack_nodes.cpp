/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "cycles_svm_test_support.h"

#include "kernel/svm/ramp_util.h"

#include <cmath>
#include <iterator>
#include <string>
#include <vector>

#include <doctest/doctest.h>

CCL_NAMESPACE_BEGIN

static SVMInputFloat c(const float x)
{
  return painterly_svm_input_constant(x);
}
static SVMInputFloat3 c3(const float x, const float y, const float z)
{
  return painterly_svm_input_constant3(x, y, z);
}
static SVMInputFloat s(const SVMStackOffset n)
{
  return painterly_svm_input_stack(n);
}
static float3 f3(const float x, const float y, const float z)
{
  return make_float3(x, y, z);
}
static float4 f4(const float x, const float y, const float z, const float w)
{
  return make_float4(x, y, z, w);
}

/* Appends NODE_END, runs the program and makes the three checks of every test case below: the
 * fetch trace equals the expected trace, no other kernel array was read, and no in-VM check
 * failed. */
static void run_program_and_check(KernelGlobalsCPU &globals, PainterlySvmTestProgram &program)
{
  program.add_node(NODE_END);
  const PainterlySvmTrace trace = painterly_svm_test_run(globals, program);
  CHECK(program.fetched_trace(trace.svm_nodes) == program.expected_trace(0));
  CHECK(trace.other_arrays == 0);
  CHECK(program.failed_checks(trace.svm_nodes) == "");
}

/* The jump entry at words 0-3 points at word 4 (NODE_END); the first node added goes to word 5. */
static PainterlySvmTestProgram new_program()
{
  PainterlySvmTestProgram program;
  const int start = program.size();
  program.set_jump(0, start, start, start);
  return program;
}

/* compatible_powf() ends in `return powf(x, y)` (util/math_base.h:582). This calls the same C
 * library function on the same float bits, so the results are bit-identical. The volatile copies
 * stop the compiler from evaluating powf at compile time, which may round differently. */
static float painterly_test_libm_powf(const float x, const float y)
{
  volatile float vx = x;
  volatile float vy = y;
  return powf(vx, vy);
}

TEST_CASE("cycles svm stack nodes: control flow")
{
  KernelGlobalsCPU globals;

  /* Shader selection: each shader's jump entry points at its own NODE_VALUE_F, and
   * SHADER_MASK drops the ShaderFlag bits. */
  {
    PainterlySvmTestProgram program(2);
    program.add_node(NODE_VALUE_F, SVMNodeValueF{.value = 1.0f, .out_offset = 1});
    program.add_node(NODE_END);
    program.add_node(NODE_VALUE_F, SVMNodeValueF{.value = 2.0f, .out_offset = 1});
    program.add_node(NODE_END);
    program.add_node(NODE_VALUE_F, SVMNodeValueF{.value = 3.0f, .out_offset = 1});
    program.add_node(NODE_END);
    program.set_jump(1, 9, 13, 17);
    CHECK(painterly_svm_test_format(
              painterly_svm_test_run(globals, program, 1, SHADER_SMOOTH_NORMAL).svm_nodes) ==
          "4 5 9 10 12");
    CHECK(painterly_svm_test_format(
              painterly_svm_test_run<SHADER_TYPE_VOLUME>(globals, program, 1, SHADER_SMOOTH_NORMAL)
                  .svm_nodes) == "4 5 13 14 16");
    CHECK(painterly_svm_test_format(painterly_svm_test_run<SHADER_TYPE_DISPLACEMENT>(
                                        globals, program, 1, SHADER_SMOOTH_NORMAL)
                                        .svm_nodes) == "4 5 17 18 20");
    CHECK(painterly_svm_test_format(
              painterly_svm_test_run<SHADER_TYPE_BUMP>(globals, program, 1, SHADER_SMOOTH_NORMAL)
                  .svm_nodes) == "4 5");
    CHECK(painterly_svm_test_format(painterly_svm_test_run(globals, program, 0).svm_nodes) ==
          "0 1 8");
  }

  /* Conditional jumps: NODE_JUMP_IF_ZERO jumps when the stack value is <= 0, NODE_JUMP_IF_ONE when
   * it is >= 1 (svm.h:177-192). */
  struct JumpCase {
    ShaderNodeType type;
    float w;
    const char *expected;
    const char *label;
  };
  static const JumpCase jump_cases[] = {
      {NODE_JUMP_IF_ZERO, 0.0f, "0 1 5 6 8 9 14", "ZERO 0"},
      {NODE_JUMP_IF_ZERO, -1.0f, "0 1 5 6 8 9 14", "ZERO -1"},
      {NODE_JUMP_IF_ZERO, 0.5f, "0 1 5 6 8 9 11 12 14", "ZERO 0.5"},
      {NODE_JUMP_IF_ONE, 1.0f, "0 1 5 6 8 9 14", "ONE 1"},
      {NODE_JUMP_IF_ONE, 2.0f, "0 1 5 6 8 9 14", "ONE 2"},
      {NODE_JUMP_IF_ONE, 0.5f, "0 1 5 6 8 9 11 12 14", "ONE 0.5"},
  };
  for (const JumpCase &entry : jump_cases) {
    CAPTURE(entry.label);
    PainterlySvmTestProgram program;
    program.set_jump(0, 5, 5, 5);
    program.add_node(NODE_VALUE_F, SVMNodeValueF{.value = entry.w, .out_offset = 1});
    if (entry.type == NODE_JUMP_IF_ZERO) {
      program.add_node(NODE_JUMP_IF_ZERO, SVMNodeJumpIfZero{.jump_offset = 3, .stack_offset = 1});
    }
    else {
      program.add_node(NODE_JUMP_IF_ONE, SVMNodeJumpIfOne{.jump_offset = 3, .stack_offset = 1});
    }
    program.add_node(NODE_VALUE_F, SVMNodeValueF{.value = 9.0f, .out_offset = 2});
    program.add_node(NODE_END);
    CHECK(painterly_svm_test_format(painterly_svm_test_run(globals, program).svm_nodes) ==
          entry.expected);
  }
}

/* One dispatch entry per stack node case. Each writes its node's struct, and a table node writes
 * its table data and expects the reads of it. */
struct StackNodeCase {
  ShaderNodeType type;
  const char *name;
};

static void add_dispatch_node(PainterlySvmTestProgram &program, const ShaderNodeType type)
{
  switch (type) {
    case NODE_CONVERT:
    case NODE_CONVERT_DERIVATIVE:
      program.add_node(
          type,
          SVMNodeConvert{.convert_type = NODE_CONVERT_FV, .from_offset = 10, .to_offset = 20});
      break;
    case NODE_VALUE_F:
    case NODE_VALUE_F_DERIVATIVE:
      program.add_node(type, SVMNodeValueF{.value = 0.5f, .out_offset = 20});
      break;
    case NODE_VALUE_V:
    case NODE_VALUE_V_DERIVATIVE:
      program.add_node(type, SVMNodeValueV{.out_offset = 20, .value = f3(1, 2, 4)});
      break;
    case NODE_HSV:
      program.add_node(type,
                       SVMNodeHSV{.color = c3(0.5f, 0.25f, 0.125f),
                                  .hue = c(0.5f),
                                  .sat = c(1),
                                  .val = c(1),
                                  .fac = c(1),
                                  .out_color_offset = 20});
      break;
    case NODE_MATH:
      program.add_node(type,
                       SVMNodeMath{.math_type = NODE_MATH_ADD,
                                   .value1 = c(1.5f),
                                   .value2 = c(2.25f),
                                   .value3 = c(0),
                                   .result_offset = 20});
      break;
    case NODE_VECTOR_MATH:
    case NODE_VECTOR_MATH_DERIVATIVE:
      program.add_node(type,
                       SVMNodeVectorMath{.math_type = NODE_VECTOR_MATH_ADD,
                                         .a = c3(1, 2, 4),
                                         .b = c3(0.5f, 0.25f, 0.125f),
                                         .c = c3(0, 0, 0),
                                         .param1 = c(1),
                                         .value_offset = 20,
                                         .vector_offset = 30});
      break;
    case NODE_RGB_RAMP: {
      program.add_node(type,
                       SVMNodeRGBRamp{.table_size = 2,
                                      .fac = c(0),
                                      .interpolate = 1,
                                      .color_offset = 20,
                                      .alpha_offset = 23});
      const int table = program.size();
      program.add_data_float4(f4(0, 0, 0, 1));
      program.add_data_float4(f4(1, 1, 1, 0));
      program.expect_fetches(table, 4);
      break;
    }
    case NODE_GAMMA:
      program.add_node(type,
                       SVMNodeGamma{.color = c3(0.25f, 0.5f, 1), .gamma = c(2), .out_offset = 20});
      break;
    case NODE_BRIGHTCONTRAST:
      program.add_node(type,
                       SVMNodeBrightContrast{.color = c3(0.25f, 0.5f, 1),
                                             .bright = c(0.25f),
                                             .contrast = c(0.5f),
                                             .out_offset = 20});
      break;
    case NODE_TEXTURE_MAPPING:
    case NODE_TEXTURE_MAPPING_DERIVATIVE:
      program.add_node(type,
                       SVMNodeTextureMapping{.vec_offset = 10,
                                             .out_offset = 20,
                                             .tfm = transform_translate(1, 2, 4)});
      break;
    case NODE_MAPPING:
    case NODE_MAPPING_DERIVATIVE:
      program.add_node(type,
                       SVMNodeMapping{.mapping_type = NODE_MAPPING_TYPE_POINT,
                                      .vector = c3(1, 2, 4),
                                      .location = c3(0.5f, 0.5f, 0.5f),
                                      .rotation = c3(0, 0, 0),
                                      .scale = c3(1, 1, 1),
                                      .result_offset = 20});
      break;
    case NODE_MIN_MAX:
      program.add_node(
          type,
          SVMNodeMinMax{
              .vec_offset = 10, .out_offset = 20, .mn = f3(0, 0, 0), .mx = f3(0.5f, 0.5f, 0.5f)});
      break;
    case NODE_CURVES: {
      program.add_node(type,
                       SVMNodeCurves{.color = c3(0, 0, 0),
                                     .fac = c(1),
                                     .min_x = 0,
                                     .max_x = 1,
                                     .table_size = 2,
                                     .extrapolate = 1,
                                     .out_offset = 20});
      const int table = program.size();
      program.add_data_float4(f4(0, 0, 0, 0));
      program.add_data_float4(f4(1, 1, 1, 1));
      program.expect_fetches(table, 4);
      program.expect_fetches(table, 4);
      program.expect_fetches(table, 4);
      break;
    }
    case NODE_INVERT:
      program.add_node(type,
                       SVMNodeInvert{.color = c3(0.25f, 0.5f, 1), .fac = c(1), .out_offset = 20});
      break;
    case NODE_MIX:
      program.add_node(type,
                       SVMNodeMix{.mix_type = NODE_MIX_BLEND,
                                  .c1 = c3(0, 1, 2),
                                  .c2 = c3(4, 5, 10),
                                  .fac = c(0.25f),
                                  .result_offset = 20});
      break;
    case NODE_SEPARATE_COLOR:
      program.add_node(type,
                       SVMNodeSeparateColor{.color_type = NODE_COMBSEP_COLOR_RGB,
                                            .color = c3(0.25f, 0.5f, 1),
                                            .red_offset = 20,
                                            .green_offset = 21,
                                            .blue_offset = 22});
      break;
    case NODE_COMBINE_COLOR:
      program.add_node(type,
                       SVMNodeCombineColor{.color_type = NODE_COMBSEP_COLOR_RGB,
                                           .red = c(0.25f),
                                           .green = c(0.5f),
                                           .blue = c(1),
                                           .color_offset = 20});
      break;
    case NODE_SEPARATE_VECTOR:
    case NODE_SEPARATE_VECTOR_DERIVATIVE:
      program.add_node(type,
                       SVMNodeSeparateVector{
                           .vector = c3(0.25f, 0.5f, 1), .vector_index = 1, .out_offset = 20});
      break;
    case NODE_COMBINE_VECTOR:
    case NODE_COMBINE_VECTOR_DERIVATIVE:
      program.add_node(type,
                       SVMNodeCombineVector{.in = c(0.5f), .vector_index = 1, .out_offset = 20});
      break;
    case NODE_MAP_RANGE:
      program.add_node(type,
                       SVMNodeMapRange{.range_type = NODE_MAP_RANGE_LINEAR,
                                       .value = c(3.5f),
                                       .from_min = c(2),
                                       .from_max = c(6),
                                       .to_min = c(10),
                                       .to_max = c(18),
                                       .steps = c(4),
                                       .result_offset = 20});
      break;
    case NODE_VECTOR_MAP_RANGE:
      program.add_node(type,
                       SVMNodeVectorMapRange{.range_type = NODE_MAP_RANGE_LINEAR,
                                             .use_clamp = 0,
                                             .value = c3(3.5f, 3.5f, 3.5f),
                                             .from_min = c3(2, 2, 2),
                                             .from_max = c3(6, 6, 6),
                                             .to_min = c3(10, 10, 10),
                                             .to_max = c3(18, 18, 18),
                                             .steps = c3(4, 4, 4),
                                             .result_offset = 20});
      break;
    case NODE_CLAMP:
      program.add_node(type,
                       SVMNodeClamp{.clamp_type = NODE_CLAMP_MINMAX,
                                    .min = c(0),
                                    .max = c(5),
                                    .value = c(7),
                                    .result_offset = 20});
      break;
    case NODE_FLOAT_CURVE: {
      program.add_node(type,
                       SVMNodeFloatCurve{.fac = c(1),
                                         .value_in = c(0),
                                         .min_x = 0,
                                         .max_x = 1,
                                         .table_size = 2,
                                         .extrapolate = 1,
                                         .out_offset = 20});
      const int table = program.size();
      program.add_data_float(0);
      program.add_data_float(1);
      program.expect_fetches(table, 1);
      break;
    }
    case NODE_MIX_COLOR:
      program.add_node(type,
                       SVMNodeMixColor{.blend_type = NODE_MIX_BLEND,
                                       .a = c3(0, 1, 2),
                                       .b = c3(4, 5, 10),
                                       .fac = c(0.25f),
                                       .use_clamp = 1,
                                       .use_clamp_result = 0,
                                       .result_offset = 20});
      break;
    case NODE_MIX_FLOAT:
      program.add_node(
          type,
          SVMNodeMixFloat{
              .fac = c(0.25f), .a = c(2), .b = c(6), .use_clamp = 1, .result_offset = 20});
      break;
    case NODE_MIX_VECTOR:
      program.add_node(type,
                       SVMNodeMixVector{.a = c3(0, 1, 2),
                                        .b = c3(4, 5, 10),
                                        .fac = c(0.25f),
                                        .use_clamp = 1,
                                        .result_offset = 20});
      break;
    case NODE_MIX_VECTOR_NON_UNIFORM:
      program.add_node(type,
                       SVMNodeMixVectorNonUniform{.a = c3(0, 1, 2),
                                                  .b = c3(4, 5, 10),
                                                  .fac = c3(0.25f, 0.5f, 0.75f),
                                                  .use_clamp = 1,
                                                  .result_offset = 20});
      break;
    default:
      FAIL("no dispatch node for this case");
      break;
  }
}

static const StackNodeCase stack_node_cases[] = {
    {NODE_CONVERT, "NODE_CONVERT"},
    {NODE_CONVERT_DERIVATIVE, "NODE_CONVERT_DERIVATIVE"},
    {NODE_VALUE_F, "NODE_VALUE_F"},
    {NODE_VALUE_F_DERIVATIVE, "NODE_VALUE_F_DERIVATIVE"},
    {NODE_VALUE_V, "NODE_VALUE_V"},
    {NODE_VALUE_V_DERIVATIVE, "NODE_VALUE_V_DERIVATIVE"},
    {NODE_HSV, "NODE_HSV"},
    {NODE_MATH, "NODE_MATH"},
    {NODE_VECTOR_MATH, "NODE_VECTOR_MATH"},
    {NODE_VECTOR_MATH_DERIVATIVE, "NODE_VECTOR_MATH_DERIVATIVE"},
    {NODE_RGB_RAMP, "NODE_RGB_RAMP"},
    {NODE_GAMMA, "NODE_GAMMA"},
    {NODE_BRIGHTCONTRAST, "NODE_BRIGHTCONTRAST"},
    {NODE_TEXTURE_MAPPING, "NODE_TEXTURE_MAPPING"},
    {NODE_TEXTURE_MAPPING_DERIVATIVE, "NODE_TEXTURE_MAPPING_DERIVATIVE"},
    {NODE_MAPPING, "NODE_MAPPING"},
    {NODE_MAPPING_DERIVATIVE, "NODE_MAPPING_DERIVATIVE"},
    {NODE_MIN_MAX, "NODE_MIN_MAX"},
    {NODE_CURVES, "NODE_CURVES"},
    {NODE_INVERT, "NODE_INVERT"},
    {NODE_MIX, "NODE_MIX"},
    {NODE_SEPARATE_COLOR, "NODE_SEPARATE_COLOR"},
    {NODE_COMBINE_COLOR, "NODE_COMBINE_COLOR"},
    {NODE_SEPARATE_VECTOR, "NODE_SEPARATE_VECTOR"},
    {NODE_SEPARATE_VECTOR_DERIVATIVE, "NODE_SEPARATE_VECTOR_DERIVATIVE"},
    {NODE_COMBINE_VECTOR, "NODE_COMBINE_VECTOR"},
    {NODE_COMBINE_VECTOR_DERIVATIVE, "NODE_COMBINE_VECTOR_DERIVATIVE"},
    {NODE_MAP_RANGE, "NODE_MAP_RANGE"},
    {NODE_VECTOR_MAP_RANGE, "NODE_VECTOR_MAP_RANGE"},
    {NODE_CLAMP, "NODE_CLAMP"},
    {NODE_FLOAT_CURVE, "NODE_FLOAT_CURVE"},
    {NODE_MIX_COLOR, "NODE_MIX_COLOR"},
    {NODE_MIX_FLOAT, "NODE_MIX_FLOAT"},
    {NODE_MIX_VECTOR, "NODE_MIX_VECTOR"},
    {NODE_MIX_VECTOR_NON_UNIFORM, "NODE_MIX_VECTOR_NON_UNIFORM"},
};
static_assert(std::size(stack_node_cases) == 35);

TEST_CASE("cycles svm stack nodes: every stack node case dispatches")
{
  for (const StackNodeCase &entry : stack_node_cases) {
    CAPTURE(entry.name);
    KernelGlobalsCPU globals;
    PainterlySvmTestProgram program = new_program();
    /* Slots 10-18: a float3 and two zero derivatives, so every case's inputs are defined. */
    program.add_node(NODE_VALUE_V_DERIVATIVE,
                     SVMNodeValueV{.out_offset = 10, .value = f3(0.25f, 0.5f, 0.75f)});
    add_dispatch_node(program, entry.type);
    run_program_and_check(globals, program);
  }
}

TEST_CASE("cycles svm stack nodes: math")
{
  KernelGlobalsCPU globals;
  PainterlySvmTestProgram program = new_program();
  program.add_node(NODE_VALUE_F, SVMNodeValueF{.value = 0.5f, .out_offset = 1});
  program.add_node(NODE_MATH,
                   SVMNodeMath{.math_type = NODE_MATH_ADD,
                               .value1 = c(1.5f),
                               .value2 = c(2.25f),
                               .value3 = c(0),
                               .result_offset = 2});
  program.check_equal(2, 3.75f, "ADD");
  program.add_node(NODE_MATH,
                   SVMNodeMath{.math_type = NODE_MATH_ADD,
                               .value1 = s(1),
                               .value2 = c(0.25f),
                               .value3 = c(0),
                               .result_offset = 3});
  program.check_equal(3, 0.75f, "ADD stack input");
  program.add_node(NODE_MATH,
                   SVMNodeMath{.math_type = NODE_MATH_DIVIDE,
                               .value1 = c(1),
                               .value2 = c(0),
                               .value3 = c(0),
                               .result_offset = 4});
  program.check_equal(4, 0.0f, "DIVIDE by 0");
  program.add_node(NODE_MATH,
                   SVMNodeMath{.math_type = NODE_MATH_POWER,
                               .value1 = c(-2),
                               .value2 = c(0.5f),
                               .value3 = c(0),
                               .result_offset = 5});
  program.check_equal(5, 0.0f, "POWER (-2)^0.5");
  program.add_node(NODE_MATH,
                   SVMNodeMath{.math_type = NODE_MATH_POWER,
                               .value1 = c(0),
                               .value2 = c(0),
                               .value3 = c(0),
                               .result_offset = 5});
  program.check_equal(5, 1.0f, "POWER 0^0");
  program.add_node(NODE_MATH,
                   SVMNodeMath{.math_type = NODE_MATH_POWER,
                               .value1 = c(0),
                               .value2 = c(3),
                               .value3 = c(0),
                               .result_offset = 5});
  program.check_equal(5, 0.0f, "POWER 0^3");
  program.add_node(NODE_MATH,
                   SVMNodeMath{.math_type = NODE_MATH_POWER,
                               .value1 = c(2),
                               .value2 = c(10),
                               .value3 = c(0),
                               .result_offset = 5});
  program.check_equal(5, painterly_test_libm_powf(2.0f, 10.0f), "POWER 2^10");
  program.add_node(NODE_MATH,
                   SVMNodeMath{.math_type = NODE_MATH_POWER,
                               .value1 = c(3),
                               .value2 = c(2),
                               .value3 = c(0),
                               .result_offset = 5});
  program.check_equal(5, painterly_test_libm_powf(3.0f, 2.0f), "POWER 3^2");
  program.add_node(NODE_MATH,
                   SVMNodeMath{.math_type = NODE_MATH_POWER,
                               .value1 = c(-2),
                               .value2 = c(3),
                               .value3 = c(0),
                               .result_offset = 5});
  program.check_equal(5, painterly_test_libm_powf(-2.0f, 3.0f), "POWER (-2)^3");
  run_program_and_check(globals, program);
}

TEST_CASE("cycles svm stack nodes: mix")
{
  KernelGlobalsCPU globals;
  PainterlySvmTestProgram program = new_program();
  program.add_node(NODE_MIX,
                   SVMNodeMix{.mix_type = NODE_MIX_BLEND,
                              .c1 = c3(0, 1, 2),
                              .c2 = c3(4, 5, 10),
                              .fac = c(0.25f),
                              .result_offset = 20});
  program.check_equal3(20, f3(1, 2, 4), "MIX blend");
  program.add_node(NODE_MIX,
                   SVMNodeMix{.mix_type = NODE_MIX_BLEND,
                              .c1 = c3(0, 1, 2),
                              .c2 = c3(4, 5, 10),
                              .fac = c(1.5f),
                              .result_offset = 23});
  program.check_equal3(23, f3(4, 5, 10), "MIX factor clamped");
  program.add_node(
      NODE_MIX_FLOAT,
      SVMNodeMixFloat{.fac = c(0.25f), .a = c(2), .b = c(6), .use_clamp = 1, .result_offset = 26});
  program.check_equal(26, 3.0f, "MIX_FLOAT");
  program.add_node(
      NODE_MIX_FLOAT,
      SVMNodeMixFloat{.fac = c(1.5f), .a = c(2), .b = c(6), .use_clamp = 0, .result_offset = 27});
  program.check_equal(27, 8.0f, "MIX_FLOAT unclamped");
  run_program_and_check(globals, program);
}

TEST_CASE("cycles svm stack nodes: map range")
{
  KernelGlobalsCPU globals;
  PainterlySvmTestProgram program = new_program();
  struct Row {
    NodeMapRangeType range_type;
    float from_max;
    SVMStackOffset slot;
    float expected;
    const char *label;
  };
  static const Row rows[] = {
      {NODE_MAP_RANGE_LINEAR, 6, 30, 13.0f, "LINEAR"},
      {NODE_MAP_RANGE_STEPPED, 6, 31, 12.0f, "STEPPED"},
      {NODE_MAP_RANGE_SMOOTHSTEP, 6, 32, 12.53125f, "SMOOTHSTEP"},
      {NODE_MAP_RANGE_LINEAR, 2, 33, 0.0f, "empty range"},
  };
  for (const Row &row : rows) {
    program.add_node(NODE_MAP_RANGE,
                     SVMNodeMapRange{.range_type = row.range_type,
                                     .value = c(3.5f),
                                     .from_min = c(2),
                                     .from_max = c(row.from_max),
                                     .to_min = c(10),
                                     .to_max = c(18),
                                     .steps = c(4),
                                     .result_offset = row.slot});
    program.check_equal(row.slot, row.expected, row.label);
  }
  run_program_and_check(globals, program);
}

TEST_CASE("cycles svm stack nodes: color ramp")
{
  KernelGlobalsCPU globals;
  PainterlySvmTestProgram program = new_program();
  /* The last two rows compare the kernel with the host lookups of kernel/svm/ramp_util.h, which
   * RGBRampNode::constant_fold uses. 0.3 and 0.7 are not dyadic, but the equality is still exact:
   * ramp.h:80-92 and ramp_util.h:32-44 (rgb), :65-77 (alpha) perform the same float32 operations
   * in the same order on each component (saturatef is clamp(f, 0, 1), math_base.h:400-418). */
  const packed_float3 rgb[3] = {f3(0, 0, 0), f3(1, 0.5f, 0.25f), f3(1, 1, 1)};
  const float alpha[3] = {1, 0.5f, 0};
  struct Row {
    float fac;
    uint8_t interpolate;
    SVMStackOffset slot;
    std::vector<int> entries;
    float3 rgb;
    float alpha;
    std::string label;
  };
  const std::vector<Row> rows = {
      {0.25f, 1, 40, {0, 1}, f3(0.5f, 0.25f, 0.125f), 0.75f, "ramp 0.25"},
      {0.75f, 1, 44, {1, 2}, f3(1, 0.75f, 0.625f), 0.25f, "ramp 0.75"},
      {0.75f, 0, 48, {1}, f3(1, 0.5f, 0.25f), 0.5f, "ramp 0.75 constant"},
      {1.5f, 1, 52, {2}, f3(1, 1, 1), 0.0f, "ramp 1.5"},
      {0.3f,
       1,
       56,
       {0, 1},
       rgb_ramp_lookup(rgb, 0.3f, true, false, 3),
       float_ramp_lookup(alpha, 0.3f, true, false, 3),
       "ramp_util 0.3"},
      {0.7f,
       1,
       60,
       {1, 2},
       rgb_ramp_lookup(rgb, 0.7f, true, false, 3),
       float_ramp_lookup(alpha, 0.7f, true, false, 3),
       "ramp_util 0.7"},
  };
  for (const Row &row : rows) {
    CAPTURE(row.label);
    program.add_node(NODE_RGB_RAMP,
                     SVMNodeRGBRamp{.table_size = 3,
                                    .fac = c(row.fac),
                                    .interpolate = row.interpolate,
                                    .color_offset = row.slot,
                                    .alpha_offset = SVMStackOffset(row.slot + 3)});
    const int table = program.size();
    program.add_data_float4(f4(0, 0, 0, 1));
    program.add_data_float4(f4(1, 0.5f, 0.25f, 0.5f));
    program.add_data_float4(f4(1, 1, 1, 0));
    for (const int e : row.entries) {
      program.expect_fetches(table + 4 * e, 4);
    }
    program.check_equal3(row.slot, row.rgb, row.label);
    program.check_equal(SVMStackOffset(row.slot + 3), row.alpha, row.label + " alpha");
  }
  run_program_and_check(globals, program);
}

TEST_CASE("cycles svm stack nodes: convert")
{
  KernelGlobalsCPU globals;
  /* The test's own dyadic weights, which make the dot product exact. Cycles fills them from the
   * scene color space (scene/shader.cpp:1019, :742). The check shows that the case reads
   * kernel_data.film.rgb_to_y (kernel/util/colorspace.h:34-37). */
  globals.data.film.rgb_to_y = f4(0.25f, 0.5f, 0.25f, 0);
  PainterlySvmTestProgram program = new_program();
  program.add_node(NODE_VALUE_V, SVMNodeValueV{.out_offset = 10, .value = f3(1, 2, 4)});
  program.add_node(
      NODE_CONVERT,
      SVMNodeConvert{.convert_type = NODE_CONVERT_CF, .from_offset = 10, .to_offset = 13});
  program.check_equal(13, 2.25f, "CF");
  program.add_node(NODE_VALUE_F, SVMNodeValueF{.value = 0.5f, .out_offset = 14});
  program.add_node(
      NODE_CONVERT,
      SVMNodeConvert{.convert_type = NODE_CONVERT_FV, .from_offset = 14, .to_offset = 15});
  program.check_equal3(15, f3(0.5f, 0.5f, 0.5f), "FV");
  run_program_and_check(globals, program);
}

CCL_NAMESPACE_END
