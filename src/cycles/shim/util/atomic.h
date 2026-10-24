/* Shim: replaces Cycles util/atomic.h without Blender's intern/atomic */

/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

#define PAINTERLY_SHIM_UTIL_ATOMIC_H 1

/* Upstream's CPU branch (util/atomic.h:7-20) includes atomic_ops.h from Blender's intern/atomic,
 * which lies outside the pinned intern/cycles root, and maps Cycles' atomic macros onto it. The
 * only vendored includer, kernel/util/image_2d.h:10, calls no atomic operation on the CPU
 * (card T6.8), so this shim defines none. A card that vendors code calling one adds it here. */
