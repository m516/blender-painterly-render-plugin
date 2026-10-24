/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* Vendored Cycles shader graph, constant folding and core shader nodes (cycles_scene, card T6.4).
 *
 * Socket naming: linkable sockets are ShaderInput/ShaderOutput objects, found by their UI name
 * with ShaderNode::input()/output() (scene/shader_graph.cpp:93-135). Parameters (SOCKET_ENUM,
 * SOCKET_BOOLEAN, SOCKET_FLOAT, ... without IN/OUT) are not linkable and have no ShaderInput.
 * They are found by member name with NodeType::find_input() (graph/node_type.cpp:186-196), then
 * set with Node::set(); an enum is set by its NodeEnum name. */

#include <algorithm>
#include <vector>

#include "cycles/shader_node_registry.h"
#include "cycles_scene_fixture.h"

#include "graph/node_type.h"
#include "scene/shader_graph.h"
#include "scene/shader_nodes.h"

#include <doctest/doctest.h>

CCL_NAMESPACE_BEGIN

namespace {

/* Creates a node from its Cycles type name, as the Python export of M6b will. */
ShaderNode *create_node_by_name(ShaderGraph &graph, const char *type_name)
{
  const NodeType *type = NodeType::find(ustring(type_name));
  REQUIRE(type != nullptr);
  return graph.create_node(type);
}

/* A parameter's SocketType, found by member name. */
const SocketType &parameter(const ShaderNode *node, const char *member_name)
{
  const SocketType *socket = node->type->find_input(ustring(member_name));
  REQUIRE(socket != nullptr);
  return *socket;
}

}  // namespace

TEST_CASE("cycles shader graph: the core node types are registered by name")
{
  const std::vector<const NodeType *> &types = painterly_cycles_shader_node_types();

  /* The NODE_DEFINE classes that card T6.4 extracts, by Cycles type name. Later cards add types;
   * each of these stays registered exactly once. */
  const char *const names[] = {"attribute",
                               "bump",
                               "clamp",
                               "color",
                               "emission",
                               "geometry",
                               "math",
                               "mix_closure_weight",
                               "output",
                               "set_normal",
                               "texture_coordinate",
                               "value",
                               "vector_math",
                               "vector_transform"};
  for (const char *name : names) {
    CAPTURE(name);
    const NodeType *type = NodeType::find(ustring(name));
    REQUIRE(type != nullptr);
    CHECK(type->type == NodeType::SHADER);
    CHECK(std::count(types.begin(), types.end(), type) == 1);
  }

  /* Every registry entry is the type that NodeType::find() returns for its name. */
  for (const NodeType *type : types) {
    CAPTURE(type->name.c_str());
    CHECK(NodeType::find(type->name) == type);
  }

  /* ConvertNode registers its types through NodeType::register_on_init
   * (scene/shader_nodes.cpp:1924-1977), not through NODE_DEFINE. */
  CHECK(NodeType::find(ustring("convert_float_to_color")) != nullptr);
  CHECK(NodeType::find(ustring("convert_color_to_float")) != nullptr);
}

TEST_CASE("cycles shader graph: links use UI names; parameters use member names")
{
  ShaderGraph graph;
  ShaderNode *math = create_node_by_name(graph, "math");

  REQUIRE(math->input("Value1") != nullptr);
  CHECK(math->input("value1") == nullptr);
  CHECK(math->output("Value") != nullptr);
  CHECK(math->type->find_input(ustring("Value1")) == nullptr);
  CHECK(math->type->find_input(ustring("value1")) == &math->input("Value1")->socket_type);

  /* "Type" and "Use Clamp" are parameters: no ShaderInput. */
  CHECK(math->input("Type") == nullptr);
  CHECK(math->input("Use Clamp") == nullptr);

  math->input("Value1")->set(2.0f);
  math->set(parameter(math, "math_type"), ustring("multiply"));
  math->set(parameter(math, "use_clamp"), true);
  const MathNode *typed_math = static_cast<const MathNode *>(math);
  CHECK(typed_math->get_value1() == 2.0f);
  CHECK(typed_math->get_math_type() == NODE_MATH_MULTIPLY);
  CHECK(typed_math->get_use_clamp());

  /* ValueNode's "Value" is a parameter (SOCKET_FLOAT) and its output a linkable socket. */
  ShaderNode *value = create_node_by_name(graph, "value");
  CHECK(value->input("Value") == nullptr);
  REQUIRE(value->output("Value") != nullptr);
  value->set(parameter(value, "value"), 0.25f);
  CHECK(static_cast<const ValueNode *>(value)->get_value() == 0.25f);
}

