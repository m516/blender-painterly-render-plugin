/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* CONTRACT: Opus-owned. Do not edit without an Opus card. */

#pragma once

/* Kernel data layout: written by painterly/scene/ (device_update), read by painterly/kernel/.
 * Mirrors the role of Cycles' kernel/types.h, at painterly scale. Plain-old-data only: no STL, no
 * virtuals, no allocation, so that the kernel stays portable to GPU devices later. */

#include "painterly/util/types_double3.h"
#include "util/types.h"

CCL_NAMESPACE_BEGIN

/* SPEC §2: purposes of the stateless random number generator. */
enum PainterlyRngPurpose : uint {
  PURPOSE_JITTER_X = 0,
  PURPOSE_JITTER_Y = 1,
  PURPOSE_U2 = 2,
  PURPOSE_CLOSURE = 3,
  PURPOSE_LANE_K0 = 4,
};

/* SPEC §3. */
enum PainterlyChain : int {
  CHAIN_IMAGE = 0, /* One chain over the whole render, continuous across passes (reference). */
  CHAIN_ROW = 1,   /* One chain per (row, pass). */
  CHAIN_LANE = 2,  /* One chain per (lane, pass); lanes are `lane_length` pixels of a row. */
};

/* SPEC §4. */
enum PainterlyU2Mode : int {
  U2_SAME = 0,        /* u2 = u1 = vdc(K): the painterly spiral. */
  U2_INDEPENDENT = 1, /* u2 = rng_unit(PURPOSE_U2 ...). */
};

/* SPEC §7. */
enum PainterlyCameraType : int {
  PAINTERLY_CAMERA_SMALLPAINT = 0, /* smallpaint camcr(): reference scenes only. */
  PAINTERLY_CAMERA_PERSPECTIVE =
      1, /* raster -> camera via raster_to_camera, pinhole at the camera origin. */
  PAINTERLY_CAMERA_ORTHOGRAPHIC = 2,
};

/* Painterly lobes: the closure model. Kinds 1-3 keep smallpaint's material type ids
 * (smallpaint_painterly.cpp:251: 1=diff, 2=spec, 3=refr). SPEC §6. */
enum PainterlyLobeKind : int {
  LOBE_DIFFUSE = 1, /* Spiral diffuse (SPEC §4); weight multiplies the child radiance with cost and
                       diffuse_gain. */
  LOBE_MIRROR = 2,  /* Perfect reflection; weight tints the child radiance. */
  LOBE_GLASS = 3, /* Snell-only refraction, TIR ends the path; weight tints the child radiance. */
  LOBE_TRANSPARENT = 4, /* Straight continuation (d unchanged); weight tints the child radiance. */
};

/* SPEC §5. */
enum PainterlySphereIntersection : int {
  SPHERE_GHOST = 0, /* smallpaint's a=1 quadratic. */
  SPHERE_EXACT = 1, /* Correct quadratic with a = dot(d, d). */
};

enum PainterlyAnalyticType : int {
  ANALYTIC_SPHERE = 0,
  ANALYTIC_PLANE = 1,
};

/* Spot cone emission profile for ghost spheres made from Blender spot lights (SPEC §5).
 * `enabled == 0` means isotropic emission. */
struct KernelPainterlySpotProfile {
  int enabled;
  double3 direction;     /* Unit spot axis (world). */
  double cos_half_angle; /* cos(spot_size / 2). */
  double blend;          /* Blender spot_blend in [0, 1]. */
};

/* Analytic primitives, stored in scene-list order. Order matters: ties resolve to the earlier
 * primitive (smallpaint_painterly.cpp:136-141 uses strict `<`). */
struct KernelPainterlyAnalytic {
  int type;         /* PainterlyAnalyticType */
  int intersection; /* PainterlySphereIntersection (spheres only) */
  int material;     /* Index into materials. */
  int object_id;    /* Value written to the object-id pass. */
  double3 a;        /* sphere: centre;  plane: unit normal n */
  double b;         /* sphere: radius;  plane: d with n.p + d = 0 */
  KernelPainterlySpotProfile spot;
};

