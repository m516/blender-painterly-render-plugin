/* Shim: replaces Cycles scene/attribute.cpp without geometry attribute storage */

/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: only the functions below. The parts marked "verbatim" are
 * byte-for-byte copies of the upstream lines they name. */

#include "scene/attribute.h"

#include <cstring>

CCL_NAMESPACE_BEGIN

/* Attribute: scene/attribute.cpp:453-543, verbatim. */

const char *Attribute::standard_name(AttributeStandard std)
{
  switch (std) {
    case ATTR_STD_POSITION:
      return "P";
    case ATTR_STD_RADIUS:
      return "radius";
    case ATTR_STD_VERTEX_NORMAL:
    case ATTR_STD_CORNER_NORMAL:
      return "N";
    case ATTR_STD_UV:
      return "uv";
    case ATTR_STD_GENERATED:
      return "generated";
    case ATTR_STD_GENERATED_TRANSFORM:
      return "generated_transform";
    case ATTR_STD_UV_TANGENT:
      return "tangent";
    case ATTR_STD_UV_TANGENT_SIGN:
      return "tangent_sign";
    case ATTR_STD_UV_TANGENT_UNDISPLACED:
      return "undisplaced_tangent";
    case ATTR_STD_UV_TANGENT_SIGN_UNDISPLACED:
      return "undisplaced_tangent_sign";
    case ATTR_STD_VERTEX_COLOR:
      return "vertex_color";
    case ATTR_STD_POSITION_UNDEFORMED:
      return "undeformed";
    case ATTR_STD_POSITION_UNDISPLACED:
      return "undisplaced";
    case ATTR_STD_NORMAL_UNDISPLACED:
      return "undisplaced_N";
    case ATTR_STD_PARTICLE:
      return "particle";
    case ATTR_STD_CURVE_INTERCEPT:
      return "curve_intercept";
    case ATTR_STD_CURVE_LENGTH:
      return "curve_length";
    case ATTR_STD_CURVE_RANDOM:
      return "curve_random";
    case ATTR_STD_POINT_RANDOM:
      return "point_random";
    case ATTR_STD_PTEX_FACE_ID:
      return "ptex_face_id";
    case ATTR_STD_PTEX_UV:
      return "ptex_uv";
    case ATTR_STD_VOLUME_DENSITY:
      return "density";
    case ATTR_STD_VOLUME_COLOR:
      return "color";
    case ATTR_STD_VOLUME_FLAME:
      return "flame";
    case ATTR_STD_VOLUME_HEAT:
      return "heat";
    case ATTR_STD_VOLUME_TEMPERATURE:
      return "temperature";
    case ATTR_STD_VOLUME_VELOCITY:
      return "velocity";
    case ATTR_STD_VOLUME_VELOCITY_X:
      return "velocity_x";
    case ATTR_STD_VOLUME_VELOCITY_Y:
      return "velocity_y";
    case ATTR_STD_VOLUME_VELOCITY_Z:
      return "velocity_z";
    case ATTR_STD_POINTINESS:
      return "pointiness";
    case ATTR_STD_RANDOM_PER_ISLAND:
      return "random_per_island";
    case ATTR_STD_SHADOW_TRANSPARENCY:
      return "shadow_transparency";
    case ATTR_STD_NOT_FOUND:
    case ATTR_STD_NONE:
    case ATTR_STD_NUM:
      return "";
  }

  return "";
}

AttributeStandard Attribute::name_standard(const char *name)
{
  if (name) {
    for (int std = ATTR_STD_NONE; std < ATTR_STD_NUM; std++) {
      if (strcmp(name, Attribute::standard_name((AttributeStandard)std)) == 0) {
        return (AttributeStandard)std;
      }
    }
  }

  return ATTR_STD_NONE;
}

/* AttributeRequest: scene/attribute.cpp:1139-1161 without the type and desc members. */

AttributeRequest::AttributeRequest(ustring name_)
{
  name = name_;
  std = ATTR_STD_NONE;
}

AttributeRequest::AttributeRequest(AttributeStandard std_)
{
  name = ustring();
  std = std_;
}

/* AttributeRequestSet: scene/attribute.cpp:1190-1210 and 1224-1238, verbatim. */

void AttributeRequestSet::add(ustring name)
{
  for (const AttributeRequest &req : requests) {
    if (req.name == name) {
      return;
    }
  }

  requests.push_back(AttributeRequest(name));
}

void AttributeRequestSet::add(AttributeStandard std)
{
  for (const AttributeRequest &req : requests) {
    if (req.std == std) {
      return;
    }
  }

  requests.push_back(AttributeRequest(std));
}

void AttributeRequestSet::add_standard(ustring name)
{
  if (name.empty()) {
    return;
  }

  const AttributeStandard std = Attribute::name_standard(name.c_str());

  if (std) {
    add(std);
  }
  else {
    add(name);
  }
}

CCL_NAMESPACE_END
