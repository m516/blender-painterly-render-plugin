/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* The painterly closure collector (card T6.7). Cycles' SVM writes a shader's closures into
 * ShaderData (kernel/svm/closure.h, kernel/closure/alloc.h); this maps them to painterly lobes
 * and emission (SPEC §6, "Materials are lobe mixtures"). It runs after svm_eval_nodes() and
 * reads ShaderData only: no kernel array, no random number.
 *
 * Contract of the evaluation it reads (M6b's painterly_trace_pixel keeps it):
 * - svm_eval_nodes<painterly_svm_surface_feature_mask, SHADER_TYPE_SURFACE> at a surface hit, or
 *   <painterly_svm_background_feature_mask, SHADER_TYPE_SURFACE> on a miss, with
 *   path_visibility 0 and path_flag 0: bsdf_alloc_maybe_emission() then allocates closures
 *   (kernel/closure/alloc.h:96-118) and no PATH_RAY_TERMINATE limits them
 *   (kernel/closure/bsdf_transparent.h:43-48);
 * - ShaderData prepared as surface_shader_eval() prepares it (num_closure 0, num_closure_left
 *   kernel_data.max_closures, lcg_state 0), and SD_BACKFACING clear: the glass lobe decides
 *   inside and outside itself (SPEC §6), so its IOR must be the authored one that Cycles inverts
 *   on back faces (kernel/svm/closure.h:761, 816);
 * - the collector reads the ShaderData that svm_eval_nodes() wrote, never a copy: a microfacet
 *   closure's Fresnel payload is a pointer into that object's closure array
 *   (kernel/closure/alloc.h:34-53). */

#include "kernel/closure/bsdf_microfacet.h"
#include "kernel/closure/bsdf_util.h"
#include "kernel/svm/types.h"
#include "kernel/types.h"

#include "painterly/kernel/types.h"

CCL_NAMESPACE_BEGIN

/* The node feature masks of painterly's shader evaluations. A surface hit uses Cycles' surface
 * mask without ray-traced nodes, which the generated svm_eval_nodes() leaves out (card T6.2);
 * a miss uses the mask of Cycles' background evaluation (kernel/integrator/shade_background.h:86).
 * The surface mask allocates BSDF closures, emission and the extra Voronoi features
 * (kernel/svm/closure.h:239-271, kernel/svm/voronoi.h:1151-1177). */
inline constexpr uint painterly_svm_surface_feature_mask = KERNEL_FEATURE_NODE_MASK_SURFACE &
                                                           ~KERNEL_FEATURE_NODE_RAYTRACE;
inline constexpr uint painterly_svm_background_feature_mask =
    KERNEL_FEATURE_NODE_MASK_SURFACE_BACKGROUND;
static_assert((painterly_svm_surface_feature_mask &
               (KERNEL_FEATURE_NODE_BSDF | KERNEL_FEATURE_NODE_EMISSION |
                KERNEL_FEATURE_NODE_VORONOI_EXTRA)) ==
              (KERNEL_FEATURE_NODE_BSDF | KERNEL_FEATURE_NODE_EMISSION |
               KERNEL_FEATURE_NODE_VORONOI_EXTRA));
static_assert((painterly_svm_background_feature_mask & KERNEL_FEATURE_NODE_EMISSION) != 0);

/* The material of one hit, as one SVM evaluation gives it: the lobe list and emission colour of
 * SPEC §6, the per-hit counterpart of KernelPainterlyMaterial. */
struct PainterlySvmMaterial {
  /* One lobe per collected closure, in closure order (at most MAX_CLOSURE). */
  KernelPainterlyLobe lobes[MAX_CLOSURE];
  int num_lobes; /* >= 1 */
  /* ShaderData::closure_emission_background if SD_EMISSION is set, else zero. */
  double3 emission;
  /* Closures that the policy maps to no lobe (painterly_svm_lobe_kind() returns false). */
  int num_dropped;
};

/* The closure policy (Opus decision, card T6.7): the painterly lobe kind of a Cycles closure
 * type, by Cycles' own closure categories (kernel/svm/types.h:535-574). Returns false for a
 * closure that has no painterly lobe.
 * - Diffuse family and BSSRDF -> LOBE_DIFFUSE. The family is CLOSURE_IS_BSDF_DIFFUSE: diffuse,
 *   Oren-Nayar, Burley, diffuse ramp, sheen, diffuse toon, translucent and rough translucent.
 *   Painterly has no subsurface transport; a BSSRDF becomes its diffuse limit, as Cycles itself
 *   falls back to a diffuse closure for radii below BSSRDF_MIN_RADIUS
 *   (kernel/closure/bssrdf.h:322-336). Translucent light leaves on the far side in Cycles; the
 *   painterly diffuse lobe reflects it on the near side.
 * - Microfacet glass and refraction -> LOBE_GLASS (Snell-only, SPEC §6).
 * - Other transmission (thin-glass transmission, hair transmission) and transparent ->
 *   LOBE_TRANSPARENT: they continue without bending the ray.
 * - The glossy family (CLOSURE_IS_BSDF_GLOSSY) -> LOBE_MIRROR.
 * - Ray portal, holdout and volume closures -> no lobe (dropped). */
ccl_device_inline bool painterly_svm_lobe_kind(const ClosureType type, ccl_private int *kind)
{
  if (CLOSURE_IS_BSDF_DIFFUSE(type) || CLOSURE_IS_BSSRDF(type)) {
    *kind = LOBE_DIFFUSE;
    return true;
  }
  if (CLOSURE_IS_GLASS(type) || CLOSURE_IS_REFRACTION(type)) {
    *kind = LOBE_GLASS;
    return true;
  }
  if (CLOSURE_IS_BSDF_TRANSMISSION(type) || CLOSURE_IS_BSDF_TRANSPARENT(type)) {
    *kind = LOBE_TRANSPARENT;
    return true;
  }
  if (CLOSURE_IS_BSDF_GLOSSY(type)) {
    *kind = LOBE_MIRROR;
    return true;
  }
  return false;
}

/* The reflection colour of a microfacet closure: its Fresnel reflectance at normal incidence,
 * from the Fresnel payload. Painterly mirrors have no Fresnel (SPEC §6), so the payload's colour
 * at cos(theta) = 1 tints the lobe. Thin-film iridescence is not represented.
 * - NONE: the colour is already in the closure weight (Glossy BSDF, kernel/svm/closure.h:679;
 *   multiscatter GGX, bsdf_microfacet.h:1025-1036).
 * - DIELECTRIC (Principled coat): F0 of its IOR.
 * - GENERALIZED_SCHLICK (Principled specular): f0 times the reflection tint. f0 is the end of the
 *   mix that starts at normal incidence (bsdf_microfacet.h:299-326).
 * - F82_TINT (Principled metallic, Metallic BSDF): f0 (bsdf_util.h:178-184 at cosi = 1).
 * - CONDUCTOR (Metallic BSDF, physical): fresnel_conductor() at cosi = 1. */
ccl_device_inline Spectrum painterly_svm_reflection_color(const ccl_private MicrofacetBsdf *bsdf)
{
  switch (bsdf->fresnel_type) {
    case MicrofacetFresnel::DIELECTRIC:
      return make_spectrum(F0_from_ior(bsdf->ior));
    case MicrofacetFresnel::DIELECTRIC_TINT:
      return F0_from_ior(bsdf->ior) *
             ((const ccl_private FresnelDielectricTint *)bsdf->fresnel)->reflection_tint;
    case MicrofacetFresnel::CONDUCTOR:
      return fresnel_conductor(1.0f, ((const ccl_private FresnelConductor *)bsdf->fresnel)->ior);
    case MicrofacetFresnel::GENERALIZED_SCHLICK: {
      const ccl_private FresnelGeneralizedSchlick *fresnel =
          (const ccl_private FresnelGeneralizedSchlick *)bsdf->fresnel;
      return fresnel->f0 * fresnel->reflection_tint;
    }
    case MicrofacetFresnel::F82_TINT:
      return ((const ccl_private FresnelF82Tint *)bsdf->fresnel)->f0;
    default:
      return one_spectrum();
  }
}

/* The transmission colour of a microfacet glass: the payload's transmission tint (Glass BSDF:
 * its Color, kernel/svm/closure.h:823-825; Principled transmission: sqrt(Base Color),
 * kernel/svm/closure.h:405-410). Painterly glass is Snell-only with TIR (SPEC §6): it neither
 * reflects nor weighs by 1 - F, so a white Glass BSDF is smallpaint's glass with unit weight. */
ccl_device_inline Spectrum painterly_svm_transmission_color(const ccl_private MicrofacetBsdf *bsdf)
{
  switch (bsdf->fresnel_type) {
    case MicrofacetFresnel::DIELECTRIC_TINT:
      return ((const ccl_private FresnelDielectricTint *)bsdf->fresnel)->transmission_tint;
    case MicrofacetFresnel::GENERALIZED_SCHLICK:
      return ((const ccl_private FresnelGeneralizedSchlick *)bsdf->fresnel)->transmission_tint;
    default:
      return one_spectrum();
  }
}

/* weight * color per channel, in double. Exact: the product of two floats has at most 48
 * significand bits, and double has 53. */
ccl_device_inline double3 painterly_svm_lobe_weight(const Spectrum weight, const Spectrum color)
{
  return make_double3(double(weight.x) * double(color.x),
                      double(weight.y) * double(color.y),
                      double(weight.z) * double(color.z));
}

/* Maps the closures of `sd` to `material` (see the policy above):
 * - each closure in sd->closure[0, num_closure), in order. CLOSURE_NONE_ID slots are skipped:
 *   Cycles leaves them when a setup moves the weight elsewhere or gives up
 *   (kernel/closure/bssrdf.h:347-350, kernel/closure/bsdf_sheen.h:43-48). Fresnel payloads sit
 *   past num_closure (kernel/closure/alloc.h:34-53) and are never read as closures;
 * - diffuse, transparent and non-microfacet glossy lobes take the closure weight; a microfacet
 *   mirror takes weight * painterly_svm_reflection_color(); a glass lobe takes
 *   weight * painterly_svm_transmission_color() and the closure's IOR;
 * - if no closure gives a lobe, one LOBE_DIFFUSE lobe of weight 0: smallpaint's light is a
 *   diffuse sphere with cl = 0 whose path keeps bouncing (SPEC §6, "Emitters are surfaces"), and
 *   a painterly material has at least one lobe (KernelPainterlyMaterial::num_lobes). */
ccl_device void painterly_svm_collect(const ccl_private ShaderData *ccl_restrict sd,
                                      ccl_private PainterlySvmMaterial *ccl_restrict material)
{
  material->num_lobes = 0;
  material->num_dropped = 0;
  material->emission = (sd->flag & SD_EMISSION) ?
                           make_double3(double(sd->closure_emission_background.x),
                                        double(sd->closure_emission_background.y),
                                        double(sd->closure_emission_background.z)) :
                           make_double3(0.0);

  for (int i = 0; i < sd->num_closure; i++) {
    const ccl_private ShaderClosure *sc = &sd->closure[i];
    if (sc->type == CLOSURE_NONE_ID) {
      continue;
    }

    int kind;
    if (!painterly_svm_lobe_kind(sc->type, &kind)) {
      material->num_dropped++;
      continue;
    }

    ccl_private KernelPainterlyLobe *lobe = &material->lobes[material->num_lobes++];
    lobe->kind = kind;
    lobe->ior = 0.0;
    if (kind == LOBE_GLASS) {
      const ccl_private MicrofacetBsdf *bsdf = (const ccl_private MicrofacetBsdf *)sc;
      lobe->weight = painterly_svm_lobe_weight(sc->weight, painterly_svm_transmission_color(bsdf));
      lobe->ior = double(bsdf->ior);
    }
    else if (kind == LOBE_MIRROR && CLOSURE_IS_BSDF_MICROFACET(sc->type)) {
      const ccl_private MicrofacetBsdf *bsdf = (const ccl_private MicrofacetBsdf *)sc;
      lobe->weight = painterly_svm_lobe_weight(sc->weight, painterly_svm_reflection_color(bsdf));
    }
    else {
      lobe->weight = painterly_svm_lobe_weight(sc->weight, one_spectrum());
    }
  }

  if (material->num_lobes == 0) {
    material->lobes[0].kind = LOBE_DIFFUSE;
    material->lobes[0].weight = make_double3(0.0);
    material->lobes[0].ior = 0.0;
    material->num_lobes = 1;
  }
}

CCL_NAMESPACE_END