/* One lobe of a material. */
struct KernelPainterlyLobe {
  int kind;       /* PainterlyLobeKind */
  double3 weight; /* Diffuse: smallpaint `cl` / albedo. Others: tint (reference scenes use 1). */
  double ior;     /* LOBE_GLASS only. */
};

/* A material is a lobe mixture plus emission. One lobe is chosen per hit with probability
 * proportional to its weight's Rec.709 luminance, using rng(PURPOSE_CLOSURE); the chosen lobe's
 * weight is divided by that probability. With one lobe, p = 1 exactly (bit-identical to
 * smallpaint). With several lobes whose luminances are all zero, the choice is uniform. SPEC §6.
 */
struct KernelPainterlyMaterial {
  int lobe_offset;  /* Into PainterlyGlobalsCPU::lobes. */
  int num_lobes;    /* >= 1 */
  double3 emission; /* Radiance added on hit before emission_gain (smallpaint `emission`). */
  int svm_offset;   /* -1: constant lobes. M6: an SVM program overrides lobes/emission per hit. */
};

struct KernelPainterlyCamera {
  int type;          /* PainterlyCameraType */
  int width, height; /* Pixels. */
  /* SPEC §7, converted from the integrator socket `jitter` (a fraction of the fitted image side)
   * by PainterlyScene::device_update. PAINTERLY_CAMERA_SMALLPAINT: image-plane units, 2 * jitter
   * (reference 1/700). Perspective/orthographic: raster pixels, jitter * fitted side. */
  double jitter;
  /* Row-major. Perspective/orthographic: raster point (col + 0.5 + jx, row + 0.5 + jy, 0, 1) maps
   * to camera space through raster_to_camera; camera_to_world is a 3x4 affine (Blender camera:
   * -Z forward, +Y up). PAINTERLY_CAMERA_SMALLPAINT: rays use neither matrix (SPEC §7);
   * camera_to_world holds the rotation M_s->cam^T with zero translation (SPEC §1), so that
   * spiral_frame `camera` gives F = R(spiral_rotation). */
  double raster_to_camera[16];
  double camera_to_world[12];
};

/* Every knob in SPEC §8 that affects the kernel. Defaults live in painterly/scene/integrator.cpp
 * (NODE_DEFINE). */
struct KernelPainterlyIntegrator {
  int chain;       /* PainterlyChain */
  int lane_length; /* >= 1, CHAIN_LANE only. */
  uint seed;
  int u2_mode;                /* PainterlyU2Mode */
  int k0_phase_lock_bits;     /* q >= 0: K0 &= ~((1u << q) - 1). */
  double alpha;               /* SPEC §4 normalization blend. */
  int max_depth;              /* SPEC §6. */
  double diffuse_gain;        /* SPEC §4. */
  double emission_gain;       /* SPEC §6. */
  int continue_after_emitter; /* SPEC §6, boolean. */
  double ray_epsilon;         /* Parametric self-intersection epsilon (smallpaint eps 1e-4,
                                 painterly.cpp:39). */
  int two_sided; /* SPEC §6: triangle shading normals face the incoming ray (boolean); the glass
                    lobe always gets the unflipped normal. */
  double spiral_frame[9]; /* Row-major F (SPEC §1). */
};

/* Distant light seen by escaping rays as an angular disk (SPEC §6). */
struct KernelPainterlySun {
  double3 direction;     /* Unit vector toward the sun (world). */
  double cos_half_angle; /* cos(angular_diameter / 2); a ray hits iff dot(normalize(d), direction)
                            >= this. */
  double3 radiance;      /* Before emission_gain. */
};

struct KernelPainterlyBackground {
  double3
      radiance; /* Constant world radiance on a miss, before emission_gain. M6: world shader. */
  int num_suns; /* Suns live in PainterlyGlobalsCPU::suns. */
};

struct KernelPainterlyData {
  KernelPainterlyCamera cam;
  KernelPainterlyIntegrator integrator; /* As Cycles' KernelData::integrator. */
  KernelPainterlyBackground background;
};

/* One painterly path's result. */
struct PainterlyPathResult {
  double3 radiance;    /* L for this sample (smallpaint `c`). */
  uint64_t k_consumed; /* Diffuse draws consumed by this path (SPEC §2). */
};

CCL_NAMESPACE_END