TEST_CASE("cycles shader graph: connect inserts conversion nodes")
{
  ShaderGraph graph;
  ShaderNode *value = create_node_by_name(graph, "value");
  ShaderNode *emission = create_node_by_name(graph, "emission");
  REQUIRE(graph.nodes.size() == 3);

  /* Float to color: an automatic ConvertNode (scene/shader_graph.cpp:285-291). */
  graph.connect(value->output("Value"), emission->input("Color"));
  CHECK(graph.nodes.size() == 4);
  const ShaderOutput *color_link = emission->input("Color")->link;
  REQUIRE(color_link != nullptr);
  CHECK(color_link->parent->type == NodeType::find(ustring("convert_float_to_color")));
  CHECK(color_link->parent->special_type == SHADER_SPECIAL_TYPE_AUTOCONVERT);
  CHECK(color_link->parent->inputs[0]->link == value->output("Value"));

  /* Float to closure: an automatic EmissionNode, fed through Strength
   * (scene/shader_graph.cpp:271-284). */
  graph.connect(value->output("Value"), graph.output()->input("Surface"));
  CHECK(graph.nodes.size() == 5);
  const ShaderOutput *surface_link = graph.output()->input("Surface")->link;
  REQUIRE(surface_link != nullptr);
  REQUIRE(surface_link->parent->type == NodeType::find(ustring("emission")));
  EmissionNode *auto_emission = static_cast<EmissionNode *>(surface_link->parent);
  CHECK(auto_emission->from_auto_conversion);
  CHECK(auto_emission->get_strength() == 1.0f);
  CHECK(auto_emission->input("Strength")->link == value->output("Value"));

  /* Closure to anything else: refused, no link and no node (scene/shader_graph.cpp:258-265).
   * The nodes are named because the warning it logs streams both node names (:261-263). */
  ShaderNode *math = create_node_by_name(graph, "math");
  REQUIRE(graph.nodes.size() == 6);
  emission->name = ustring("emission");
  math->name = ustring("math");
  graph.connect(emission->output("Emission"), math->input("Value1"));
  CHECK(math->input("Value1")->link == nullptr);
  CHECK(graph.nodes.size() == 6);
}

TEST_CASE("cycles shader graph: simplify folds Value 2 + Math 3 into Emission Strength 5")
{
  const unique_ptr<Scene> scene = painterly_test_scene();
  ShaderGraph graph;
  ShaderNode *value = create_node_by_name(graph, "value");
  ShaderNode *math = create_node_by_name(graph, "math");
  ShaderNode *emission = create_node_by_name(graph, "emission");
  value->set(parameter(value, "value"), 2.0f);
  math->set(parameter(math, "math_type"), ustring("add"));
  math->input("Value2")->set(3.0f);
  graph.connect(value->output("Value"), math->input("Value1"));
  graph.connect(math->output("Value"), emission->input("Strength"));
  graph.connect(emission->output("Emission"), graph.output()->input("Surface"));
  REQUIRE(graph.nodes.size() == 4);

  graph.simplify(scene.get());

  /* ValueNode folds into Math.Value1, then MathNode folds 2 + 3 into Emission.Strength
   * (ShaderGraph::constant_fold, scene/shader_graph.cpp:533-589). clean() then removes the Value
   * and Math nodes, which no longer reach the output (scene/shader_graph.cpp:801-851). */
  REQUIRE(graph.nodes.size() == 2);
  CHECK(graph.nodes[0]->type == NodeType::find(ustring("output")));
  CHECK(graph.nodes[1] == emission);
  const ShaderInput *strength = emission->input("Strength");
  CHECK(strength->link == nullptr);
  CHECK(strength->constant_folded_in);
  CHECK(static_cast<const EmissionNode *>(emission)->get_strength() == 5.0f);
  CHECK(graph.output()->input("Surface")->link == emission->output("Emission"));
  CHECK(graph.simplified);
}

