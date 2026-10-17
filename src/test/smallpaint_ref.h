/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* The reference code of the bitwise tests, in one copy (TQ.1 F16): smallpaint's PI, eps, Vec,
 * Ray, Obj, Plane, Sphere, Halton and hemisphere() in namespace smallpaint_ref, and the oracle's
 * hash, image size, exact sphere test and camcr() in namespace smallpaint_oracle. smallpaint is
 * MIT (LICENSES/MIT-smallpaint.txt, THIRD_PARTY_NOTICES.md).
 *
 * Verbatim blocks. Each block between "// verbatim <file>:<lines>" and "// end verbatim" is
 * byte-identical to every range its marker lines cite, apart from the line endings: smallpaint's
 * sources are CRLF, and this file is LF. clang-format is off for the blocks, so their tabs stay.
 * A block that cites two ranges also records that its two sources agree there: the oracle's Vec,
 * Ray, Obj and Plane are smallpaint's (src/app/CHANGES.md item 7).
 * tests/core/test_smallpaint_ref.py checks every cited range.
 *
 * Linkage. Several test files of the one painterly_tests executable include this header, and the
 * copied hemisphere() and camcr() are not inline, and width and height are namespace-scope
 * variables. So every copy lives in an unnamed namespace, which gives it internal linkage in each
 * translation unit, while the copied text stays as it is. The helpers at the end, which convert
 * between these types and painterly's, share the unnamed namespace of bitwise.h for the same
 * reason. */

/* <math.h> declares sqrt, cos, sin and tan at global scope, where the copied code calls them
 * unqualified, as smallpaint does (smallpaint_painterly.cpp:12). Every such call takes a double,
 * so it is the same function as in the originals. */
#include <cstdint>
#include <math.h>
#include <random>

#include "bitwise.h"
#include "painterly/util/types_double3.h"

/* The oracle's hash helpers rng_u32, rng_unit and rng_signed, and its PURPOSE_* values. The header
 * defines them at global scope, so it is included in a namespace of its own, where it cannot
 * collide with painterly's names. Its functions are inline. <cstdint> is already included above,
 * so the header adds no standard-library declarations inside the namespace. */
namespace smallpaint_oracle {
#include "app/smallpaint_oracle_hash.h"
}  // namespace smallpaint_oracle

/* smallpaint's PI macro is defined below and undefined at the end of this file. Another PI would
 * be redefined and then removed for the including file. */
#ifdef PI
#  error "smallpaint_ref.h defines smallpaint's PI macro: PI must not be defined before it"
#endif

/* Warnings of the verbatim code, which stays as it is: Plane::normal does not use its parameter
 * p0 (smallpaint_painterly.cpp:91), a file that includes this header but does not call
 * hemisphere() or camcr() leaves them unused, and camcr() stores fovx and fovy as float, as the
 * oracle does. GCC and Clang take the diagnostic state at each definition, so the warnings are
 * off for these blocks only. MSVC: C4100 unused parameter, C4244 and C4305 double to float, C4505
 * unreferenced function with internal linkage. */
#if defined(_MSC_VER) && !defined(__clang__)
#  pragma warning(push)
#  pragma warning(disable : 4100 4244 4305 4505)
#elif defined(__GNUC__)
#  pragma GCC diagnostic push
#  pragma GCC diagnostic ignored "-Wunused-parameter"
#  pragma GCC diagnostic ignored "-Wunused-function"
#endif

// clang-format off
// verbatim third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp:33
// verbatim src/app/smallpaint_oracle.cpp:32
#define PI 3.1415926536
// end verbatim

namespace smallpaint_ref {
namespace {

// verbatim third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp:39
const double eps = 1e-4;
// end verbatim

// verbatim third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp:43-92
// verbatim src/app/smallpaint_oracle.cpp:72-121
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

// Rays have origin and direction.
// The direction vector should always be normalized.
struct Ray {
	Vec o, d;
	Ray(Vec o0 = 0, Vec d0 = 0) { o = o0, d = d0.norm(); }
};

// Objects have color, emission, type (diffuse, specular, refractive)
// All object should be intersectable and should be able to compute their surface normals.
class Obj {
public:
	Vec cl;
	double emission;
	int type;
	void setMat(Vec cl_ = 0, double emission_ = 0, int type_ = 0) { cl = cl_; emission = emission_; type = type_; }
	virtual double intersect(const Ray&) const = 0;
	virtual Vec normal(const Vec&) const = 0;
};

class Plane : public Obj {
public:
	Vec n;
	double d;
	Plane(double d_ = 0, Vec n_ = 0) {
		d = d_;
		n = n_;
	}
	double intersect(const Ray& ray) const {
		double d0 = n.dot(ray.d);
		if (d0 != 0) {
			double t = -1 * (((n.dot(ray.o)) + d) / d0);
			return (t > eps) ? t : 0;
		} else return 0;
	}
	Vec normal(const Vec& p0) const { return n; }
};
// end verbatim

// verbatim third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp:94-114
class Sphere : public Obj {
public:
	Vec c;
	double r;

