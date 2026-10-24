/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* Cycles' SVM compiler end to end (card T6.5): a shader graph (cycles_scene, card T6.4) is
 * compiled by the verbatim SVMCompiler, packed by PainterlyShaderManager and evaluated by the
 * generated svm_eval_nodes() (cycles_svm, cards T6.2 and T6.3). Every expected value is exact:
 * the inputs are dyadic, or the reference is an IEEE 754 identity (see reference_math()). */

#include "cycles_svm_test_support.h"

#include "cycles/shader_node_registry.h"
#include "painterly/scene/svm/shader_manager.h"

#include "graph/node_type.h"
#include "scene/scene.h"
#include "scene/shader.h"
#include "scene/shader_graph.h"
#include "scene/shader_nodes.h"
#include "scene/svm.h"

#include "util/array.h"
#include "util/hash.h"
#include "util/progress.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <iterator>
#include <limits>
#include <string>
#include <vector>

#include <doctest/doctest.h>

CCL_NAMESPACE_BEGIN

namespace {

/* reference_math() relies on IEEE 754 arithmetic and conversions. */
static_assert(std::numeric_limits<float>::is_iec559 && std::numeric_limits<double>::is_iec559);

/* A Scene whose shader_manager is a PainterlyShaderManager. */
unique_ptr<Scene> make_scene()
{
  painterly_cycles_shader_node_types();
  unique_ptr<Scene> scene = make_unique<Scene>();
  scene->shader_manager = make_unique<PainterlyShaderManager>();
  return scene;
}

PainterlyShaderManager &shader_manager(Scene &scene)
{
  return static_cast<PainterlyShaderManager &>(*scene.shader_manager);
}

/* Creates a node from its Cycles type name (card T6.4, "Socket naming"). The first test case
 * checks that every type name used here is registered. */
ShaderNode *create_node_by_name(ShaderGraph &graph, const char *type_name)
{
  return graph.create_node(NodeType::find(ustring(type_name)));
}

/* A parameter's SocketType, found by member name (card T6.4, "Socket naming"). The first test
 * case checks that every parameter used here exists. */
const SocketType &parameter(const ShaderNode *node, const char *member_name)
{
  return *node->type->find_input(ustring(member_name));
}

/* Value -> Math -> Emission -> Output.Surface. Value `value` feeds Math.Value1. Math.Value2 is
 * `value2`, linked from a second Value node if `link_value2`, else an unlinked default.
 * Math.Value3 keeps its default 0. Math feeds Emission.Strength; Emission.Color is `color`. */
unique_ptr<ShaderGraph> value_math_emission(const float value,
                                            const char *math_type,
                                            const float value2,
                                            const bool link_value2,
                                            const float3 color)
{
  unique_ptr<ShaderGraph> graph = make_unique<ShaderGraph>();
  ShaderNode *value_node = create_node_by_name(*graph, "value");
  ShaderNode *math = create_node_by_name(*graph, "math");
  ShaderNode *emission = create_node_by_name(*graph, "emission");
  value_node->set(parameter(value_node, "value"), value);
  math->set(parameter(math, "math_type"), ustring(math_type));
  if (link_value2) {
    ShaderNode *value2_node = create_node_by_name(*graph, "value");
    value2_node->set(parameter(value2_node, "value"), value2);
    graph->connect(value2_node->output("Value"), math->input("Value2"));
  }
  else {
    math->input("Value2")->set(value2);
  }
  emission->input("Color")->set(color);
  graph->connect(value_node->output("Value"), math->input("Value1"));
  graph->connect(math->output("Value"), emission->input("Strength"));
  graph->connect(emission->output("Emission"), graph->output()->input("Surface"));
  return graph;
}

/* Adds a referenced shader with `graph` to the scene. */
Shader *add_shader(Scene &scene, unique_ptr<ShaderGraph> &&graph)
{
  unique_ptr<Shader> shader = make_unique<Shader>();
  shader->set_graph(std::move(graph));
  shader->reference();
  scene.shaders.push_back(std::move(shader));
  return scene.shaders[scene.shaders.size() - 1];
}

/* Prepares an unfinalized graph as device_update_pre and ShaderGraph::finalize would for a lone
 * surface closure, without constant folding: the shader id is its index, the surface is linked
 * (scene/shader.cpp:533, 558), and the closure's SurfaceMixWeight is 0 + 1
 * (ShaderGraph::transform_multi_closure, scene/shader_graph.cpp:1149-1187). */
void prepare_unfolded(Scene &scene)
{
  uint id = 0;
  for (Shader *shader : scene.shaders) {
    shader->id = id++;
    shader->has_surface = true;
    ShaderNode *closure = shader->graph->output()->input("Surface")->link->parent;
    closure->input("SurfaceMixWeight")->set(1.0f);
  }
}

/* The words that SVMCompiler::add_node(shader_node, type, node) appends (scene/svm.h:95-112). */
template<typename T> void push_node(vector<int> &words, const ShaderNodeType type, const T &node)
{
  words.push_back(type);
  const size_t first = words.size();
  words.resize(first + sizeof(T) / sizeof(int));
  std::memcpy(&words[first], &node, sizeof(T));
}

/* The surface program that SVMCompiler emits for value_math_emission(value, type, value2, false,
 * color) without constant folding (card T6.5, "Expected byte code"). */
void push_unfolded_surface(vector<int> &words,
                           const float value,
                           const NodeMathType math_type,
                           const float value2,
                           const float3 color)
{
  push_node(words, NODE_VALUE_F, SVMNodeValueF{.value = value, .out_offset = 0});
  push_node(words,
            NODE_MATH,
            SVMNodeMath{.math_type = math_type,
                        .value1 = painterly_svm_input_stack(0),
                        .value2 = painterly_svm_input_constant(value2),
                        .value3 = painterly_svm_input_constant(0.0f),
                        .result_offset = 1});
  push_node(
      words,
      NODE_EMISSION_WEIGHT,
      SVMNodeEmissionWeight{.color = painterly_svm_input_constant3(color.x, color.y, color.z),
                            .strength = painterly_svm_input_stack(1)});
  push_node(words,
            NODE_CLOSURE_EMISSION,
            SVMNodeClosureEmission{.mix_weight_offset = SVM_STACK_INVALID});
  words.push_back(NODE_END);
}

vector<int> to_vector(const array<int> &words)
{
  return vector<int>(words.data(), words.data() + words.size());
}

/* Evaluates the surface shader `shader_id` of `dscene` with the generated svm_eval_nodes(), as
 * surface_shader_eval() calls it (kernel/integrator/surface_shader.h:1248-1297). ShaderData comes
 * from painterly_svm_test_shader_data() (card T6.3), and sd->flag from the shader's KernelShader,
 * as shader_setup_from_ray() sets it (kernel/geom/shader_data.h:113). */
ShaderData eval_surface(const DeviceScene &dscene, const int shader_id, PainterlySvmTrace &trace)
{
  KernelGlobalsCPU globals;
  globals.svm_nodes.data = reinterpret_cast<const uint *>(dscene.svm_nodes.data());
  globals.svm_nodes.width = int(dscene.svm_nodes.size());
  globals.shaders.data = dscene.shaders.data();
  globals.shaders.width = int(dscene.shaders.size());
  globals.data = dscene.data;

  ShaderData sd = painterly_svm_test_shader_data(shader_id);
  sd.flag = dscene.shaders[shader_id].flags;
  painterly_svm_trace() = PainterlySvmTrace{};
  const KernelGlobals kg = &globals;
  svm_eval_nodes<painterly_svm_test_node_feature_mask, SHADER_TYPE_SURFACE>(
      kg, nullptr, &sd, nullptr, PathRayVisibility(0), uint32_t(0));
  trace = painterly_svm_trace();
  return sd;
}

/* KernelShader::flags of the shaders in these tests. Of the conditions that PainterlyShaderManager
 * ports, only the defaults volume_sampling_method = multiple_importance and
 * use_bump_map_correction = true hold (scene/shader.cpp:52, 58-61; device_update_common,
 * scene/shader.cpp:671-673, 686-688). For these shaders upstream would also set SD_HAS_EMISSION,
 * SD_MIS_FRONT and SD_MIS_BACK (:629-641), and for the folded one SD_HAS_CONSTANT_EMISSION
 * (:690-693), all from Shader::estimate_emission() (:239-281), which the port leaves out. */
constexpr int default_shader_flags = SD_VOLUME_MIS | SD_USE_BUMP_MAP_CORRECTION;

/* The value of Math operation `type` on float32 inputs a and b, computed in double precision and
 * rounded to float32 once: a reference that shares no code with Cycles.
 * - +, -, *, / and sqrt: IEEE 754 makes Cycles' float32 result the exact value correctly rounded.
 *   Rounding the double result again gives the same float, because double has 53 >= 2 * 24 + 2
 *   significand bits (Figueroa, "When is double rounding innocuous?", SIGNUM 1995). Fraction is
 *   a - floor(a), a subtraction of two floats.
 * - abs, floor, ceil, trunc, fmod, min, max, the comparisons and sign are exact.
 * - Cycles' definitions at 0 are part of the operation: division and modulo by 0 give 0
 *   (util/math_base.h:594-597, 608-611), sqrt of x <= 0 gives 0 (:538-541), sign of 0 is 0
 *   (:491-497). */
float reference_math(const NodeMathType type, const float a, const float b)
{
  const double x = a;
  const double y = b;
  switch (type) {
    case NODE_MATH_ADD:
      return float(x + y);
    case NODE_MATH_SUBTRACT:
      return float(x - y);
    case NODE_MATH_MULTIPLY:
      return float(x * y);
    case NODE_MATH_DIVIDE:
      return (b != 0.0f) ? float(x / y) : 0.0f;
    case NODE_MATH_MINIMUM:
      return (a < b) ? a : b;
    case NODE_MATH_MAXIMUM:
      return (a > b) ? a : b;
    case NODE_MATH_LESS_THAN:
      return (a < b) ? 1.0f : 0.0f;
    case NODE_MATH_GREATER_THAN:
      return (a > b) ? 1.0f : 0.0f;
    case NODE_MATH_ABSOLUTE:
      return float(std::fabs(x));
    case NODE_MATH_SQRT:
      return (a > 0.0f) ? float(std::sqrt(x)) : 0.0f;
    case NODE_MATH_FLOOR:
      return float(std::floor(x));
    case NODE_MATH_CEIL:
      return float(std::ceil(x));
    case NODE_MATH_TRUNC:
      return float(std::trunc(x));
    case NODE_MATH_FRACTION:
      return float(x - std::floor(x));
    case NODE_MATH_MODULO:
      return (b != 0.0f) ? float(std::fmod(x, y)) : 0.0f;
    case NODE_MATH_SIGN:
      return (a > 0.0f) ? 1.0f : ((a < 0.0f) ? -1.0f : 0.0f);
    default:
      return std::numeric_limits<float>::quiet_NaN();
  }
}

}  // namespace

