/* Shim: replaces Cycles scene/attribute.h without geometry attribute storage or OIIO TypeDesc */

/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: Attribute, AttributeRequest and AttributeRequestSet keep
 * only the members that vendored code uses. */

#pragma once

#define PAINTERLY_SHIM_SCENE_ATTRIBUTE_H 1

#include "kernel/types.h"

#include "util/param.h"
#include "util/vector.h"

CCL_NAMESPACE_BEGIN

/* Upstream's Attribute (scene/attribute.h:55-193) reduced to its two name lookups
 * (scene/attribute.h:187-188), which vendored code calls at scene/svm.cpp:548 and
 * scene/shader_nodes.cpp:6206, 6313. */
class Attribute {
 public:
  static const char *standard_name(AttributeStandard std);
  static AttributeStandard name_standard(const char *name);
};

/* Upstream's AttributeRequest (scene/attribute.h:267-278) without the type and desc members,
 * which only GeometryManager uses. */
class AttributeRequest {
 public:
  ustring name;
  AttributeStandard std;

  explicit AttributeRequest(ustring name_);
  explicit AttributeRequest(AttributeStandard std);
};

/* Upstream's AttributeRequestSet (scene/attribute.h:284-303) reduced to the add() calls of
 * scene/shader_graph.cpp:157-165 and scene/shader_nodes.cpp:3836-3842, 4052-4063, 6193-6217. */
class AttributeRequestSet {
 public:
  vector<AttributeRequest> requests;

  void add(ustring name);
  void add(AttributeStandard std);
  void add_standard(ustring name);
};

CCL_NAMESPACE_END
