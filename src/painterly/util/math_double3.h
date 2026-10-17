/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* CONTRACT: Opus-owned. Do not edit without an Opus card. */

#pragma once

/* double3 arithmetic. The operators keep smallpaint `Vec` semantics
 * (smallpaint_painterly.cpp:43-55), and each of their comments shows the smallpaint expression
 * being reproduced. The 3x3/3x4 transform helpers and the host-only painterly_normal_matrix follow
 * them. */

#include <cmath>
#include <stdexcept>

#include "painterly/util/types_double3.h"
#include "util/defines.h"
#include "util/types_float3.h"

CCL_NAMESPACE_BEGIN

/* Vec operator+(const Vec &b) const { return Vec(x + b.x, y + b.y, z + b.z); } */
ccl_device_inline double3 operator+(const double3 a, const double3 b)
{
  return make_double3(a.x + b.x, a.y + b.y, a.z + b.z);
}

/* Vec operator-(const Vec &b) const */
ccl_device_inline double3 operator-(const double3 a, const double3 b)
{
  return make_double3(a.x - b.x, a.y - b.y, a.z - b.z);
}

/* Vec operator*(double b) const { return Vec(x*b, y*b, z*b); } */
ccl_device_inline double3 operator*(const double3 a, const double s)
{
  return make_double3(a.x * s, a.y * s, a.z * s);
}

/* Vec operator/(double b) const { return Vec(x / b, y / b, z / b); } */
ccl_device_inline double3 operator/(const double3 a, const double s)
{
  return make_double3(a.x / s, a.y / s, a.z / s);
}

/* Vec mult(const Vec &b) const — component-wise product (Cycles spelling: operator* on two
 * vectors). */
ccl_device_inline double3 operator*(const double3 a, const double3 b)
{
  return make_double3(a.x * b.x, a.y * b.y, a.z * b.z);
}

