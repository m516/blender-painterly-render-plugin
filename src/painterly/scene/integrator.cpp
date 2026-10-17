/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "painterly/scene/integrator.h"

CCL_NAMESPACE_BEGIN

NODE_DEFINE(PainterlyIntegrator)
{
  /* D15: "painterly_integrator", never "integrator": Cycles registers its own "integrator"
   * NodeType, and M6 vendors it into the same namespace and registry. */
  NodeType *type = NodeType::add("painterly_integrator", create);

  /* Sockets in SPEC §8 table order (T3.13). Each default's source is the comment above it. */

  static NodeEnum chain_values;
  /* SPEC §3. */
  chain_values.insert("image", CHAIN_IMAGE);
  chain_values.insert("row", CHAIN_ROW);
  chain_values.insert("lane", CHAIN_LANE);

  static NodeEnum u2_mode_values;
  /* SPEC §4. */
  u2_mode_values.insert("same", U2_SAME);
  u2_mode_values.insert("independent", U2_INDEPENDENT);

  static NodeEnum spiral_frame_values;
  /* SPEC §1. */
  spiral_frame_values.insert("camera", SPIRAL_FRAME_CAMERA);
  spiral_frame_values.insert("world", SPIRAL_FRAME_WORLD);
  spiral_frame_values.insert("object", SPIRAL_FRAME_OBJECT);
  spiral_frame_values.insert("smallpaint", SPIRAL_FRAME_SMALLPAINT);

  static NodeEnum output_mode_values;
  /* SPEC §8. */
  output_mode_values.insert("display_referred", OUTPUT_DISPLAY_REFERRED);
  output_mode_values.insert("scene_linear", OUTPUT_SCENE_LINEAR);

  /* SPEC §3, experiment 003: row matches the reference chain's fidelity (0.590 vs 0.589) and
   * parallelizes over rows. The reference itself uses image. */
  SOCKET_ENUM(chain, "Chain", chain_values, CHAIN_ROW);
  /* SPEC §3: 16 is the stylization default of the lane length (experiment 003). */
  SOCKET_INT(lane_length, "Lane Length", 16);
  /* The oracle's --seed default 0 (src/app/smallpaint_oracle.cpp, Options::seed), so default
   * renders match the oracle (T4.4). */
  SOCKET_UINT(seed, "Seed", 0);
  /* SPEC §8: the add-on adds the frame number to seed when this is on. */
  SOCKET_BOOLEAN(seed_per_frame, "Seed per Frame", false);
  /* Experiment 001: the reference preset's pass count. */
  SOCKET_INT(passes, "Passes", 1024);
  /* SPEC §1: the Blender default frame is camera, fixed to the view. */
  SOCKET_ENUM(spiral_frame, "Spiral Frame", spiral_frame_values, SPIRAL_FRAME_CAMERA);
  /* SPEC §1: spiral_rotation defaults to (0, 0, 0). */
  SOCKET_VECTOR(spiral_rotation, "Spiral Rotation", make_float3(0.0f, 0.0f, 0.0f));
  /* SPEC §2, §4: same, so both spiral dimensions use the painterly value. */
  SOCKET_ENUM(u2_mode, "Second Dimension", u2_mode_values, U2_SAME);
  /* SPEC §3: K0 has 22 bits (painterly/kernel/sample/sampler.h, PAINTERLY_K0_BITS). */
  SOCKET_INT(k0_phase_lock_bits, "Phase Lock Bits", 0);
  /* SPEC §4: 0 is smallpaint's unnormalized diffuse direction (exact no-op, pow(L, -0) = 1). */
  SOCKET_FLOAT(alpha, "Alpha", 0.0f);
  /* smallpaint `depth >= 20` (smallpaint_painterly.cpp:190). */
  SOCKET_INT(max_depth, "Max Depth", 20);
  /* Blender albedo semantics: albedos lie in 0…1, so the gain is 1.0. The reference uses 0.1 with
   * smallpaint `cl` colours of 0…12 (SPEC §4). */
  SOCKET_FLOAT(diffuse_gain, "Diffuse Gain", 1.0f);
  /* smallpaint `emission * 2` (smallpaint_painterly.cpp:200). */
  SOCKET_FLOAT(emission_gain, "Emission Gain", 2.0f);
  /* SPEC §6: smallpaint's light is a black diffuse sphere that the path keeps bouncing on. */
  SOCKET_BOOLEAN(continue_after_emitter, "Continue after Emitter", true);
  /* smallpaint's `eps` (smallpaint_painterly.cpp:39). */
  SOCKET_FLOAT(ray_epsilon, "Ray Epsilon", 1e-4f);
  /* SPEC §6: Blender surfaces are double-sided. */
  SOCKET_BOOLEAN(two_sided, "Two-Sided", true);
  /* SPEC §6, §8: at 1, a 120 W point light of radius 0.5 is smallpaint's reference light. */
  SOCKET_FLOAT(emission_scale, "Emission Scale", 1.0f);
  /* SPEC §5: point and spot lights are smallpaint's ghost spheres. */
  SOCKET_BOOLEAN(ghost_lights, "Ghost Lights", true);
  /* SPEC §8: display_referred reproduces smallpaint's clipped 8-bit look. */
  SOCKET_ENUM(output_mode, "Output Mode", output_mode_values, OUTPUT_DISPLAY_REFERRED);
  /* SPEC §8: the identity scale of `L / 255 * exposure` in scene_linear mode. */
  SOCKET_FLOAT(exposure, "Exposure", 1.0f);
  /* SPEC §7: 1/1400 of the fitted image side is smallpaint's 1/700 image-plane units, whose image
   * plane spans 2 units across the image, i.e. 2/7 px at the 400 px reference (experiment 006).
   * Evaluated in float, as every socket default is: float32(1/1400). */
  SOCKET_FLOAT(jitter, "Jitter", 1.0f / 1400.0f);

  return type;
}

