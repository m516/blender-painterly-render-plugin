// SPDX-License-Identifier: GPL-3.0-or-later
// Unit tests for the vendored Cycles graph/ reflection (T3.3): NODE_DECLARE / NODE_DEFINE /
// SOCKET_* defaults, set and get round trips, NodeType::find, enum lookup by name and the modified
// flags. Every comparison is exact.

#include <doctest/doctest.h>

#include "graph/node.h"
#include "graph/node_type.h"
#include "util/param.h"
#include "util/transform.h"
#include "util/types.h"

CCL_NAMESPACE_BEGIN

namespace {

// Values of the enum socket "mode". A node stores each enumerator as its int value.
enum TestGraphMode { GRAPH_MODE_A = 0, GRAPH_MODE_B = 1, GRAPH_MODE_C = 2 };

// A node with one socket of each type the card names: bool, int, float, enum, transform and
// float3.
struct TestGraphNode : public Node {
  NODE_DECLARE;

  TestGraphNode() : Node(get_node_type()) {}

  NODE_SOCKET_API(bool, flag)
  NODE_SOCKET_API(int, count)
  NODE_SOCKET_API(float, scale)
  NODE_SOCKET_API(int, mode)
  NODE_SOCKET_API(Transform, tfm)
  NODE_SOCKET_API(float3, offset)
};

NODE_DEFINE(TestGraphNode)
{
  NodeType *type = NodeType::add("test_graph_node", create);

  static NodeEnum mode_values;
  mode_values.insert("a", GRAPH_MODE_A);
  mode_values.insert("b", GRAPH_MODE_B);
  mode_values.insert("c", GRAPH_MODE_C);

  SOCKET_BOOLEAN(flag, "Flag", false);
  SOCKET_INT(count, "Count", 3);
  SOCKET_FLOAT(scale, "Scale", 0.5f);
  SOCKET_ENUM(mode, "Mode", mode_values, GRAPH_MODE_B);
  SOCKET_TRANSFORM(tfm, "Transform", transform_identity());
  SOCKET_POINT(offset, "Offset", make_float3(1.0f, 2.0f, 3.0f));

  return type;
}

}  // namespace

TEST_CASE("node type registers every socket with its declared default")
{
  const NodeType *type = NodeType::find(ustring("test_graph_node"));
  REQUIRE(type != nullptr);
  CHECK(type == TestGraphNode::get_node_type());
  CHECK(type->inputs.size() == 6u);

  TestGraphNode node;
  CHECK_FALSE(node.get_flag());
  CHECK(node.get_count() == 3);
  CHECK(node.get_scale() == 0.5f);
  CHECK(node.get_mode() == GRAPH_MODE_B);
  CHECK(node.get_tfm() == transform_identity());
  CHECK(node.get_offset() == make_float3(1.0f, 2.0f, 3.0f));
  // Node's constructor names an unnamed node after its type.
  CHECK(node.name == type->name);
}

TEST_CASE("set and get round trip every socket type")
{
  TestGraphNode node;

  node.set_flag(true);
  CHECK(node.get_flag());

  node.set_count(-7);
  CHECK(node.get_count() == -7);

  node.set_scale(2.25f);  // exact in binary floating point
  CHECK(node.get_scale() == 2.25f);

  node.set_mode(GRAPH_MODE_C);
  CHECK(node.get_mode() == GRAPH_MODE_C);

  const Transform translated = transform_translate(make_float3(4.0f, -5.0f, 6.0f));
  node.set_tfm(translated);
  CHECK(node.get_tfm() == translated);

  node.set_offset(make_float3(-1.0f, 0.5f, 8.0f));
  CHECK(node.get_offset() == make_float3(-1.0f, 0.5f, 8.0f));
}

TEST_CASE("NodeType::find returns the registered type or nullptr")
{
  const NodeType *type = NodeType::find(ustring("test_graph_node"));
  REQUIRE(type != nullptr);
  CHECK(type->name == ustring("test_graph_node"));
  CHECK(type->find_input(ustring("count")) != nullptr);
  CHECK(type->find_input(ustring("no_such_socket")) == nullptr);
  CHECK(NodeType::find(ustring("no_such_node_type")) == nullptr);
}

TEST_CASE("enum sockets map names to values in both directions")
{
  const SocketType *mode = NodeType::find(ustring("test_graph_node"))->find_input(ustring("mode"));
  REQUIRE(mode != nullptr);
  REQUIRE(mode->enum_values != nullptr);
  const NodeEnum &values = *mode->enum_values;

  CHECK(values.exists(ustring("b")));
  CHECK_FALSE(values.exists(ustring("missing")));
  CHECK(values[ustring("c")] == GRAPH_MODE_C);
  CHECK(values["a"] == GRAPH_MODE_A);
  CHECK(values[static_cast<int>(GRAPH_MODE_B)] == ustring("b"));

  // Setting an enum socket by name stores the value of that name.
  TestGraphNode node;
  node.set(*mode, ustring("c"));
  CHECK(node.get_mode() == GRAPH_MODE_C);
  node.set(*mode, ustring("a"));
  CHECK(node.get_mode() == GRAPH_MODE_A);
}

TEST_CASE("modified flags follow value changes and explicit tags")
{
  TestGraphNode node;
  // The constructor tags every socket as modified.
  CHECK(node.is_modified());

  node.clear_modified();
  CHECK_FALSE(node.is_modified());

  // Setting a socket to its current value is not a change.
  node.set_count(3);
  CHECK_FALSE(node.count_is_modified());
  CHECK_FALSE(node.is_modified());

  node.set_count(4);
  CHECK(node.count_is_modified());
  CHECK(node.is_modified());
  CHECK_FALSE(node.flag_is_modified());

  node.clear_modified();
  node.set_offset(make_float3(1.0f, 2.0f, 3.0f));  // equal to the default
  CHECK_FALSE(node.is_modified());

  node.tag_tfm_modified();
  CHECK(node.tfm_is_modified());
  CHECK_FALSE(node.scale_is_modified());

  node.tag_modified();
  CHECK(node.is_modified());
  node.clear_modified();
  CHECK_FALSE(node.is_modified());
}

CCL_NAMESPACE_END