TEST_CASE("cycles svm compiler: the node types and parameters of these tests are registered")
{
  painterly_cycles_shader_node_types();
  for (const char *type_name : {"emission", "math", "output", "value"}) {
    const std::string name = type_name;
    CAPTURE(name);
    REQUIRE(NodeType::find(ustring(type_name)) != nullptr);
  }
  CHECK(NodeType::find(ustring("value"))->find_input(ustring("value")) != nullptr);
  CHECK(NodeType::find(ustring("math"))->find_input(ustring("math_type")) != nullptr);
}

TEST_CASE("cycles svm compiler: Value -> Math -> Emission compiles to the derived byte code")
{
  const unique_ptr<Scene> scene = make_scene();
  Shader *shader = add_shader(
      *scene, value_math_emission(0.75f, "multiply", 4.0f, false, make_float3(0.25f, 0.5f, 1.0f)));
  prepare_unfolded(*scene);

  Progress progress;
  SVMCompiler compiler(scene.get(), progress);
  array<int> svm_nodes;
  SVMCompiler::Summary summary;
  compiler.compile(shader, svm_nodes, 0, &summary);

  vector<int> expected;
  push_node(expected, NODE_SHADER_JUMP, SVMNodeShaderJump{4, 21, 22});
  push_unfolded_surface(expected, 0.75f, NODE_MATH_MULTIPLY, 4.0f, make_float3(0.25f, 0.5f, 1.0f));
  expected.push_back(NODE_END); /* volume */
  expected.push_back(NODE_END); /* displacement */
  CHECK(painterly_svm_test_format(to_vector(svm_nodes)) == painterly_svm_test_format(expected));

  /* scene/svm.cpp:1228-1232: the nodes after the jump node, and the stack slots 0 and 1. */
  CHECK(summary.num_svm_nodes == 19);
  CHECK(summary.peak_stack_usage == 2);

  /* SVMCompiler marks each node type it emits in KernelData::svm_usage (scene/svm.cpp:169, 436,
   * 1176; scene/svm.h:105). */
  const int *usage = reinterpret_cast<const int *>(&scene->dscene.data.svm_usage);
  vector<int> used;
  for (int type = 0; type < int(NODE_NUM); type++) {
    if (usage[type]) {
      used.push_back(type);
    }
  }
  vector<int> expected_used = {NODE_END,
                               NODE_SHADER_JUMP,
                               NODE_CLOSURE_EMISSION,
                               NODE_EMISSION_WEIGHT,
                               NODE_VALUE_F,
                               NODE_MATH};
  std::sort(expected_used.begin(), expected_used.end());
  CHECK(painterly_svm_test_format(used) == painterly_svm_test_format(expected_used));
}

