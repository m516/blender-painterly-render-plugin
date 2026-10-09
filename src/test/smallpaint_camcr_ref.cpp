// SPDX-License-Identifier: GPL-3.0-or-later
// Oracle reference for test_camera.cpp (T3.8). It holds smallpaint_oracle.cpp's camcr() (oracle
// change 12 in src/app/CHANGES.md, lines 247-255) and the jitter lines of its take_sample()
// (oracle change 14, lines 365-366), with the oracle's headers and `using namespace std;`. The
// oracle's globals `width`, `height` and `g_jitter` are a namespace variable pair and a parameter
// here. clang-format is off for the copied code, so it stays byte-identical to the source, tabs
// included.

// clang-format off
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <limits.h>
#include <vector>
#include <string>
#include <unordered_map>
#include <algorithm>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <filesystem>
#include <thread>
// clang-format on

namespace smallpaint_camcr_ref {

// The oracle's rng_signed and purpose values, included in this namespace as test_sampler.cpp does.
#include "app/smallpaint_oracle_hash.h"

// clang-format off
using namespace std;

#define PI 3.1415926536

// smallpaint's Vec, copied from smallpaint_oracle.cpp:65-77.
struct Vec {
	double x, y, z;
	Vec(double x0 = 0, double y0 = 0, double z0 = 0) { x = x0; y = y0; z = z0; }
	Vec operator+(const Vec &b) const { return Vec(x + b.x, y + b.y, z + b.z); }
	Vec operator-(const Vec &b) const { return Vec(x - b.x, y - b.y, z - b.z); }
	Vec operator*(double b) const { return Vec(x*b, y*b, z*b); }
	Vec operator/(double b) const { return Vec(x / b, y / b, z / b); }
	Vec mult(const Vec &b) const { return Vec(x*b.x, y*b.y, z*b.z); }
	Vec& norm() { return *this = *this * (1 / sqrt(x*x + y*y + z*z)); }
	double length() { return sqrt(x*x + y*y + z*z); }
	double dot(const Vec &b) const { return x*b.x + y*b.y + z*b.z; }
	Vec operator%(Vec &b) { return Vec(y*b.z - z*b.y, z*b.x - x*b.z, x*b.y - y*b.x); }
};

// The oracle's image size, set by primary_ray() before camcr() is called.
int width, height;

// smallpaint_oracle.cpp:247-255 (oracle change 12): tan is taken in double.
Vec camcr(const double x, const double y) {
	double w = width;
	double h = height;
	float fovx = PI / 4;
	float fovy = (h / w)*fovx;
	return Vec(((2 * x - w) / w)*tan((double)fovx),
		((2 * y - h) / h)*tan((double)fovy),
			   -1.0);
}
// clang-format on

// The primary ray of pixel (row, col) in pass `pass`, as the oracle forms it. With `jittered`, it
// is take_sample()'s camera (smallpaint_oracle.cpp:363-367), with `jitter` in place of g_jitter.
// Without it, it is compute_object_ids()'s camera (smallpaint_oracle.cpp:383-385). The origin is
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
