/* Shim: replaces Cycles scene/image.h without OIIO, OCIO, devices or the image manager */

/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: ImageParams is only declared, and ImageHandle has no
 * members yet. */

#pragma once

#define PAINTERLY_SHIM_SCENE_IMAGE_H 1

#include "util/types_image.h"

CCL_NAMESPACE_BEGIN

/* scene/shader_nodes.h declares ImageTextureNode::image_params() and
 * EnvironmentTextureNode::image_params() (:121, :159), which only need the declaration. */
class ImageParams;

/* scene/shader_nodes.h holds an ImageHandle by value (:102, :196) and compares two of them
 * (:91). Upstream compares image_texture and manager (scene/image.cpp:190-193); this shim has
 * no members yet, so the defaulted comparison compares the members a later card adds. */
class ImageHandle {
 public:
  bool operator==(const ImageHandle &other) const = default;
};

CCL_NAMESPACE_END