TEST_CASE("cycles svm compiler: the unfolded program evaluates to its emission")
{
  const unique_ptr<Scene> scene = make_scene();
  add_shader(*scene,
             value_math_emission(0.75f, "multiply", 4.0f, false, make_float3(0.25f, 0.5f, 1.0f)));
  prepare_unfolded(*scene);
  Progress progress;
  shader_manager(*scene).device_update_post(nullptr, &scene->dscene, scene.get(), progress);

  /* One shader: the packed program is the compiled one (scene/svm.cpp:115-124 add
   * 4 - 4 to every offset). */
  REQUIRE(scene->dscene.svm_nodes.size() == 23);
  CHECK(scene->dscene.shaders.size() == 1);
  CHECK(scene->dscene.shaders[0].flags == default_shader_flags);

  PainterlySvmTrace trace;
  const ShaderData sd = eval_surface(scene->dscene, 0, trace);
  /* 0.75 * 4 = 3 into slot 1, then (0.25, 0.5, 1) * 3: exact in float. */
  CHECK(sd.closure_emission_background.x == 0.75f);
  CHECK(sd.closure_emission_background.y == 1.5f);
  CHECK(sd.closure_emission_background.z == 3.0f);
  CHECK((sd.flag & SD_EMISSION) != 0);
  /* The jump entry, then the type and first struct word of each node, then NODE_END
   * (kernel/svm/svm.h:112-136; svm_node_get, kernel/svm/util.h:204-213). */
  CHECK(painterly_svm_test_format(trace.svm_nodes) == "0 1 4 5 7 8 13 14 18 19 20");
  CHECK(trace.other_arrays == 0);
}

