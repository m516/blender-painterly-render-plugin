/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* Cycles' texture node classes and TextureMapping, extracted from scene/shader_nodes.cpp into
 * cycles_scene (card T6.6). Every expected value is exact: socket defaults are the literals of
 * the NODE_DEFINE fragments, and the TextureMapping transforms use power-of-two scales and
 * integer translations, which transform_inverse() inverts exactly (card T3.2). Transforms are
 * compared component by component: util/transform.h:369-374 compares with memcmp, which tells
 * -0.0 from +0.0. */

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

ShaderNode *create_node_by_name(ShaderGraph &graph, const char *type_name)
{
  const NodeType *type = NodeType::find(ustring(type_name));
  REQUIRE(type != nullptr);
  return graph.create_node(type);
}

/* Component-wise float ==, so that -0.0 equals +0.0. */
bool transform_equal(const Transform &a, const Transform &b)
{
  for (int row = 0; row < 3; row++) {
    for (int column = 0; column < 4; column++) {
      if (!(a[row][column] == b[row][column])) {
        return false;
      }
    }
  }
  return true;
}

}  // namespace

TEST_CASE("cycles texture nodes: the eight texture node types are registered by name")
{
  const std::vector<const NodeType *> &types = painterly_cycles_shader_node_types();
  const char *const names[] = {"gradient_texture",
                               "noise_texture",
                               "voronoi_texture",
                               "white_noise_texture",
                               "wave_texture",
                               "magic_texture",
                               "checker_texture",
                               "brick_texture"};
  for (const char *name : names) {
    CAPTURE(name);
    const NodeType *type = NodeType::find(ustring(name));
    REQUIRE(type != nullptr);
    CHECK(type->type == NodeType::SHADER);
    CHECK(std::count(types.begin(), types.end(), type) == 1);
  }
}

TEST_CASE("cycles texture nodes: socket defaults of the NODE_DEFINE fragments")
{
  ShaderGraph graph;

  /* scene/shader_nodes.cpp:1171-1208. */
  const NoiseTextureNode *noise = static_cast<const NoiseTextureNode *>(
      create_node_by_name(graph, "noise_texture"));
  CHECK(noise->get_dimensions() == 3);
  CHECK(noise->get_type() == NODE_NOISE_FBM);
  CHECK(noise->get_use_normalize());
  CHECK(noise->get_scale() == 1.0f);
  CHECK(noise->get_detail() == 2.0f);
  CHECK(noise->get_roughness() == 0.5f);
  CHECK(noise->get_lacunarity() == 2.0f);
  CHECK(noise->get_distortion() == 0.0f);

  /* TEXTURE_MAPPING_DEFINE (scene/shader_nodes.cpp:47-77) on the noise texture. */
  CHECK(noise->get_tex_mapping_type() == TextureMapping::TEXTURE);
  CHECK(noise->get_tex_mapping_x_mapping() == TextureMapping::X);
  CHECK(noise->get_tex_mapping_y_mapping() == TextureMapping::Y);
  CHECK(noise->get_tex_mapping_z_mapping() == TextureMapping::Z);
  CHECK(noise->get_tex_mapping_scale() == one_float3());
  CHECK(!noise->get_tex_mapping_use_minmax());

  /* scene/shader_nodes.cpp:1311-1358. */
  const VoronoiTextureNode *voronoi = static_cast<const VoronoiTextureNode *>(
      create_node_by_name(graph, "voronoi_texture"));
  CHECK(voronoi->get_dimensions() == 3);
  CHECK(voronoi->get_metric() == NODE_VORONOI_EUCLIDEAN);
  CHECK(voronoi->get_feature() == NODE_VORONOI_F1);
  CHECK(voronoi->get_scale() == 5.0f);
  CHECK(voronoi->get_randomness() == 1.0f);

  /* scene/shader_nodes.cpp:1492-1510. */
  const WhiteNoiseTextureNode *white_noise = static_cast<const WhiteNoiseTextureNode *>(
      create_node_by_name(graph, "white_noise_texture"));
  CHECK(white_noise->get_dimensions() == 3);

  /* scene/shader_nodes.cpp:1118-1140, 1535-1579, 1623-1639, 1672-1687, 1719-1746. */
  const GradientTextureNode *gradient = static_cast<const GradientTextureNode *>(
      create_node_by_name(graph, "gradient_texture"));
  CHECK(gradient->get_gradient_type() == NODE_BLEND_LINEAR);
  const WaveTextureNode *wave = static_cast<const WaveTextureNode *>(
      create_node_by_name(graph, "wave_texture"));
  CHECK(wave->get_wave_type() == NODE_WAVE_BANDS);
  CHECK(wave->get_profile() == NODE_WAVE_PROFILE_SIN);
  CHECK(wave->get_scale() == 1.0f);
  const MagicTextureNode *magic = static_cast<const MagicTextureNode *>(
      create_node_by_name(graph, "magic_texture"));
  CHECK(magic->get_depth() == 2);
  CHECK(magic->get_scale() == 5.0f);
  CHECK(magic->get_distortion() == 1.0f);
  const CheckerTextureNode *checker = static_cast<const CheckerTextureNode *>(
      create_node_by_name(graph, "checker_texture"));
  CHECK(checker->get_scale() == 1.0f);
  const BrickTextureNode *brick = static_cast<const BrickTextureNode *>(
      create_node_by_name(graph, "brick_texture"));
  CHECK(brick->get_offset() == 0.5f);
  CHECK(brick->get_offset_frequency() == 2);
  CHECK(brick->get_squash_frequency() == 2);
  CHECK(brick->get_scale() == 5.0f);
  CHECK(brick->get_mortar_size() == 0.02f);
  CHECK(brick->get_brick_width() == 0.5f);
  CHECK(brick->get_row_height() == 0.25f);
}