/* double dot(const Vec &b) const { return x*b.x + y*b.y + z*b.z; } */
ccl_device_inline double dot(const double3 a, const double3 b)
{
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

/* double length() { return sqrt(x*x + y*y + z*z); } */
ccl_device_inline double len(const double3 a)
{
  return std::sqrt(a.x * a.x + a.y * a.y + a.z * a.z);
}

/* Vec& norm() { return *this = *this * (1 / sqrt(x*x + y*y + z*z)); } — reciprocal, then multiply.
 */
ccl_device_inline double3 normalize(const double3 a)
{
  return a * (1 / std::sqrt(a.x * a.x + a.y * a.y + a.z * a.z));
}

/* Vec operator%(Vec &b) { return Vec(y*b.z - z*b.y, z*b.x - x*b.z, x*b.y - y*b.x); } */
ccl_device_inline double3 cross(const double3 a, const double3 b)
{
  return make_double3(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x);
}

/* Row-major 3x3 matrix times vector (spiral frame F, SPEC §1). For F = identity this is exact:
 * 1*x + 0*y + 0*z == x in IEEE arithmetic. */
ccl_device_inline double3 transform_direction_3x3(const double m[9], const double3 v)
{
  return make_double3(m[0] * v.x + m[1] * v.y + m[2] * v.z,
                      m[3] * v.x + m[4] * v.y + m[5] * v.z,
                      m[6] * v.x + m[7] * v.y + m[8] * v.z);
}

/* A row-major 3x4 affine transform [A | t] stores four values per row: the three entries of the
 * row of the 3x3 part A, then the translation t. A layout definition: KernelPainterlyCamera's
 * camera_to_world (double) and the float object_to_world of every object (painterly/bvh/embree.h)
 * use it, as Blender's matrix_world rows and Embree's RTC_FORMAT_FLOAT3X4_ROW_MAJOR do. */
constexpr int PAINTERLY_TRANSFORM_3X4_ROW_STRIDE = 4;

/* A * v for the 3x3 part A of a row-major 3x4 affine transform m: a direction, so the translation
 * is not added. Row by row, x then y then z. */
ccl_device_inline double3 painterly_transform_direction_3x4(const double m[12], const double3 v)
{
  const double *r0 = m;
  const double *r1 = m + PAINTERLY_TRANSFORM_3X4_ROW_STRIDE;
  const double *r2 = m + 2 * PAINTERLY_TRANSFORM_3X4_ROW_STRIDE;
  return make_double3(r0[0] * v.x + r0[1] * v.y + r0[2] * v.z,
                      r1[0] * v.x + r1[1] * v.y + r1[2] * v.z,
                      r2[0] * v.x + r2[1] * v.y + r2[2] * v.z);
}

/* The translation t of a row-major 3x4 affine transform m: the last entry of each row. */
ccl_device_inline double3 painterly_transform_translation_3x4(const double m[12])
{
  constexpr int t = PAINTERLY_TRANSFORM_3X4_ROW_STRIDE - 1;
  return make_double3(m[t],
                      m[PAINTERLY_TRANSFORM_3X4_ROW_STRIDE + t],
                      m[2 * PAINTERLY_TRANSFORM_3X4_ROW_STRIDE + t]);
}

/* The normal matrix N = (A^-1)^T of the 3x3 part A of a row-major 3x4 affine object_to_world,
 * row-major, in double: out[3 r + c] = N[r][c]. A normal n maps to world space as N n. Then
 * dot(N n, A d) = dot(n, d) for every direction d, so a normal keeps its side of the surface, also
 * under a mirroring A (det(A) < 0). The cofactor form N = cofactor(A) / det(A) avoids forming the
 * inverse. N n is not normalized.
 *
 * The one normal matrix of a triangle hit (TQ.1 F25): painterly_embree_scene_create computes it
 * per object and painterly_embree_intersect_closest maps Embree's object-space Ng with it; the
 * scene stores it as KernelPainterlyObject::normal_to_world for the corner normals
 * (painterly_triangle_shading_normal). The same float object_to_world gives both the same bits.
 *
 * Host code only (not ccl_device): throws std::invalid_argument when det(A) == 0, because a normal
 * cannot be mapped through a singular A. */
inline void painterly_normal_matrix(const float object_to_world[12], double out[9])
{
  double a[3][3];
  for (int r = 0; r < 3; ++r) {
    for (int c = 0; c < 3; ++c) {
      a[r][c] = static_cast<double>(object_to_world[PAINTERLY_TRANSFORM_3X4_ROW_STRIDE * r + c]);
    }
  }

  /* cofactor(r, c) = (-1)^(r+c) times the minor of element (r, c). */
  const double c00 = a[1][1] * a[2][2] - a[1][2] * a[2][1];
  const double c01 = a[1][2] * a[2][0] - a[1][0] * a[2][2];
  const double c02 = a[1][0] * a[2][1] - a[1][1] * a[2][0];
  const double c10 = a[0][2] * a[2][1] - a[0][1] * a[2][2];
  const double c11 = a[0][0] * a[2][2] - a[0][2] * a[2][0];
  const double c12 = a[0][1] * a[2][0] - a[0][0] * a[2][1];
  const double c20 = a[0][1] * a[1][2] - a[0][2] * a[1][1];
  const double c21 = a[0][2] * a[1][0] - a[0][0] * a[1][2];
  const double c22 = a[0][0] * a[1][1] - a[0][1] * a[1][0];

  /* Expansion of det(A) along row 0. */
  const double det = a[0][0] * c00 + a[0][1] * c01 + a[0][2] * c02;
  if (det == 0.0) {
    throw std::invalid_argument("painterly_normal_matrix: singular object_to_world");
  }
  out[0] = c00 / det;
  out[1] = c01 / det;
  out[2] = c02 / det;
  out[3] = c10 / det;
  out[4] = c11 / det;
  out[5] = c12 / det;
  out[6] = c20 / det;
  out[7] = c21 / det;
  out[8] = c22 / det;
}

ccl_device_inline double3 make_double3(const float3 f)
{
  return make_double3(double(f.x), double(f.y), double(f.z));
}

ccl_device_inline float3 make_float3(const double3 d)
{
  return make_float3(float(d.x), float(d.y), float(d.z));
}

CCL_NAMESPACE_END