TEST_CASE("cycles svm compiler: device_update_pre folds the graph and the folded program agrees")
{
  const unique_ptr<Scene> scene = make_scene();
  Shader *shader = add_shader(
      *scene, value_math_emission(0.75f, "multiply", 4.0f, false, make_float3(0.25f, 0.5f, 1.0f)));
  Progress progress;
  PainterlyShaderManager &manager = shader_manager(*scene);
  manager.device_update_pre(nullptr, &scene->dscene, scene.get(), progress);

  /* ShaderGraph::finalize: Value and Math fold into Emission.Strength = 3, clean() removes them,
   * and the lone closure gets SurfaceMixWeight 0 + 1 (scene/shader_graph.cpp:374-402). */
  CHECK(shader->id == 0);
  CHECK(shader->has_surface);
  CHECK_FALSE(shader->has_volume);
  CHECK_FALSE(shader->has_displacement);
  REQUIRE(shader->graph->nodes.size() == 2);
  const EmissionNode *emission = static_cast<const EmissionNode *>(shader->graph->nodes[1]);
  CHECK(emission->get_strength() == 3.0f);
  CHECK(emission->get_surface_mix_weight() == 1.0f);

  manager.device_update_post(nullptr, &scene->dscene, scene.get(), progress);

  /* EmissionNode::compile without links: NODE_CLOSURE_SET_WEIGHT with color * strength
   * (scene/shader_nodes.cpp:3085-3092), then NODE_CLOSURE_EMISSION. */
  vector<int> expected;
  push_node(expected, NODE_SHADER_JUMP, SVMNodeShaderJump{4, 11, 12});
  push_node(expected,
            NODE_CLOSURE_SET_WEIGHT,
            SVMNodeClosureSetWeight{.rgb = make_float3(0.75f, 1.5f, 3.0f)});
  push_node(expected,
            NODE_CLOSURE_EMISSION,
            SVMNodeClosureEmission{.mix_weight_offset = SVM_STACK_INVALID});
  expected.push_back(NODE_END);
  expected.push_back(NODE_END);
  expected.push_back(NODE_END);
  CHECK(painterly_svm_test_format(to_vector(scene->dscene.svm_nodes)) ==
        painterly_svm_test_format(expected));

  REQUIRE(scene->dscene.shaders.size() == 1);
  CHECK(scene->dscene.shaders[0].flags == default_shader_flags);
  CHECK(scene->dscene.data.integrator.use_volumes == 0);
  CHECK(scene->dscene.data.integrator.transparent_shadows == 0);
  /* device_update_common writes rgb_to_y (scene/shader.cpp:742). Each component is
   * linear_rgb_to_gray() of a unit vector: 1 * r + 0 * g + 0 * b is exact. */
  CHECK(scene->dscene.data.film.rgb_to_y.x ==
        manager.linear_rgb_to_gray(make_float3(1.0f, 0.0f, 0.0f)));
  CHECK(scene->dscene.data.film.rgb_to_y.y ==
        manager.linear_rgb_to_gray(make_float3(0.0f, 1.0f, 0.0f)));
  CHECK(scene->dscene.data.film.rgb_to_y.z ==
        manager.linear_rgb_to_gray(make_float3(0.0f, 0.0f, 1.0f)));

  PainterlySvmTrace trace;
  const ShaderData sd = eval_surface(scene->dscene, 0, trace);
  CHECK(sd.closure_emission_background.x == 0.75f);
  CHECK(sd.closure_emission_background.y == 1.5f);
  CHECK(sd.closure_emission_background.z == 3.0f);
  CHECK((sd.flag & SD_EMISSION) != 0);
  CHECK(painterly_svm_test_format(trace.svm_nodes) == "0 1 4 5 8 9 10");
  CHECK(trace.other_arrays == 0);
}