TEST_CASE("cycles texture nodes: simplify links TexCoord Generated to flagged Vector inputs")
{
  const unique_ptr<Scene> scene = painterly_test_scene();

  /* NoiseTextureNode's Vector carries SocketType::LINK_TEXTURE_GENERATED
   * (scene/shader_nodes.cpp:1194). ShaderGraph::default_inputs() links it to the Generated output
   * of a new TextureCoordinateNode (scene/shader_graph.cpp:864-883). */
  ShaderGraph graph;
  ShaderNode *noise = create_node_by_name(graph, "noise_texture");
  ShaderNode *emission = create_node_by_name(graph, "emission");
  graph.connect(noise->output("Fac"), emission->input("Strength"));
  graph.connect(emission->output("Emission"), graph.output()->input("Surface"));
  REQUIRE(graph.nodes.size() == 3);

  graph.simplify(scene.get());

  CHECK(graph.nodes.size() == 4);
  const ShaderOutput *vector_link = noise->input("Vector")->link;
  REQUIRE(vector_link != nullptr);
  CHECK(vector_link->parent->type == NodeType::find(ustring("texture_coordinate")));
  CHECK(vector_link->name() == ustring("Generated"));

  /* WhiteNoiseTextureNode's Vector has no such flag (scene/shader_nodes.cpp:1503): it stays
   * unlinked and no TextureCoordinateNode is created. */
  ShaderGraph white_graph;
  ShaderNode *white_noise = create_node_by_name(white_graph, "white_noise_texture");
  ShaderNode *white_emission = create_node_by_name(white_graph, "emission");
  white_graph.connect(white_noise->output("Value"), white_emission->input("Strength"));
  white_graph.connect(white_emission->output("Emission"), white_graph.output()->input("Surface"));
  REQUIRE(white_graph.nodes.size() == 3);

  white_graph.simplify(scene.get());

  CHECK(white_graph.nodes.size() == 3);
  CHECK(white_noise->input("Vector")->link == nullptr);
}

TEST_CASE("cycles texture nodes: TextureMapping skip and compute_transform")
{
  ShaderGraph graph;
  NoiseTextureNode *noise = static_cast<NoiseTextureNode *>(
      create_node_by_name(graph, "noise_texture"));

  /* Default mapping: nothing to do (scene/shader_nodes.cpp:144-164). */
  CHECK(noise->tex_mapping.skip());

  noise->set_tex_mapping_translation(make_float3(1.0f, 2.0f, 4.0f));
  noise->set_tex_mapping_scale(make_float3(2.0f, 2.0f, 2.0f));
  CHECK(!noise->tex_mapping.skip());

  /* TEXTURE: the inverse of translate * rotate(0) * scale (scene/shader_nodes.cpp:117-122):
   * p -> (p - (1, 2, 4)) / 2. */
  CHECK(transform_equal(
      noise->tex_mapping.compute_transform(),
      make_transform(0.5f, 0.0f, 0.0f, -0.5f, 0.0f, 0.5f, 0.0f, -1.0f, 0.0f, 0.0f, 0.5f, -2.0f)));

  /* POINT: translate * rotate(0) * scale itself (scene/shader_nodes.cpp:123-126). */
  noise->set_tex_mapping_type(TextureMapping::POINT);
  CHECK(transform_equal(
      noise->tex_mapping.compute_transform(),
      make_transform(2.0f, 0.0f, 0.0f, 1.0f, 0.0f, 2.0f, 0.0f, 2.0f, 0.0f, 0.0f, 2.0f, 4.0f)));

  /* NORMAL: the transposed inverse of rotate(0) * scale, without translation
   * (scene/shader_nodes.cpp:131-135). This is the caller of transform_transposed_inverse(),
   * util/transform.cpp:15-19, the fragment in the generated unit "transform". */
  noise->set_tex_mapping_type(TextureMapping::NORMAL);
  noise->set_tex_mapping_scale(make_float3(2.0f, 4.0f, 0.5f));
  CHECK(transform_equal(
      noise->tex_mapping.compute_transform(),
      make_transform(0.5f, 0.0f, 0.0f, 0.0f, 0.0f, 0.25f, 0.0f, 0.0f, 0.0f, 0.0f, 2.0f, 0.0f)));
}

CCL_NAMESPACE_END