void PainterlyIntegrator::device_update(KernelPainterlyIntegrator &kp) const
{
  /* Every field of KernelPainterlyIntegrator except spiral_frame, which PainterlyScene::
   * device_update computes as the 3x3 matrix F (SPEC §1). Floats become doubles with
   * double(float); booleans become 0/1. */
  kp.chain = get_chain();
  kp.lane_length = get_lane_length();
  kp.seed = get_seed();
  kp.u2_mode = get_u2_mode();
  kp.k0_phase_lock_bits = get_k0_phase_lock_bits();
  kp.alpha = double(get_alpha());
  kp.max_depth = get_max_depth();
  kp.diffuse_gain = double(get_diffuse_gain());
  kp.emission_gain = double(get_emission_gain());
  kp.continue_after_emitter = get_continue_after_emitter() ? 1 : 0;
  kp.ray_epsilon = double(get_ray_epsilon());
  kp.two_sided = get_two_sided() ? 1 : 0;
}

const std::vector<PainterlySocketUIInfo> &painterly_integrator_ui_info()
{
  /* One entry per PainterlyIntegrator socket, in socket order, so the two name sets are equal (a
   * test asserts it). The ui_name and description strings are the artist-facing text of T7.1's
   * Step 2 table, the only source that states them. The limits are UI limits, not behaviour: the
   * engine rejects only the three kernel preconditions of SPEC §8 (lane_length < 1,
   * k0_phase_lock_bits outside 0..22, max_depth < 1), which set_integrator checks (T3.15, T3.20).
   * A limit that no source states stays std::nullopt, which maps to Python None. */
  static const std::vector<PainterlySocketUIInfo> info = {
      {"chain",
       std::nullopt,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Chain",
       "How far the painterly counter runs before it restarts. Image: one chain through the whole "
       "render, single-threaded (the smallpaint reference). Row: one chain per row and pass, the "
       "same look as Image rendered in parallel. Lane: one chain per Lane Length pixels of a row, "
       "which reshapes the strokes and leaves a seam column at each lane start",
       "Sampling"},
      {"lane_length",
       1,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Lane Length",
       "Pixels per chain when Chain is Lane. Longer lanes come closer to the Row look. Lane "
       "starts "
       "line up in columns across rows",
       "Sampling"},
      /* seed is a uint; Blender's IntProperty is int32, so the UI maximum is 2^31 - 1 (T4.2). */
      {"seed",
       0,
       2147483647,
       std::nullopt,
       std::nullopt,
       "Seed",
       "Seed of the random numbers for pixel jitter, lobe choice in mixed materials and the "
       "starting "
       "counter of each row or lane chain. With Chain Image, Jitter 0 and Second Dimension Same, "
       "only the lobe choice depends on it",
       "Sampling"},
      {"seed_per_frame",
       std::nullopt,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Seed per Frame",
       "Add the frame number to Seed, so that each frame of an animation gets its own random "
       "numbers",
       "Sampling"},
      {"passes",
       1,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Passes",
       "Samples per pixel. The brush texture is a converged pattern: it emerges as passes "
       "accumulate, then stays in place",
       "Sampling"},
      {"spiral_frame",
       std::nullopt,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Spiral Frame",
       "Orientation of the spiral that steers every diffuse bounce, and so of the strokes. "
       "Camera: "
       "fixed to the view, as in smallpaint. World: fixed in the scene. Object: follows the "
       "rotation "
       "of Spiral Object. Smallpaint: the identity, for scenes authored in smallpaint coordinates",
       "Brush"},
      {"spiral_rotation",
       std::nullopt,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Spiral Rotation",
       "Extra XYZ Euler rotation of the spiral frame. The Smallpaint frame ignores it",
       "Brush"},
      {"u2_mode",
       std::nullopt,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Second Dimension",
       "Same: both coordinates of each diffuse bounce use the painterly value, as smallpaint's "
       "lockstep Halton pair does, which traces the spiral that draws the strokes. Independent: "
       "the "
       "second coordinate is random, which removes the strokes",
       "Brush"},
      {"k0_phase_lock_bits",
       0,
       22,
       std::nullopt,
       std::nullopt,
       "Phase Lock Bits",
       "Clear this many low bits of the starting counter of each row or lane chain, so that "
       "chains "
       "start in step. 0 is off",
       "Brush"},
      {"alpha",
       std::nullopt,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Bounce Normalization",
       "Normalization of the diffuse bounce direction: 0 keeps smallpaint's unnormalized "
       "direction, "
       "1 makes it a unit vector. Raising it dims the light that ghost spheres spread through the "
       "scene, and any value above 0 changes the stroke pattern",
       "Path"},
      {"max_depth",
       1,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Max Depth",
       "Maximum bounces per path. Paths are never cut short at random (no Russian roulette). "
       "Smallpaint uses 20",
       "Path"},
      {"diffuse_gain",
       std::nullopt,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Diffuse Gain",
       "Multiplier on every diffuse bounce. 1 suits Blender albedos from 0 to 1. Smallpaint's own "
       "scene uses 0.1 with colours from 0 to 12",
       "Path"},
      {"emission_gain",
       std::nullopt,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Emission Gain",
       "Multiplier on every emitter, background and sun that a path hits. Smallpaint uses 2",
       "Path"},
      {"continue_after_emitter",
       std::nullopt,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Continue after Emitter",
       "Keep bouncing after a path hits an emitter, as smallpaint does with its black diffuse "
       "light. "
       "Off ends the path there, which strengthens the strokes and dims the scene slightly",
       "Path"},
      {"ray_epsilon",
       std::nullopt,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Ray Epsilon",
       "Self-intersection offset, measured along the unnormalized ray direction (smallpaint's "
       "eps)",
       "Path"},
      {"two_sided",
       std::nullopt,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Two-Sided",
       "Turn triangle shading normals toward the incoming ray, since Blender surfaces are "
       "double-sided. Glass keeps the authored normal",
       "Path"},
      {"emission_scale",
       std::nullopt,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Emission Scale",
       "Factor from Blender light power (W) and sun strength to smallpaint emission. At 1, a 120 "
       "W "
       "point light of radius 0.5 is smallpaint's light. Blender's default 1000 W light clips in "
       "Display Referred output",
       "Lights"},
      {"ghost_lights",
       std::nullopt,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Ghost Lights",
       "Intersect point and spot lights as smallpaint's ghost spheres, which grow with the length "
       "of "
       "the unnormalized bounce and carry most of the light in smallpaint's scene. Off: exact "
       "spheres. Each light can opt out in its Light properties",
       "Lights"},
      {"output_mode",
       std::nullopt,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Output Mode",
       "Display Referred: smallpaint's clipped 8-bit look, which the Standard view transform with "
       "dither 0 reproduces up to rounding. Scene Linear: unclipped radiance times Exposure, for "
       "compositing",
       "Film"},
      {"exposure",
       std::nullopt,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Exposure",
       "Scale of Scene Linear output. Display Referred ignores it",
       "Film"},
      {"jitter",
       0,
       std::nullopt,
       std::nullopt,
       std::nullopt,
       "Jitter",
       "Pixel jitter as a fraction of the camera's fitted image side. 1/1400 is smallpaint's "
       "+/-2/7 "
       "pixel at 400 px. Lower values give crisper, stronger strokes. At 0, with Chain Image and "
       "Second Dimension Same, only the lobe choice depends on Seed. Edge aliasing at small "
       "values "
       "is untested",
       "Film"},
  };
  return info;
}

CCL_NAMESPACE_END
