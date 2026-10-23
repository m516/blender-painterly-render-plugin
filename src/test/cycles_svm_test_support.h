/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* Test support for cycles_svm, Cycles' svm_eval_nodes() as tools/gen_svm_switch.py generates it.
 *
 * svm_eval_nodes() keeps its stack in a local array (kernel/svm/svm.h:109), so a test cannot read
 * a node's outputs. It can see which byte-code words the interpreter fetches. This header
 * redefines kernel_data_fetch, the macro of the shim kernel/device/cpu/globals.h, to record the
 * index of every svm_nodes word read:
 * - the trace shows which cases ran and how many words each consumed (svm_node_get<T>,
 *   kernel/svm/util.h:204-213);
 * - NODE_JUMP_IF_ZERO turns a stack value into a branch that the trace shows
 *   (PainterlySvmTestProgram::check_equal).
 *
 * In a test source, include it before any kernel/svm/ header; never include it outside src/test/.
 *
 * One definition rule: every kernel/svm/ function and svm_eval_nodes() are ccl_device*, which is
 * static on CPU (util/defines.h:25-27 and, for ccl_device_inline and ccl_device_forceinline,
 * :32-33 on MSVC, :48-49 on GCC and Clang). So each translation unit compiles its own copies,
 * which expand the redefined macro. Everything this header defines is in an unnamed namespace for
 * the same reason: each test translation unit gets its own trace, helpers and program class, which
 * call only that unit's svm_eval_nodes(), and no definition with external linkage refers to a
 * static function. kernel_array<T>::fetch(), which has external linkage, does not use the macro
 * and is defined before the redefinition, so all translation units share one definition of it. */

#include <algorithm>
#include <cstddef>
#include <cstring>
#include <string>
#include <string_view>
#include <vector>

#include "kernel/globals.h"

CCL_NAMESPACE_BEGIN
namespace {

/* What svm_eval_nodes() fetched since the last reset: the svm_nodes indices in fetch order, and
 * the number of fetches from any other kernel array. */
struct PainterlySvmTrace {
  std::vector<int> svm_nodes;
  int other_arrays = 0;
};

inline PainterlySvmTrace &painterly_svm_trace()
{
  static PainterlySvmTrace trace;
  return trace;
}

template<typename T>
inline const T &painterly_svm_trace_fetch(const kernel_array<T> &array,
                                          const char *name,
                                          const int index)
{
  if (std::string_view(name) == "svm_nodes") {
    painterly_svm_trace().svm_nodes.push_back(index);
  }
  else {
    painterly_svm_trace().other_arrays++;
  }
  return array.fetch(index);
}

}  // namespace
CCL_NAMESPACE_END

/* The shim defines it as (kg->name.fetch(index)). */
#undef kernel_data_fetch
#define kernel_data_fetch(name, index) (painterly_svm_trace_fetch(kg->name, #name, (index)))

/* Generated into the build tree by tools/gen_svm_switch.py (target cycles_svm). */
#include "svm_eval_nodes.h"

CCL_NAMESPACE_BEGIN
namespace {

/* SVMCompiler::input_float() of an unlinked and of a linked input (scene/svm.cpp:310-322). */
inline SVMInputFloat painterly_svm_input_constant(const float value)
{
  return SVMInputFloat{__float_as_uint(value)};
}

inline SVMInputFloat painterly_svm_input_stack(const SVMStackOffset offset)
{
  return SVMInputFloat{SVM_INPUT_STACK_OFFSET_MASK | uint(offset)};
}

/* SVMCompiler::input_float3() of an unlinked input, and input_float3_from_offset()
 * (scene/svm.cpp:324-346). */
inline SVMInputFloat3 painterly_svm_input_constant3(const float x, const float y, const float z)
{
  return SVMInputFloat3{painterly_svm_input_constant(x),
                        painterly_svm_input_constant(y),
                        painterly_svm_input_constant(z)};
}

inline SVMInputFloat3 painterly_svm_input_stack3(const SVMStackOffset offset)
{
  return SVMInputFloat3{painterly_svm_input_stack(offset), {0}, {0}};
}

/* Indices separated by single spaces, so that a failed CHECK prints them. */
inline std::string painterly_svm_test_format(const std::vector<int> &indices)
{
  std::string text;
  for (const int index : indices) {
    if (!text.empty()) {
      text += ' ';
    }
    text += std::to_string(index);
  }
  return text;
}

/* One svm_nodes array, encoded as SVMCompiler encodes byte code (scene/svm.h:95-112,
 * scene/svm.cpp:434-478): a node is its ShaderNodeType word, then the words of its SVMNode*
 * struct, then any table data. It starts with a jump table of `num_shaders` entries
 * (scene/svm.cpp:95-125) and one NODE_END, at which every entry points until set_jump(). */
class PainterlySvmTestProgram {
 public:
  /* NODE_SHADER_JUMP and SVMNodeShaderJump (scene/svm.cpp:97). */
  static constexpr int jump_entry_words = 1 + int(sizeof(SVMNodeShaderJump) / sizeof(uint));
  /* svm_eval_nodes() fetches two words of a jump entry: its type and its struct. */
  static constexpr int jump_fetches = 2;
  /* The slot check_equal() computes in: the highest valid one (SVM_STACK_INVALID is 255,
   * kernel/svm/types.h:41-43). */
  static constexpr SVMStackOffset scratch_slot = SVMStackOffset(SVM_STACK_SIZE - 1);