TEST_CASE("cycles shader graph: a Value folds through an automatic conversion into Emission Color")
{
  const unique_ptr<Scene> scene = painterly_test_scene();
  ShaderGraph graph;
  ShaderNode *value = create_node_by_name(graph, "value");
  ShaderNode *emission = create_node_by_name(graph, "emission");
  value->set(parameter(value, "value"), 0.25f);
  graph.connect(value->output("Value"), emission->input("Color"));
  graph.connect(emission->output("Emission"), graph.output()->input("Surface"));
  REQUIRE(graph.nodes.size() == 4);

  graph.simplify(scene.get());

  /* ConvertNode::constant_fold, float to color (scene/shader_nodes.cpp:2014-2020). */
  REQUIRE(graph.nodes.size() == 2);
  CHECK(graph.nodes[1] == emission);
  CHECK(emission->input("Color")->link == nullptr);
  const float3 color = static_cast<const EmissionNode *>(emission)->get_color();
  CHECK(color.x == 0.25f);
  CHECK(color.y == 0.25f);
  CHECK(color.z == 0.25f);
}

TEST_CASE("cycles shader graph: Math with Use Clamp expands into a Clamp node that folds")
{
  const unique_ptr<Scene> scene = painterly_test_scene();
  ShaderGraph graph;
  ShaderNode *math = create_node_by_name(graph, "math");
  ShaderNode *emission = create_node_by_name(graph, "emission");
  math->set(parameter(math, "math_type"), ustring("add"));
  math->set(parameter(math, "use_clamp"), true);
  math->input("Value1")->set(2.0f);
  math->input("Value2")->set(3.0f);
  graph.connect(math->output("Value"), emission->input("Strength"));
  graph.connect(emission->output("Emission"), graph.output()->input("Surface"));
  REQUIRE(graph.nodes.size() == 3);

  graph.simplify(scene.get());

  /* MathNode::expand inserts ClampNode(minmax, 0, 1) (scene/shader_nodes.cpp:6924-6937);
   * folding gives clamp(2 + 3, 0, 1) = 1 (scene/shader_nodes.cpp:6771-6781). */
  REQUIRE(graph.nodes.size() == 2);
  CHECK(graph.nodes[1] == emission);
  CHECK(static_cast<const EmissionNode *>(emission)->get_strength() == 1.0f);
}

TEST_CASE("cycles shader graph: color to float folding reads Scene::shader_manager")
{
  const unique_ptr<Scene> scene = painterly_test_scene();
  ShaderGraph graph;
  ShaderNode *color = create_node_by_name(graph, "color");
  ShaderNode *emission = create_node_by_name(graph, "emission");
  const float3 rgb = make_float3(0.5f, 0.25f, 0.125f);
  color->set(parameter(color, "value"), rgb);
  graph.connect(color->output("Color"), emission->input("Strength"));
  graph.connect(emission->output("Emission"), graph.output()->input("Surface"));
  REQUIRE(graph.nodes.size() == 4);

  graph.simplify(scene.get());

  /* ConvertNode::constant_fold, color to float (scene/shader_nodes.cpp:2031-2034). */
  REQUIRE(graph.nodes.size() == 2);
  CHECK(static_cast<const EmissionNode *>(emission)->get_strength() ==
        scene->shader_manager->linear_rgb_to_gray(rgb));
}

CCL_NAMESPACE_END