TEST_CASE("cycles svm compiler: two shaders share one jump table")
{
  const unique_ptr<Scene> scene = make_scene();
  add_shader(*scene,
             value_math_emission(0.75f, "multiply", 4.0f, false, make_float3(0.25f, 0.5f, 1.0f)));
  add_shader(*scene,
             value_math_emission(0.5f, "multiply", 8.0f, false, make_float3(0.25f, 0.5f, 1.0f)));
  prepare_unfolded(*scene);
  Progress progress;
  shader_manager(*scene).device_update_post(nullptr, &scene->dscene, scene.get(), progress);

  /* scene/svm.cpp:95-134: two jump entries, then the 19 node words of each shader. The offsets of
   * shader 0 move by 8 - 4, those of shader 1 by 27 - 4. */
  vector<int> expected;
  push_node(expected, NODE_SHADER_JUMP, SVMNodeShaderJump{8, 25, 26});
  push_node(expected, NODE_SHADER_JUMP, SVMNodeShaderJump{27, 44, 45});
  push_unfolded_surface(expected, 0.75f, NODE_MATH_MULTIPLY, 4.0f, make_float3(0.25f, 0.5f, 1.0f));
  expected.push_back(NODE_END);
  expected.push_back(NODE_END);
  push_unfolded_surface(expected, 0.5f, NODE_MATH_MULTIPLY, 8.0f, make_float3(0.25f, 0.5f, 1.0f));
  expected.push_back(NODE_END);
  expected.push_back(NODE_END);
  CHECK(painterly_svm_test_format(to_vector(scene->dscene.svm_nodes)) ==
        painterly_svm_test_format(expected));
  REQUIRE(scene->dscene.shaders.size() == 2);
  CHECK(scene->dscene.shaders[0].flags == default_shader_flags);
  CHECK(scene->dscene.shaders[1].flags == default_shader_flags);

  PainterlySvmTrace trace;
  const ShaderData sd0 = eval_surface(scene->dscene, 0, trace);
  CHECK(sd0.closure_emission_background.x == 0.75f);
  CHECK(sd0.closure_emission_background.y == 1.5f);
  CHECK(sd0.closure_emission_background.z == 3.0f);
  CHECK(painterly_svm_test_format(trace.svm_nodes) == "0 1 8 9 11 12 17 18 22 23 24");

  /* 0.5 * 8 = 4, then (0.25, 0.5, 1) * 4. */
  const ShaderData sd1 = eval_surface(scene->dscene, 1, trace);
  CHECK(sd1.closure_emission_background.x == 1.0f);
  CHECK(sd1.closure_emission_background.y == 2.0f);
  CHECK(sd1.closure_emission_background.z == 4.0f);
  CHECK(painterly_svm_test_format(trace.svm_nodes) == "4 5 27 28 30 31 36 37 41 42 43");
}