  explicit PainterlySvmTestProgram(const int num_shaders = 1)
  {
    const int end = num_shaders * jump_entry_words;
    for (int shader = 0; shader < num_shaders; shader++) {
      push_word(NODE_SHADER_JUMP);
      push_struct(SVMNodeShaderJump{end, end, end});
    }
    push_word(NODE_END);
  }

  /* Points the jump entry of `shader` at three word indices. */
  void set_jump(const int shader, const int surface, const int volume, const int displacement)
  {
    const SVMNodeShaderJump jump{surface, volume, displacement};
    std::memcpy(&words_[size_t(shader * jump_entry_words + 1)], &jump, sizeof(jump));
  }

  /* The index of the next word. */
  int size() const
  {
    return int(words_.size());
  }

  const std::vector<uint> &words() const
  {
    return words_;
  }

  /* SVMCompiler::add_node(ShaderNodeType) (scene/svm.cpp:434-438). svm_eval_nodes() fetches the
   * type word (kernel/svm/svm.h:115). */
  void add_node(const ShaderNodeType type)
  {
    expected_.push_back(size());
    push_word(type);
  }

  /* SVMCompiler::add_node<T>() (scene/svm.h:95-112). svm_eval_nodes() fetches the type word and
   * the first word of the struct (svm_node_get<T>, kernel/svm/util.h:204-213). */
  template<typename T> void add_node(const ShaderNodeType type, const T &node)
  {
    expected_.push_back(size());
    push_word(type);
    expected_.push_back(size());
    push_struct(node);
  }

  /* SVMCompiler::add_node_data_float4() and add_node_data_float() (scene/svm.cpp:467-478). */
  void add_data_float4(const float4 value)
  {
    push_word(__float_as_uint(value.x));
    push_word(__float_as_uint(value.y));
    push_word(__float_as_uint(value.z));
    push_word(__float_as_uint(value.w));
  }

  void add_data_float(const float value)
  {
    push_word(__float_as_uint(value));
  }

  /* Expects one table read of `count` consecutive words from `first` (kernel/svm/ramp.h:14-93),
   * in any order: svm_node_get_data_float4() fetches its four words as function arguments
   * (kernel/svm/util.h:215-221), whose evaluation order C++ leaves unspecified. */
  void expect_fetches(const int first, const int count)
  {
    groups_.push_back({int(expected_.size()), count});
    for (int i = 0; i < count; i++) {
      expected_.push_back(first + i);
    }
  }

  /* Appends byte code that fetches only its three nodes iff stack[slot] == expected. Otherwise
   * svm_eval_nodes() also fetches a fail marker, which failed_checks() reports as `label`:
   *   NODE_MATH SUBTRACT   scratch = stack[slot] - expected
   *   NODE_MATH ABSOLUTE   scratch = |scratch|
   *   NODE_JUMP_IF_ZERO    skip the marker if scratch <= 0 (kernel/svm/svm.h:177-184)
   *   NODE_VALUE_F         the fail marker
   * This is IEEE ==: for finite floats, x - y == 0 iff x == y (IEEE 754 subtraction with gradual
   * underflow), so +0 and -0 pass as equal, and a NaN difference never jumps. `expected` must be
   * finite. */
  void check_equal(const SVMStackOffset slot, const float expected, const std::string &label)
  {
    add_node(NODE_MATH,
             SVMNodeMath{.math_type = NODE_MATH_SUBTRACT,
                         .value1 = painterly_svm_input_stack(slot),
                         .value2 = painterly_svm_input_constant(expected),
                         .value3 = painterly_svm_input_constant(0.0f),
                         .result_offset = scratch_slot});
    add_node(NODE_MATH,
             SVMNodeMath{.math_type = NODE_MATH_ABSOLUTE,
                         .value1 = painterly_svm_input_stack(scratch_slot),
                         .value2 = painterly_svm_input_constant(0.0f),
                         .value3 = painterly_svm_input_constant(0.0f),
                         .result_offset = scratch_slot});
    add_node(NODE_JUMP_IF_ZERO,
             SVMNodeJumpIfZero{.jump_offset = marker_words, .stack_offset = scratch_slot});
    markers_.push_back({size(), label});
    push_word(NODE_VALUE_F);
    push_struct(SVMNodeValueF{.value = 0.0f, .out_offset = scratch_slot});
  }

  /* check_equal() of the three slots of a float3 output. */
  void check_equal3(const SVMStackOffset slot, const float3 expected, const std::string &label)
  {
    check_equal(slot, expected.x, label + ".x");
    check_equal(SVMStackOffset(slot + 1), expected.y, label + ".y");
    check_equal(SVMStackOffset(slot + 2), expected.z, label + ".z");
  }

