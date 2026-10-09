/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* The smallpaint GUI reference scene (SPEC §9), built by hand as kernel data with the knob values
 * of the smallpaint reference (SPEC §7, §8). test_path.cpp (T3.11) and test_path_trace.cpp (T3.12)
 * both include this header in the one painterly_tests executable. It therefore defines only types
 * and inline functions: no namespace-scope variable and no non-inline function. */

#include <vector>

#include "painterly/kernel/globals.h"
#include "painterly/kernel/types.h"
#include "painterly/util/math_double3.h"

CCL_NAMESPACE_BEGIN

/* Owns every array that its PainterlyGlobalsCPU points to, so kg() stays valid for the object's
 * lifetime. The object is neither copyable nor movable, because globals points into it. */
struct SmallpaintSceneFixture {
  /* A 32 px image. The reference image is 400 px (SPEC §9). The tests only need a small one. */
  static constexpr int WIDTH = 32;
  static constexpr int HEIGHT = 32;

  /* SPEC §9 table: object ids are the positions in the object list, and so are the material
   * indices of this fixture (one material per object). */
  static constexpr int LIGHT_OBJECT_ID = 9;
  /* SPEC §9: light emission 120 (painterly.cpp:262). */
  static constexpr double LIGHT_EMISSION = 120.0;
  /* SPEC §9: glass IOR 1.5 (GUI default, refr_index). */
  static constexpr double GLASS_IOR = 1.5;

  /* SPEC §8 knob values of the reference. The gains and epsilon are written as the card gives
   * them: diffuse_gain = double(0.1f), ray_epsilon = double(1e-4f). The smallpaint sources use the
   * double literals 0.1 and 1e-4 (smallpaint_painterly.cpp:39 and :209-211). */
  static constexpr double DIFFUSE_GAIN = double(0.1f);
  static constexpr double EMISSION_GAIN = 2.0; /* smallpaint_painterly.cpp:200 (* 2) */
  static constexpr double RAY_EPSILON = double(1e-4f);
  static constexpr int MAX_DEPTH = 20; /* smallpaint_painterly.cpp:190 */
  /* SPEC §7, image-plane units. The knob 1/1400 is a fraction of the image side (T3.13), and the
   * smallpaint camera works in image-plane units, so the value is 2 * jitter (reference 1/700,
   * painterly.cpp:291-292). */
  static constexpr double JITTER = 2.0 * double(float(1.0 / 1400));

  KernelPainterlyData data{};
  PainterlyGlobalsCPU globals{};
  std::vector<KernelPainterlyAnalytic> analytic;
  std::vector<KernelPainterlyMaterial> materials;
  std::vector<KernelPainterlyLobe> lobes;
  std::vector<KernelPainterlySun> suns;
  std::vector<KernelPainterlyObject> objects;
  std::vector<KernelPainterlyMesh> meshes;

  /* chain: a PainterlyChain value (SPEC §3). lane_length: >= 1, read for CHAIN_LANE only. */
  SmallpaintSceneFixture(const int chain, const int lane_length)
  {
    set_knobs(chain, lane_length);
    build_scene();

    globals.data = &data;
    globals.analytic = analytic.data();
    globals.num_analytic = int(analytic.size());
    globals.materials = materials.data();
    globals.num_materials = int(materials.size());
    globals.lobes = lobes.data();
    globals.num_lobes = int(lobes.size());
    globals.suns = suns.data();
    globals.objects = objects.data();
    globals.num_objects = int(objects.size());
    globals.meshes = meshes.data();
    globals.num_meshes = int(meshes.size());
    /* The reference scene has no triangles, so there is no BVH and no triangle arrays. */
    globals.tri_material = nullptr;
    globals.tri_vertices = nullptr;
    globals.tri_corner_normals = nullptr;
    globals.bvh = nullptr;
  }

  SmallpaintSceneFixture(const SmallpaintSceneFixture &) = delete;
  SmallpaintSceneFixture &operator=(const SmallpaintSceneFixture &) = delete;
  SmallpaintSceneFixture(SmallpaintSceneFixture &&) = delete;
  SmallpaintSceneFixture &operator=(SmallpaintSceneFixture &&) = delete;

  PainterlyGlobals kg() const
  {
    return &globals;
  }