TEST_CASE("cycles svm compiler: Math through compiler and SVM equals an independent reference")
{
  /* The operations whose float32 result reference_math() gives exactly, by Cycles name
   * (NODE_DEFINE(MathNode), scene/shader_nodes.cpp:6867-6909). */
  struct Operation {
    const char *name;
    NodeMathType type;
  };
  const Operation operations[] = {{"add", NODE_MATH_ADD},
                                  {"subtract", NODE_MATH_SUBTRACT},
                                  {"multiply", NODE_MATH_MULTIPLY},
                                  {"divide", NODE_MATH_DIVIDE},
                                  {"minimum", NODE_MATH_MINIMUM},
                                  {"maximum", NODE_MATH_MAXIMUM},
                                  {"less_than", NODE_MATH_LESS_THAN},
                                  {"greater_than", NODE_MATH_GREATER_THAN},
                                  {"absolute", NODE_MATH_ABSOLUTE},
                                  {"sqrt", NODE_MATH_SQRT},
                                  {"floor", NODE_MATH_FLOOR},
                                  {"ceil", NODE_MATH_CEIL},
                                  {"trunc", NODE_MATH_TRUNC},
                                  {"fraction", NODE_MATH_FRACTION},
                                  {"modulo", NODE_MATH_MODULO},
                                  {"sign", NODE_MATH_SIGN}};
  static_assert(std::size(operations) == 16);

  /* The inputs: every pair of ten special values (zeros of both signs, units, a half, dyadic
   * values, the largest, the smallest normal and the smallest subnormal float), then the finite
   * pairs among 4096 pairs of hashed float bit patterns. */
  const float special[] = {0.0f,
                           -0.0f,
                           1.0f,
                           -1.0f,
                           0.5f,
                           -2.5f,
                           3.0f,
                           std::numeric_limits<float>::max(),
                           std::numeric_limits<float>::min(),
                           std::numeric_limits<float>::denorm_min()};
  vector<std::pair<float, float>> inputs;
  for (const float a : special) {
    for (const float b : special) {
      inputs.emplace_back(a, b);
    }
  }
  const uint num_hashed = 4096;
  for (uint i = 0; i < num_hashed; i++) {
    const float a = __uint_as_float(hash_uint2(i, 0));
    const float b = __uint_as_float(hash_uint2(i, 1));
    if (std::isfinite(a) && std::isfinite(b)) {
      inputs.emplace_back(a, b);
    }
  }
  CHECK(inputs.size() == 4162);

  for (const Operation &operation : operations) {
    const std::string name = operation.name;
    CAPTURE(name);
    int mismatches_unfolded = 0;
    int mismatches_folded = 0;
    for (const auto &[a, b] : inputs) {
      const float expected = reference_math(operation.type, a, b);
      Progress progress;

      /* Compiled without folding: the SVM computes the operation. */
      const unique_ptr<Scene> unfolded = make_scene();
      add_shader(*unfolded,
                 value_math_emission(a, operation.name, b, true, make_float3(1.0f, 1.0f, 1.0f)));
      prepare_unfolded(*unfolded);
      shader_manager(*unfolded).device_update_post(
          nullptr, &unfolded->dscene, unfolded.get(), progress);
      PainterlySvmTrace trace;
      const ShaderData sd_unfolded = eval_surface(unfolded->dscene, 0, trace);
      /* Emission is Color (1, 1, 1) times the result: exact. */
      if (!(sd_unfolded.closure_emission_background.x == expected)) {
        mismatches_unfolded++;
      }

      /* Prepared as Cycles prepares it: MathNode::constant_fold computes the operation on the host
       * (scene/shader_nodes.cpp:6939-6947). A zero strength discards the emission
       * (scene/shader_nodes.cpp:3106-3114), which leaves the emission 0. */
      const unique_ptr<Scene> folded = make_scene();
      add_shader(*folded,
                 value_math_emission(a, operation.name, b, true, make_float3(1.0f, 1.0f, 1.0f)));
      shader_manager(*folded).device_update_pre(nullptr, &folded->dscene, folded.get(), progress);
      shader_manager(*folded).device_update_post(nullptr, &folded->dscene, folded.get(), progress);
      const ShaderData sd_folded = eval_surface(folded->dscene, 0, trace);
      if (!(sd_folded.closure_emission_background.x == expected)) {
        mismatches_folded++;
      }
    }
    CHECK(mismatches_unfolded == 0);
    CHECK(mismatches_folded == 0);
  }
}

CCL_NAMESPACE_END
