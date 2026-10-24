/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* The shader node type registry of cycles_scene (card T6.4).
 *
 * NODE_DEFINE registers a node type from a static initializer in the translation unit that
 * defines it (graph/node_type.h:157-176). A static library links that unit only when something
 * references it, so a node type that nothing references would be missing from NodeType::find().
 * tools/gen_fragment_units.py defines the function below in the same translation unit as every
 * NODE_DEFINE fragment of scene/shader_nodes.cpp, and makes it call each X::get_node_type().
 * Calling it once therefore registers every shader node type that cycles_scene defines. */

#include <vector>

#include "graph/node_type.h"

CCL_NAMESPACE_BEGIN

/* The node type of every NODE_DEFINE fragment of scene/shader_nodes.cpp, in upstream order.
 * ConvertNode's types are not listed: they register through NodeType::register_on_init
 * (scene/shader_nodes.cpp:1974-1977) in the same translation unit. */
const std::vector<const NodeType *> &painterly_cycles_shader_node_types();

CCL_NAMESPACE_END
