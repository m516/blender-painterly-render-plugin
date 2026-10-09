/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* Primary rays for the three camera types (SPEC §7). Every function is a pure function of its
 * arguments: the ray of a pixel depends only on (row, col, pass) and the device scene, so lanes,
 * rows and passes can be evaluated in any order and on any thread.
 *
 * PAINTERLY_CAMERA_SMALLPAINT keeps smallpaint's camcr() expression for expression, so its rays
 * are bit-identical to the oracle (src/app/smallpaint_oracle.cpp). Never "simplify" that
 * arithmetic: a reordered product changes the last bit. */

#include <cmath>

#include "painterly/kernel/globals.h"
#include "painterly/kernel/sample/sampler.h"
#include "painterly/kernel/smallpaint.h"
#include "painterly/util/math_double3.h"

CCL_NAMESPACE_BEGIN

/* Centre of the raster pixel [i, i + 1) in raster coordinates. This is a mathematical definition,
 * not a tuning value: the ray goes through the middle of the pixel. */
constexpr double PAINTERLY_RASTER_PIXEL_CENTRE = 0.5;

/* camera_to_world is a row-major 3x4 affine matrix [R | t] (types.h). This returns R * v. */
ccl_device_inline double3 painterly_camera_rotate(const KernelPainterlyCamera &cam,
                                                  const double3 v)
{
  const double *m = cam.camera_to_world;
  return make_double3(m[0] * v.x + m[1] * v.y + m[2] * v.z,
                      m[4] * v.x + m[5] * v.y + m[6] * v.z,
                      m[8] * v.x + m[9] * v.y + m[10] * v.z);
}

/* The translation t of camera_to_world: the world position of the camera origin. */
ccl_device_inline double3 painterly_camera_translation(const KernelPainterlyCamera &cam)
{
  const double *m = cam.camera_to_world;
  return make_double3(m[3], m[7], m[11]);
}

/* Camera-space point Pc on the image plane for the raster point (raster_x, raster_y), SPEC §7:
 * p = raster_to_camera * (raster_x, raster_y, 0, 1), Pc = p.xyz / p.w. The z input is 0 and the w
 * input is 1, so their products are m[2] * 0 and m[3] * 1, which are written as the bare m[3]. */
ccl_device_inline double3 painterly_camera_raster_to_camera(const KernelPainterlyCamera &cam,
                                                            const double raster_x,
                                                            const double raster_y)
{
  const double *m = cam.raster_to_camera;
  const double px = m[0] * raster_x + m[1] * raster_y + m[3];
  const double py = m[4] * raster_x + m[5] * raster_y + m[7];
  const double pz = m[8] * raster_x + m[9] * raster_y + m[11];
  const double pw = m[12] * raster_x + m[13] * raster_y + m[15];
  return make_double3(px / pw, py / pw, pz / pw);
}

/* One axis of the jitter (SPEC §7): rng_signed(seed, purpose, 0, row, col, pass) * jitter, in the
 * units of `jitter`. The caller picks PURPOSE_JITTER_X or PURPOSE_JITTER_Y. */
ccl_device_inline double painterly_camera_jitter_axis(const uint seed,
                                                      const uint purpose,
                                                      const int row,
                                                      const int col,
                                                      const int pass,
                                                      const double jitter)
{
  return painterly_rng_signed(seed, purpose, 0, uint(row), uint(col), uint(pass)) * jitter;
}

/* smallpaint's camcr(x, y) with x = row and y = col (smallpaint_painterly.cpp:171-179), then the
 * image-plane jitter of smallpaint_painterly.cpp:291-292, and d = normalize(cam - o) with o = 0
 * (:292-293). KernelPainterlyCamera::jitter holds the jitter in image-plane units. */
ccl_device_inline PainterlyRay painterly_camera_smallpaint_ray(const KernelPainterlyData &data,
                                                               const int row,
                                                               const int col,
                                                               const int pass,
                                                               const bool jittered)
{
  const KernelPainterlyCamera &cam = data.cam;
  const double w = cam.width;
  const double h = cam.height;
  /* smallpaint_painterly.cpp:173-174. fovx and fovy are float, as in smallpaint. */
  const float fovx = SMALLPAINT_PI / 4;
  const float fovy = (h / w) * fovx;
  const double x = row;
  const double y = col;
  /* smallpaint_painterly.cpp:176-178. tan is taken in double on the float-rounded angle (SPEC §7).
   * The -1.0 is the image plane z = -1: smallpaint's camera looks down -z. */
  double3 cam_point = make_double3(((2 * x - w) / w) * std::tan(double(fovx)),
                                   ((2 * y - h) / h) * std::tan(double(fovy)),
                                   -1.0);
  if (jittered) {
    const uint seed = data.integrator.seed;
    cam_point.x = cam_point.x +
                  painterly_camera_jitter_axis(seed, PURPOSE_JITTER_X, row, col, pass, cam.jitter);
    cam_point.y = cam_point.y +
                  painterly_camera_jitter_axis(seed, PURPOSE_JITTER_Y, row, col, pass, cam.jitter);
  }
  /* smallpaint's ray origin is Vec(0, 0, 0) (smallpaint_painterly.cpp:292). */
  const double3 origin = make_double3(0.0);
  return PainterlyRay{origin, normalize(cam_point - origin)};
}

/* Primary ray for pixel (row, col) of `pass` (SPEC §7). jittered = false gives the unjittered ray
 * that the object-id pass uses. Directions are unit length. */
ccl_device_inline PainterlyRay
painterly_camera_generate_ray(PainterlyGlobals kg, int row, int col, int pass, bool jittered)
{
  const KernelPainterlyData &data = *kg->data;
  const KernelPainterlyCamera &cam = data.cam;
  if (cam.type == PAINTERLY_CAMERA_SMALLPAINT) {
    return painterly_camera_smallpaint_ray(data, row, col, pass, jittered);
  }

  /* Raster point (col + 0.5 + jx, row + 0.5 + jy). jx and jy are in raster pixels (SPEC §7), and
   * are zero when the ray is not jittered. */
  double jx = 0.0;
  double jy = 0.0;
  if (jittered) {
    const uint seed = data.integrator.seed;
    jx = painterly_camera_jitter_axis(seed, PURPOSE_JITTER_X, row, col, pass, cam.jitter);
    jy = painterly_camera_jitter_axis(seed, PURPOSE_JITTER_Y, row, col, pass, cam.jitter);
  }
  const double raster_x = col + PAINTERLY_RASTER_PIXEL_CENTRE + jx;
  const double raster_y = row + PAINTERLY_RASTER_PIXEL_CENTRE + jy;
  const double3 point_cam = painterly_camera_raster_to_camera(cam, raster_x, raster_y);

  if (cam.type == PAINTERLY_CAMERA_PERSPECTIVE) {
    /* Pinhole at the camera origin: the ray leaves the origin along R * normalize(Pc). */
    return PainterlyRay{painterly_camera_translation(cam),
                        normalize(painterly_camera_rotate(cam, normalize(point_cam)))};
  }

  /* Orthographic (PAINTERLY_CAMERA_ORTHOGRAPHIC): the ray starts at (Pc.x, Pc.y, 0) and points
   * along the camera's forward axis -Z (SPEC §1). */
  const double3 origin_cam = make_double3(point_cam.x, point_cam.y, 0.0);
  const double3 forward_cam = make_double3(0.0, 0.0, -1.0);
  return PainterlyRay{painterly_camera_rotate(cam, origin_cam) + painterly_camera_translation(cam),
                      normalize(painterly_camera_rotate(cam, forward_cam))};
}

CCL_NAMESPACE_END