  /* The integrator and camera of the smallpaint reference (SPEC §7, §8). */
  void set_knobs(const int chain, const int lane_length)
  {
    data.cam.type = PAINTERLY_CAMERA_SMALLPAINT;
    data.cam.width = WIDTH;
    data.cam.height = HEIGHT;
    data.cam.jitter = JITTER;
    /* Unused by the smallpaint camera, which takes neither matrix (SPEC §7). Only the rotation
     * M_s->cam^T of SPEC §1 is stored, with zero translation: rows (0,-1,0), (1,0,0), (0,0,1). */
    for (double &m : data.cam.raster_to_camera) {
      m = 0.0;
    }
    const double camera_to_world[12] = {
        0.0, -1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0};
    for (int i = 0; i < 12; i++) {
      data.cam.camera_to_world[i] = camera_to_world[i];
    }

    data.integrator.chain = chain;
    data.integrator.lane_length = lane_length;
    data.integrator.seed = 0;
    data.integrator.u2_mode = U2_SAME;
    data.integrator.k0_phase_lock_bits = 0;
    data.integrator.alpha = 0.0; /* SPEC §4: pow(L, -0) = 1 exactly. */
    data.integrator.max_depth = MAX_DEPTH;
    data.integrator.diffuse_gain = DIFFUSE_GAIN;
    data.integrator.emission_gain = EMISSION_GAIN;
    data.integrator.continue_after_emitter = 1;
    data.integrator.ray_epsilon = RAY_EPSILON;
    data.integrator.two_sided = 1;
    /* SPEC §1 smallpaint: F = I. A zero F would give d = N. */
    const double identity[9] = {1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0};
    for (int i = 0; i < 9; i++) {
      data.integrator.spiral_frame[i] = identity[i];
    }

    data.background.radiance = make_double3(0.0);
    data.background.num_suns = 0;
  }

  /* Appends a material with one constant lobe, and returns its index. svm_offset = -1 (constant
   * lobes, no SVM program). */
  int add_material(const int lobe_kind,
                   const double3 weight,
                   const double ior,
                   const double3 emission)
  {
    KernelPainterlyLobe lobe{};
    lobe.kind = lobe_kind;
    lobe.weight = weight;
    lobe.ior = ior;
    lobes.push_back(lobe);

    KernelPainterlyMaterial material{};
    material.lobe_offset = int(lobes.size()) - 1;
    material.num_lobes = 1;
    material.emission = emission;
    material.svm_offset = -1;
    materials.push_back(material);
    return int(materials.size()) - 1;
  }

  /* A ghost sphere (SPEC §5; smallpaint's quadratic). Its object id is its list position. */
  void add_sphere(const int material, const double3 centre, const double radius)
  {
    KernelPainterlyAnalytic prim{};
    prim.type = ANALYTIC_SPHERE;
    prim.intersection = SPHERE_GHOST;
    prim.material = material;
    prim.object_id = int(analytic.size());
    prim.a = centre;
    prim.b = radius;
    analytic.push_back(prim);
  }

  /* A plane n.p + d = 0 with unit normal n (SPEC §9). Its object id is its list position. */
  void add_plane(const int material, const double3 normal, const double d)
  {
    KernelPainterlyAnalytic prim{};
    prim.type = ANALYTIC_PLANE;
    prim.material = material;
    prim.object_id = int(analytic.size());
    prim.a = normal;
    prim.b = d;
    analytic.push_back(prim);
  }

  /* The ten objects of SPEC §9, in list order. Materials are added in the same order, so the
   * material of object i is material i. */
  void build_scene()
  {
    const double3 white = make_double3(1.0);
    const double3 black = make_double3(0.0);
    const int middle_sphere = add_material(LOBE_MIRROR, white, 0.0, black);
    const int right_sphere = add_material(LOBE_GLASS, white, GLASS_IOR, black);
    const int left_sphere = add_material(LOBE_DIFFUSE, make_double3(4.0, 4.0, 12.0), 0.0, black);
    const int bottom = add_material(LOBE_DIFFUSE, make_double3(6.0), 0.0, black);
    const int back = add_material(LOBE_DIFFUSE, make_double3(6.0), 0.0, black);
    const int left = add_material(LOBE_DIFFUSE, make_double3(10.0, 2.0, 2.0), 0.0, black);
    const int right = add_material(LOBE_DIFFUSE, make_double3(2.0, 10.0, 2.0), 0.0, black);
    const int ceiling = add_material(LOBE_DIFFUSE, make_double3(6.0), 0.0, black);
    const int front = add_material(LOBE_DIFFUSE, make_double3(6.0), 0.0, black);
    const int light = add_material(LOBE_DIFFUSE, black, 0.0, make_double3(LIGHT_EMISSION));

    add_sphere(middle_sphere, make_double3(1.45, -0.75, -4.4), 1.05); /* 0 */
    add_sphere(right_sphere, make_double3(2.05, 2.0, -3.7), 0.5);     /* 1 */
    add_sphere(left_sphere, make_double3(1.95, -1.75, -3.1), 0.6);    /* 2 */
    add_plane(bottom, make_double3(-1.0, 0.0, 0.0), 2.5);             /* 3 */
    add_plane(back, make_double3(0.0, 0.0, 1.0), 5.5);                /* 4 */
    add_plane(left, make_double3(0.0, 1.0, 0.0), 2.75);               /* 5 */
    add_plane(right, make_double3(0.0, -1.0, 0.0), 2.75);             /* 6 */
    add_plane(ceiling, make_double3(1.0, 0.0, 0.0), 3.0);             /* 7 */
    add_plane(front, make_double3(0.0, 0.0, -1.0), 0.5);              /* 8 */
    add_sphere(light, make_double3(-1.9, 0.0, -3.0), 0.5);            /* 9 */
  }
};

CCL_NAMESPACE_END
