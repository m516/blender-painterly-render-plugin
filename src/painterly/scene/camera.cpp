/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "painterly/scene/camera.h"

CCL_NAMESPACE_BEGIN

void PainterlyCamera::set_smallpaint(const int new_width, const int new_height)
{
  type = PAINTERLY_CAMERA_SMALLPAINT;
  width = new_width;
  height = new_height;
  for (double &m : raster_to_camera) {
    m = 0.0;
  }
  /* SPEC §1: M_s->cam has the columns (0,-1,0), (1,0,0), (0,0,1), so its transpose has the rows
   * (0,-1,0), (1,0,0), (0,0,1). D19: the translation is 0. The transpose is derived from
   * PAINTERLY_M_S_TO_CAM (camera.h), the matrix's single definition. */
  for (int i = 0; i < 12; i++) {
    camera_to_world[i] = PAINTERLY_M_S_TO_CAM_TRANSPOSE_3X4[size_t(i)];
  }
}

void PainterlyCamera::set_projective(const PainterlyCameraType new_type,
                                     const int new_width,
                                     const int new_height,
                                     const double new_raster_to_camera[16],
                                     const double new_camera_to_world[12],
                                     const PainterlyCameraFit new_fit)
{
  type = new_type;
  width = new_width;
  height = new_height;
  fit = new_fit;
  for (int i = 0; i < 16; i++) {
    raster_to_camera[i] = new_raster_to_camera[i];
  }
  for (int i = 0; i < 12; i++) {
    camera_to_world[i] = new_camera_to_world[i];
  }
}

void PainterlyCamera::device_update(KernelPainterlyCamera &cam, const double jitter) const
{
  cam.type = type;
  cam.width = width;
  cam.height = height;
  if (type == PAINTERLY_CAMERA_SMALLPAINT) {
    /* SPEC §7: the smallpaint camera's jitter is in image-plane units, and the socket's fraction
     * of the fitted image side becomes 2 * jitter. Exact in binary floating point. */
    cam.jitter = 2.0 * jitter;
  }
  else {
    const double fitted_side = (fit == PainterlyCameraFit::FIT_HORIZONTAL) ? double(width) :
                                                                             double(height);
    cam.jitter = jitter * fitted_side;
  }
  for (int i = 0; i < 16; i++) {
    cam.raster_to_camera[i] = raster_to_camera[i];
  }
  for (int i = 0; i < 12; i++) {
    cam.camera_to_world[i] = camera_to_world[i];
  }
}

CCL_NAMESPACE_END
