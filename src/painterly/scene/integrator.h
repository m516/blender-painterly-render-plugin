/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* PainterlyIntegrator: the single source of every SPEC §8 knob default (T3.13). It is a Cycles
 * Node, so Blender's properties are generated from its reflection (M4), and every SPEC §8 knob is
 * a socket here even when its consumer is outside the kernel. NODE_DEFINE registers
 * "painterly_integrator", never "integrator": Cycles registers its own "integrator" NodeType, and
 * M6 vendors it into the same namespace and registry (D15).
 *
 * painterly_integrator_ui_info() carries the UI text, the UI limits and the panel group that the
 * reflection cannot express. The two name sets are equal, one entry per socket, in socket order
 * (a test asserts it). The limits are UI ranges, not behaviour: the only values the engine rejects
 * are the three kernel preconditions that PainterlyScene::set_integrator checks (T3.15, T3.20). */

#include <optional>
#include <vector>

#include "graph/node.h"
#include "painterly/kernel/types.h"

CCL_NAMESPACE_BEGIN

/* SPEC §1. spiral_frame and output_mode have no kernel enum, so they are defined here; every enum
 * socket lists its items in this C++ value order (D16). */
enum PainterlySpiralFrame : int {
  SPIRAL_FRAME_CAMERA = 0,
  SPIRAL_FRAME_WORLD = 1,
  SPIRAL_FRAME_OBJECT = 2,
  SPIRAL_FRAME_SMALLPAINT = 3
};
enum PainterlyOutputMode : int { OUTPUT_DISPLAY_REFERRED = 0, OUTPUT_SCENE_LINEAR = 1 };

/* One socket's UI data (D17). A std::nullopt limit maps to Python None (T3.15). */
struct PainterlySocketUIInfo {
  const char *name; /* The socket identifier, e.g. "lane_length". */
  std::optional<double> min, max, soft_min, soft_max;
  const char *ui_name, *description,
      *group; /* group: "Sampling", "Brush", "Path", "Lights", "Film" */
};

/* One entry per PainterlyIntegrator socket, in socket order. */
const std::vector<PainterlySocketUIInfo> &painterly_integrator_ui_info();

class PainterlyIntegrator : public Node {
 public:
  NODE_DECLARE;

  PainterlyIntegrator() : Node(get_node_type()) {}

  /* SPEC §8 socket table, in table order (T3.13). */
  NODE_SOCKET_API(int, chain)
  NODE_SOCKET_API(int, lane_length)
  NODE_SOCKET_API(uint, seed)
  NODE_SOCKET_API(bool, seed_per_frame)
  NODE_SOCKET_API(int, passes)
  NODE_SOCKET_API(int, spiral_frame)
  NODE_SOCKET_API(float3, spiral_rotation)
  NODE_SOCKET_API(int, u2_mode)
  NODE_SOCKET_API(int, k0_phase_lock_bits)
  NODE_SOCKET_API(float, alpha)
  NODE_SOCKET_API(int, max_depth)
  NODE_SOCKET_API(float, diffuse_gain)
  NODE_SOCKET_API(float, emission_gain)
  NODE_SOCKET_API(bool, continue_after_emitter)
  NODE_SOCKET_API(float, ray_epsilon)
  NODE_SOCKET_API(bool, two_sided)
  NODE_SOCKET_API(float, emission_scale)
  NODE_SOCKET_API(bool, ghost_lights)
  NODE_SOCKET_API(int, output_mode)
  NODE_SOCKET_API(float, exposure)
  NODE_SOCKET_API(float, jitter)

  /* Fills every kernel-consumed field (painterly/kernel/types.h KernelPainterlyIntegrator).
   * Floats become doubles with double(float). spiral_frame is the 3x3 matrix F (SPEC §1), which
   * PainterlyScene::device_update computes, not this method. */
  void device_update(KernelPainterlyIntegrator &kp) const;
};

CCL_NAMESPACE_END
