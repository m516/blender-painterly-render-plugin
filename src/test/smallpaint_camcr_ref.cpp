/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

// Oracle reference for test_camera.cpp (T3.8): the primary ray of the oracle's take_sample() and
// compute_object_ids(). It calls the oracle's camcr() and sets the oracle's image size, both
// copied verbatim in smallpaint_ref.h (namespace smallpaint_oracle), and its jitter is the
// oracle's rng_signed (src/app/smallpaint_oracle_hash.h). The file is a translation unit of its
// own, so the reference is compiled apart from the kernel camera code that test_camera.cpp checks.

#include <cstdint>

#include "smallpaint_ref.h"

namespace smallpaint_camcr_ref {

// The oracle's names (Vec, width, height, camcr, rng_signed, PURPOSE_JITTER_X/Y), so that the body
// of primary_ray() reads as the oracle's lines do.
using namespace smallpaint_oracle;

// The primary ray of pixel (row, col) in pass `pass`, as the oracle forms it. With `jittered`, it
// is take_sample()'s camera (smallpaint_oracle.cpp:371-375), with `jitter` in place of g_jitter.
// Without it, it is compute_object_ids()'s camera (smallpaint_oracle.cpp:391-393). The origin is
// Vec(0, 0, 0), and the direction is (cam - origin).norm().
void primary_ray(int image_width,
                 int image_height,
                 std::uint32_t seed,
                 double jitter,
                 bool jittered,
                 int row,
                 int col,
                 int pass,
                 double origin[3],
                 double direction[3])
{
  width = image_width;
  height = image_height;
  const Vec o(0, 0, 0);
  Vec cam = camcr(row, col);
  if (jittered) {
    cam.x = cam.x +
            rng_signed(seed, PURPOSE_JITTER_X, 0, (uint32_t)row, (uint32_t)col, (uint32_t)pass) *
                jitter;
    cam.y = cam.y +
            rng_signed(seed, PURPOSE_JITTER_Y, 0, (uint32_t)row, (uint32_t)col, (uint32_t)pass) *
                jitter;
  }
  const Vec d = (cam - o).norm();
  origin[0] = o.x;
  origin[1] = o.y;
  origin[2] = o.z;
  direction[0] = d.x;
  direction[1] = d.y;
  direction[2] = d.z;
}

}  // namespace smallpaint_camcr_ref
