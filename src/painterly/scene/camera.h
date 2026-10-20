/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* PainterlyCamera: the host side of KernelPainterlyCamera (SPEC §7). The smallpaint camera stores
 * the rotation M_s->cam^T of SPEC §1 with zero translation, so that spiral_frame `camera` gives
 * F = R(spiral_rotation) for it (D19); its rays use neither matrix (SPEC §7). */

#include <array>

#include "painterly/kernel/types.h"
#include "painterly/util/math_double3.h"

CCL_NAMESPACE_BEGIN

/* SPEC §7: the image side the `jitter` socket's fraction is measured against (Blender
 * sensor_fit, resolved by the add-on). */
enum class PainterlyCameraFit { FIT_HORIZONTAL, FIT_VERTICAL };

/* SPEC §1: M_s->cam, the matrix with the columns (0,-1,0), (1,0,0), (0,0,1), row-major. This
 * table is its single definition: the smallpaint camera's camera_to_world is its transpose with
 * translation 0 (D19), derived below, and the spiral frame `camera` (device_scene.cpp) uses it
 * directly. */
constexpr double PAINTERLY_M_S_TO_CAM[9] = {0.0, 1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0};

/* M_s->cam^T as the row-major 3x4 affine [M_s->cam^T | 0] that KernelPainterlyCamera::
 * camera_to_world holds for the smallpaint camera (D19): entry (r, c) of the 3x3 part is
 * M_s->cam[c][r] (the transpose), and the translation column is 0. Derived from the table above,
 * never written out again. */
constexpr std::array<double, 12> painterly_m_s_to_cam_transpose_3x4()
{
  std::array<double, 12> transpose{};
  for (int r = 0; r < 3; r++) {
    for (int c = 0; c < 3; c++) {
      transpose[size_t(PAINTERLY_TRANSFORM_3X4_ROW_STRIDE * r + c)] =
          PAINTERLY_M_S_TO_CAM[3 * c + r];
    }
  }
  return transpose;
}

constexpr std::array<double, 12> PAINTERLY_M_S_TO_CAM_TRANSPOSE_3X4 =
    painterly_m_s_to_cam_transpose_3x4();

class PainterlyCamera {
 public:
  PainterlyCameraType type = PAINTERLY_CAMERA_SMALLPAINT;
  int width = 0, height = 0;
  PainterlyCameraFit fit = PainterlyCameraFit::FIT_HORIZONTAL;
  /* Row-major 4x4 and row-major 3x4, as KernelPainterlyCamera's (painterly/kernel/types.h). */
  double raster_to_camera[16] = {0.0};
  double camera_to_world[12] = {0.0};

  /* The smallpaint camera (SPEC §7, smallpaint_painterly.cpp:171-179). camera_to_world is
   * M_s->cam^T (SPEC §1) with translation 0; raster_to_camera stays zero, because the smallpaint
   * ray is built from row, col and the image size alone. */
  void set_smallpaint(int new_width, int new_height);
  /* A perspective or orthographic camera: raster_to_camera is a row-major 4x4, camera_to_world a
   * row-major 3x4 affine (Blender's matrix_world). `fit` is the fitted image side of SPEC §7. */
  void set_projective(PainterlyCameraType new_type,
                      int new_width,
                      int new_height,
                      const double new_raster_to_camera[16],
                      const double new_camera_to_world[12],
                      PainterlyCameraFit new_fit);

  /* Fills the kernel camera and converts the integrator's `jitter` (a fraction of the fitted image
   * side, SPEC §7) into the units of the camera type:
   *   PAINTERLY_CAMERA_SMALLPAINT: image-plane units, 2.0 * jitter (reference 1/700);
   *   perspective and orthographic: raster pixels, jitter * F, with F = width for FIT_HORIZONTAL
   *   and F = height for FIT_VERTICAL. */
  void device_update(KernelPainterlyCamera &cam, double jitter) const;
};

CCL_NAMESPACE_END
