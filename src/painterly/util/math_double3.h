/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* CONTRACT: Opus-owned. Do not edit without an Opus card. */

#pragma once

/* double3 arithmetic with smallpaint `Vec` semantics (smallpaint_painterly.cpp:42-54).
 * Each comment shows the smallpaint expression being reproduced. */

#include <cmath>

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

ccl_device_inline double3 make_double3(const float3 f)
{
  return make_double3(double(f.x), double(f.y), double(f.z));
}

ccl_device_inline float3 make_float3(const double3 d)
{
  return make_float3(float(d.x), float(d.y), float(d.z));
}

CCL_NAMESPACE_END