  /* The trace of svm_eval_nodes() of `shader`, when its jump entry points at the first node added
   * and every check passes. */
  std::string expected_trace(const int shader) const
  {
    std::vector<int> trace = {shader * jump_entry_words, shader * jump_entry_words + 1};
    trace.insert(trace.end(), expected_.begin(), expected_.end());
    return painterly_svm_test_format(trace);
  }

  /* A recorded trace in the form of expected_trace(): the words of each expect_fetches() read
   * sorted. */
  std::string fetched_trace(std::vector<int> fetched) const
  {
    for (const Group &group : groups_) {
      const size_t begin = size_t(jump_fetches + group.start);
      const size_t end = begin + size_t(group.count);
      if (end <= fetched.size()) {
        std::sort(fetched.begin() + std::ptrdiff_t(begin), fetched.begin() + std::ptrdiff_t(end));
      }
    }
    return painterly_svm_test_format(fetched);
  }

  /* The labels of the checks whose fail marker `fetched` contains, joined by ", "; empty if
   * none. */
  std::string failed_checks(const std::vector<int> &fetched) const
  {
    std::string failed;
    for (const Marker &marker : markers_) {
      if (std::find(fetched.begin(), fetched.end(), marker.index) != fetched.end()) {
        if (!failed.empty()) {
          failed += ", ";
        }
        failed += marker.label;
      }
    }
    return failed;
  }

 private:
  /* NODE_VALUE_F and SVMNodeValueF: the words that a passing check's jump skips. */
  static constexpr int marker_words = 1 + int(sizeof(SVMNodeValueF) / sizeof(uint));

  struct Group {
    int start; /* Index into expected_. */
    int count;
  };

  struct Marker {
    int index; /* Word index of the marker's NODE_VALUE_F. */
    std::string label;
  };

  void push_word(const uint word)
  {
    words_.push_back(word);
  }

  template<typename T> void push_struct(const T &value)
  {
    static_assert(alignof(T) <= alignof(uint) && sizeof(T) % sizeof(uint) == 0);
    const size_t first = words_.size();
    words_.resize(first + sizeof(T) / sizeof(uint));
    std::memcpy(&words_[first], &value, sizeof(T));
  }

  std::vector<uint> words_;
  std::vector<int> expected_;
  std::vector<Group> groups_;
  std::vector<Marker> markers_;
};

/* ShaderData as surface_shader_eval() hands it to svm_eval_nodes()
 * (kernel/integrator/surface_shader.h:1258, 1273-1275), for shader id `shader` with ShaderFlag
 * bits `shader_flags`. svm_eval_nodes() itself reads only `shader` (kernel/svm/svm.h:112). Every
 * other field is zero. */
inline ShaderData painterly_svm_test_shader_data(const int shader, const int shader_flags = 0)
{
  ShaderData sd = {};
  sd.shader = shader | shader_flags;
  /* 0, not integrator_state_lcg_init(): the SVM draws from lcg_state only in stochastic texture
   * filtering (kernel/util/image_2d.h:102-107 skips it at 0; kernel/util/image_3d.h:223) and in
   * the Huang hair BSDF. None is reachable from cycles_svm's cases, so evaluation draws no random
   * number and leaves SPEC §2's K and RNG untouched. */
  sd.lcg_state = 0;
  sd.num_closure = 0;
  sd.num_closure_left = MAX_CLOSURE; /* kernel_data.max_closures in Cycles. */
  sd.closure_transparent_extinction = zero_spectrum();
  return sd;
}

/* The node feature mask of Cycles' surface shading without ray-traced nodes
 * (kernel/integrator/shade_surface.h:906). It lacks KERNEL_FEATURE_NODE_VOLUME, so the
 * *_DERIVATIVE cases run. */
constexpr uint painterly_svm_test_node_feature_mask = KERNEL_FEATURE_NODE_MASK_SURFACE &
                                                      ~KERNEL_FEATURE_NODE_RAYTRACE;

/* Runs svm_eval_nodes() of `shader` on `program` and returns its trace. `globals` supplies every
 * other kernel array and KernelData; this sets only its svm_nodes array. */
template<ShaderType type = SHADER_TYPE_SURFACE>
inline PainterlySvmTrace painterly_svm_test_run(KernelGlobalsCPU &globals,
                                                const PainterlySvmTestProgram &program,
                                                const int shader = 0,
                                                const int shader_flags = 0)
{
  globals.svm_nodes.data = program.words().data();
  globals.svm_nodes.width = program.size();
  ShaderData sd = painterly_svm_test_shader_data(shader, shader_flags);
  painterly_svm_trace() = PainterlySvmTrace{};
  const KernelGlobals kg = &globals;
  svm_eval_nodes<painterly_svm_test_node_feature_mask, type>(
      kg, nullptr, &sd, nullptr, PathRayVisibility(0), uint32_t(0));
  return painterly_svm_trace();
}

}  // namespace
CCL_NAMESPACE_END
