/* Shim: replaces Cycles scene/osl.h without OSL */

/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: OSLCompiler keeps only the members that the extracted
 * compile(OSLCompiler &) bodies use. */

#pragma once

#define PAINTERLY_SHIM_SCENE_OSL_H 1

#include "kernel/types.h"

#include "util/transform.h"
#include "util/types.h"

CCL_NAMESPACE_BEGIN

class ShaderNode;

/* Upstream's OSLCompiler (scene/osl.h:152-236) as Cycles builds it without WITH_OSL, reduced to
 * the members that the extracted compile(OSLCompiler &) bodies use. Each method body is the empty
 * stub of upstream's non-OSL build (scene/osl.cpp:1608-1637). Nothing constructs an OSLCompiler:
 * painterly compiles shaders with SVM only. */
class OSLCompiler {
 public:
  void add(ShaderNode * /*node*/, const char * /*name*/, bool /*isfilepath*/ = false) {}

  void parameter(ShaderNode * /*node*/, const char * /*name*/) {}

  void parameter(const char * /*name*/, const float /*f*/) {}
  void parameter_color(const char * /*name*/, const float3 /*f*/) {}
  void parameter(const char * /*name*/, const int /*f*/) {}
  void parameter(const char * /*name*/, const char * /*s*/) {}
  void parameter(const char * /*name*/, const Transform & /*tfm*/) {}

  ShaderType output_type()
  {
    return current_type;
  }

  bool background;

 private:
  ShaderType current_type;
};

CCL_NAMESPACE_END
