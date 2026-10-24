/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* Every header under src/cycles/shim/ shadows an upstream Cycles path, and it does so only while
 * the compiler finds no other file at that relative path first: GCC and Clang search the
 * includer's own directory, MSVC the directories of every open includer, before the include path.
 * So each upstream spelling below must reach its shim, and each static_assert proves that its
 * shim's marker macro (T6.1, "Shim markers") was defined by the file the include resolved to. A
 * shim that nothing else here reaches needs its own include: without it, the assert names an
 * undefined macro.
 *
 * This is a build check, not a shim, so it shadows no path. It is an OBJECT library in ALL, so the
 * wheel builds, which build no tests, compile it with GCC, Clang and MSVC. */

#include "kernel/globals.h"

static_assert(PAINTERLY_SHIM_KERNEL_DEVICE_CPU_GLOBALS_H == 1,
              "kernel/device/cpu/globals.h did not resolve to "
              "src/cycles/shim/kernel/device/cpu/globals.h");

#include "graph/node_type.h"

static_assert(PAINTERLY_SHIM_UTIL_PARAM_H == 1,
              "util/param.h did not resolve to src/cycles/shim/util/param.h");
static_assert(PAINTERLY_SHIM_UTIL_THREAD_H == 1,
              "util/thread.h did not resolve to src/cycles/shim/util/thread.h");

#include "util/log.h"
#include "util/stats.h"
#include "util/string.h"

static_assert(PAINTERLY_SHIM_UTIL_LOG_H == 1,
              "util/log.h did not resolve to src/cycles/shim/util/log.h");
static_assert(PAINTERLY_SHIM_UTIL_STATS_H == 1,
              "util/stats.h did not resolve to src/cycles/shim/util/stats.h");
static_assert(PAINTERLY_SHIM_UTIL_STRING_H == 1,
              "util/string.h did not resolve to src/cycles/shim/util/string.h");

#include "scene/attribute.h"
#include "scene/image.h"
#include "scene/osl.h"
#include "scene/scene.h"
#include "scene/shader.h"

static_assert(PAINTERLY_SHIM_SCENE_ATTRIBUTE_H == 1,
              "scene/attribute.h did not resolve to src/cycles/shim/scene/attribute.h");
static_assert(PAINTERLY_SHIM_SCENE_IMAGE_H == 1,
              "scene/image.h did not resolve to src/cycles/shim/scene/image.h");
static_assert(PAINTERLY_SHIM_SCENE_OSL_H == 1,
              "scene/osl.h did not resolve to src/cycles/shim/scene/osl.h");
static_assert(PAINTERLY_SHIM_SCENE_SCENE_H == 1,
              "scene/scene.h did not resolve to src/cycles/shim/scene/scene.h");
static_assert(PAINTERLY_SHIM_SCENE_SHADER_H == 1,
              "scene/shader.h did not resolve to src/cycles/shim/scene/shader.h");