	Sphere(double r_ = 0, Vec c_ = 0) { c = c_; r = r_; }
	double intersect(const Ray& ray) const {
		double b = ((ray.o - c) * 2).dot(ray.d);
		double c_ = (ray.o - c).dot((ray.o - c)) - (r*r);
		double disc = b*b - 4 * c_;
		if (disc < 0) return 0;
		else disc = sqrt(disc);
		double sol1 = -b + disc;
		double sol2 = -b - disc;
		return (sol2 > eps) ? sol2 / 2 : ((sol1 > eps) ? sol1 / 2 : 0);
	}

	Vec normal(const Vec& p0) const {
		return (p0 - c).norm();
	}
};
// end verbatim

// verbatim third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp:147-169
class Halton {
	double value, inv_base;
public:
	void number(int i, int base) {
		double f = inv_base = 1.0 / base;
		value = 0.0;
		while (i > 0) {
			value += f*(double)(i%base);
			i /= base;
			f *= inv_base;
		}
	}
	void next() {
		double r = 1.0 - value - 0.0000001;
		if (inv_base < r) value += inv_base;
		else {
			double h = inv_base, hh;
			do { hh = h; h *= inv_base; } while (h >= r);
			value += hh + h - 1.0;
		}
	}
	double get() { return value; }
};
// end verbatim

// verbatim third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp:183-187
Vec hemisphere(double u1, double u2) {
	const double r = sqrt(1.0 - u1*u1);
	const double phi = 2 * PI*u2;
	return Vec(cos(phi)*r, sin(phi)*r, u1);
}
// end verbatim

}  // namespace
}  // namespace smallpaint_ref

namespace smallpaint_oracle {
namespace {

// The oracle's Vec and Ray are smallpaint's (the block that cites both files above). The oracle's
// eps is the global that --ray-epsilon sets, 1e-4 by default, which is smallpaint's eps
// (smallpaint_painterly.cpp:39).
using smallpaint_ref::Ray;
using smallpaint_ref::Vec;
using smallpaint_ref::eps;

// The oracle's image size, which camcr() reads. A caller sets both before it calls camcr().
// verbatim src/app/smallpaint_oracle.cpp:36
int width, height;
// end verbatim

// The two members of the oracle's Sphere that intersect_exact() reads, in the oracle's order, and
// intersect_exact() itself: the SPEC §5 exact quadratic (src/app/CHANGES.md item 8).
struct Sphere {
// verbatim src/app/smallpaint_oracle.cpp:125-126
	Vec c;
	double r;
// end verbatim
// verbatim src/app/smallpaint_oracle.cpp:144-155
	// SPEC §5 exact quadratic. The eps tests act on the undivided roots; the roots are then divided by 2a.
	double intersect_exact(const Ray& ray) const {
		double a = ray.d.dot(ray.d);
		double b = ((ray.o - c) * 2).dot(ray.d);
		double c_ = (ray.o - c).dot((ray.o - c)) - (r*r);
		double disc = b*b - 4 * a * c_;
		if (disc < 0) return 0;
		else disc = sqrt(disc);
		double sol1 = -b + disc;
		double sol2 = -b - disc;
		return (sol2 > eps) ? sol2 / (2 * a) : ((sol1 > eps) ? sol1 / (2 * a) : 0);
	}
// end verbatim
};

// camcr(), with tan taken in double (src/app/CHANGES.md item 12).
// verbatim src/app/smallpaint_oracle.cpp:254-262
Vec camcr(const double x, const double y) {
	double w = width;
	double h = height;
	float fovx = PI / 4;
	float fovy = (h / w)*fovx;
	return Vec(((2 * x - w) / w)*tan((double)fovx),
		((2 * y - h) / h)*tan((double)fovy),
			   -1.0);
}
// end verbatim

}  // namespace
}  // namespace smallpaint_oracle
// clang-format on

#if defined(_MSC_VER) && !defined(__clang__)
#  pragma warning(pop)
#elif defined(__GNUC__)
#  pragma GCC diagnostic pop
#endif

CCL_NAMESPACE_BEGIN

namespace {

/* Unit normals are drawn from the box [-NORMAL_BOUND, NORMAL_BOUND)^3 and then normalized. */
constexpr double NORMAL_BOUND = 1.0;

inline smallpaint_ref::Vec to_ref(const Triple &t)
{
  return smallpaint_ref::Vec(t.x, t.y, t.z);
}

inline double3 to_double3(const smallpaint_ref::Vec &v)
{
  return make_double3(v.x, v.y, v.z);
}

/* True when every component of ref and got has the same IEEE 754 bit pattern. */
inline bool same_bits(const smallpaint_ref::Vec &ref, const double3 &got)
{
  return same_bits(ref.x, got.x) && same_bits(ref.y, got.y) && same_bits(ref.z, got.z);
}

/* A unit normal, normalized with smallpaint's Vec::norm() so that it is exactly the vector
 * smallpaint would use. The zero draw has probability 2^-159, and it would give NaN in both
 * implementations. */
inline Triple random_unit_normal(std::mt19937_64 &rng)
{
  smallpaint_ref::Vec n = to_ref(uniform_triple(rng, -NORMAL_BOUND, NORMAL_BOUND));
  n.norm();
  return {n.x, n.y, n.z};
}

}  // namespace

CCL_NAMESPACE_END

/* smallpaint's PI is a macro (smallpaint_painterly.cpp:33, smallpaint_oracle.cpp:32). It is kept
 * verbatim above, so that hemisphere() and camcr() expand it as the originals do, and undefined
 * here, so that it does not reach the files that include this header. */
#undef PI
