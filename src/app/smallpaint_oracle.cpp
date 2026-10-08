// smallpaint by karoly zsolnai - zsolnai@cg.tuwien.ac.at
//
// render, modify, create new scenes, tinker around, and most of all:
// have fun!
//
// This program is used as an educational learning tool on the Rendering
// course at TU Wien. Course webpage:
// http://cg.tuwien.ac.at/courses/Rendering/

// Modified by the Painterly project: headless reference oracle (see src/app/CHANGES.md).

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
#include "smallpaint_oracle_hash.h"

namespace smallpaint_painterly {

#define PI 3.1415926536
#define MIN(a,b) (((a)<(b))?(a):(b))
#define MAX(a,b) (((a)>(b))?(a):(b))

int width, height;
const double inf = 1e9;
const double eps = 1e-4;
using namespace std;
typedef unordered_map<string, double> pl;

// Oracle knobs (CHANGES.md). main() sets them once before any worker thread starts; they are read-only afterwards.
enum class GhostPolicy { all, lights, none };                                          // --ghost
enum class U2Mode { same, independent, base3 };                                        // --u2
enum class SceneKind { gui, standalone };                                              // --scene
enum class ChainKind { image, row, lane, omp_restart, pixel_major, pixel_major_omp };  // --chain
bool g_halton_exact = false;                    // --halton exact
GhostPolicy g_ghost = GhostPolicy::all;         // --ghost all
double g_alpha = 0.0;                           // --alpha 0 (SPEC §4: exact no-op)
U2Mode g_u2 = U2Mode::same;                     // --u2 same
bool g_continue_after_emitter = true;           // --continue-after-emitter yes
SceneKind g_scene = SceneKind::gui;             // --scene gui
double g_jitter = 1.0 / 700.0;                  // --jitter; smallpaint_painterly.cpp:291-292 (RND / 700)

// Path context for the stateless RNG (SPEC §2). The chain driver sets it before every trace() call.
struct PathContext {
	uint32_t seed;
	int row, col, pass;
};
thread_local PathContext g_path{0, 0, 0, 0};

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

class Sphere : public Obj {
public:
	Vec c;
	double r;

	Sphere(double r_ = 0, Vec c_ = 0) { c = c_; r = r_; }
	double intersect(const Ray& ray) const {
		// --ghost (SPEC §5): all spheres use the original ghost test; lights only for emitters; none never.
		if (g_ghost == GhostPolicy::all || (g_ghost == GhostPolicy::lights && emission > 0)) {
			double b = ((ray.o - c) * 2).dot(ray.d);
			double c_ = (ray.o - c).dot((ray.o - c)) - (r*r);
			double disc = b*b - 4 * c_;
			if (disc < 0) return 0;
			else disc = sqrt(disc);
			double sol1 = -b + disc;
			double sol2 = -b - disc;
			return (sol2 > eps) ? sol2 / 2 : ((sol1 > eps) ? sol1 / 2 : 0);
		}
		return intersect_exact(ray);
	}

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

	Vec normal(const Vec& p0) const {
		// GUI: unit normal from the true centre (smallpaint_painterly.cpp:112).
		// Standalone: (P - c) / r (standalone/smallpaint_painterly.cpp:107-111).
		if (g_scene == SceneKind::standalone) return Vec((p0.x-c.x)/r, (p0.y-c.y)/r, (p0.z-c.z)/r);
		return (p0 - c).norm();
	}
};

class Intersection {
public:
	Intersection() { t = inf; object = nullptr; }
	Intersection(double t_, Obj* object_) { t = t_; object = object_; }
	operator bool() { return object != nullptr; }
	double t;
	Obj* object;
};

class Scene {
	vector<Obj*> objects;

public:
	void add(Obj* object) {
		objects.push_back(object);
	}

	Intersection intersect(const Ray& ray) const {
		Intersection closestIntersection;
		// intersect all objects, one after the other
		for (auto iter = objects.begin(); iter != objects.end(); ++iter) {
			double t = (*iter)->intersect(ray);
			if (t > eps && t < closestIntersection.t) {
				closestIntersection.t = t;
				closestIntersection.object = *iter;
			}
		}
		return closestIntersection;
	}

	// Scene-list index of an object, which is its object id (SPEC §9), or -1.
	int index_of(const Obj* object) const {
		for (size_t k = 0; k < objects.size(); ++k) {
			if (objects[k] == object) return (int)k;
		}
		return -1;
	}
};

// SPEC §2: vdc(K) = bitrev23(K mod 2^23) * 2^-23, where bitrev23 reverses the low 23 bits.
// 2^23 is the period of smallpaint's incremental Halton step in double. 2^-23 is the exact scale of a 23-bit integer.
inline double halton_vdc2(const uint64_t k) {
	const int bits = 23;
	uint64_t rest = k & ((uint64_t(1) << bits) - 1);
	uint64_t r = 0;
	for (int b = 0; b < bits; ++b) {
		r = (r << 1) | (rest & 1);
		rest >>= 1;
	}
	return (double)r * 0x1p-23; // exact: r < 2^23
}

class Halton {
	double value, inv_base;
	int base_ = 0;
public:
	uint64_t index = 0; // K: set by number(), incremented by next() (CHANGES.md 3)
	void number(int i, int base) {
		index = (uint64_t)i;
		base_ = base;
		double f = inv_base = 1.0 / base;
		value = 0.0;
		if (g_halton_exact && base == 2) {
			value = halton_vdc2(index);
			return;
		}
		while (i > 0) {
			value += f*(double)(i%base);
			i /= base;
			f *= inv_base;
		}
	}
	void next() {
		index++;
		if (g_halton_exact && base_ == 2) {
			value = halton_vdc2(index);
			return;
		}
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

Vec camcr(const double x, const double y) {
	double w = width;
	double h = height;
	float fovx = PI / 4;
	float fovy = (h / w)*fovx;
	return Vec(((2 * x - w) / w)*tan((double)fovx),
		((2 * y - h) / h)*tan((double)fovy),
			   -1.0);
}

// a messed up sampling function (at least in this context).
// courtesy of http://www.rorydriscoll.com/2009/01/07/better-sampling/
Vec hemisphere(double u1, double u2) {
	const double r = sqrt(1.0 - u1*u1);
	const double phi = 2 * PI*u2;
	return Vec(cos(phi)*r, sin(phi)*r, u1);
}

void trace(Ray &ray, const Scene& scene, int depth, Vec& clr, pl& params, Halton& hal, Halton& hal2) {
	if (depth >= 20) return;

	Intersection intersection = scene.intersect(ray);
	if (!intersection) return;

	// Travel the ray to the hit point where the closest object lies and compute the surface normal there.
	Vec hp = ray.o + ray.d * intersection.t;
	Vec N = intersection.object->normal(hp);
	ray.o = hp;

	clr = clr + Vec(intersection.object->emission, intersection.object->emission, intersection.object->emission) * 2;
	// --continue-after-emitter no: the path ends at an emitter after its emission (CHANGES.md 8).
	if (!g_continue_after_emitter && intersection.object->emission > 0) return;

	if (intersection.object->type == 1) {
		hal.next();
		hal2.next();
		// u2 (SPEC §4): the hal2 value, or a stateless PURPOSE_U2 draw with --u2 independent.
		const double u2 = (g_u2 == U2Mode::independent)
			? rng_unit(g_path.seed, PURPOSE_U2, (uint32_t)depth, (uint32_t)g_path.row, (uint32_t)g_path.col, (uint32_t)g_path.pass)
			: hal2.get();
		ray.d = (N + hemisphere(hal.get(), u2));
		ray.d = ray.d * pow(ray.d.length(), -g_alpha); // --alpha (SPEC §4)
		double cost = ray.d.dot(N);
		Vec tmp = Vec();
		trace(ray, scene, depth + 1, tmp, params, hal, hal2);
		clr.x += cost*(tmp.x*intersection.object->cl.x)*0.1;
		clr.y += cost*(tmp.y*intersection.object->cl.y)*0.1;
		clr.z += cost*(tmp.z*intersection.object->cl.z)*0.1;
	}

	if (intersection.object->type == 2) {
		double cost = ray.d.dot(N);
		ray.d = (ray.d - N*(cost * 2)).norm();
		Vec tmp = Vec(0, 0, 0);
		trace(ray, scene, depth + 1, tmp, params, hal, hal2);
		clr = clr + tmp;
	}

	if (intersection.object->type == 3) {
		double n = params["refr_index"];
		if (N.dot(ray.d) > 0) {
			N = N*-1;
			n = 1 / n;
		}
		n = 1 / n;
		double cost1 = (N.dot(ray.d))*-1;
		double cost2 = 1.0 - n*n*(1.0 - cost1*cost1);
		if (cost2 > 0) {
			ray.d = (ray.d*n) + (N*(n*cost1 - sqrt(cost2)));
			ray.d = ray.d.norm();
			Vec tmp = Vec(0, 0, 0);
			trace(ray, scene, depth + 1, tmp, params, hal, hal2);
			clr = clr + tmp;
		} else return;
	}
}

// Reference scene (SPEC §9). GUI values: smallpaint_painterly.cpp:252-262. Standalone values:
// standalone/smallpaint_painterly.cpp:224 and :234. Planes and the other spheres are identical in both.
void build_scene(Scene& scene) {
	auto add = [&scene](Obj* s, Vec cl, double emission, int type) {
		s->setMat(cl, emission, type);
		scene.add(s);
	};
	const bool standalone = g_scene == SceneKind::standalone;

	// Radius, position, color, emission, type (1=diff, 2=spec, 3=refr) for spheres
	add(new Sphere(1.05, Vec(1.45, -0.75, -4.4)), Vec(4, 8, 4), 0, 2); // Middle sphere
	if (standalone) add(new Sphere(0.45, Vec(2.05, 0.8, -3.7)), Vec(10, 10, 1), 0, 3); // Right sphere (standalone)
	else add(new Sphere(0.5, Vec(2.05, 2.0, -3.7)), Vec(10, 10, 1), 0, 3); // Right sphere (GUI)
	add(new Sphere(0.6, Vec(1.95, -1.75, -3.1)), Vec(4, 4, 12), 0, 1); // Left sphere
	// Position, normal, color, emission, type for planes
	add(new Plane(2.5, Vec(-1, 0, 0)), Vec(6, 6, 6), 0, 1); // Bottom plane
	add(new Plane(5.5, Vec(0, 0, 1)), Vec(6, 6, 6), 0, 1); // Back plane
	add(new Plane(2.75, Vec(0, 1, 0)), Vec(10, 2, 2), 0, 1); // Left plane
	add(new Plane(2.75, Vec(0, -1, 0)), Vec(2, 10, 2), 0, 1); // Right plane
	add(new Plane(3.0, Vec(1, 0, 0)), Vec(6, 6, 6), 0, 1); // Ceiling plane
	add(new Plane(0.5, Vec(0, 0, -1)), Vec(6, 6, 6), 0, 1); // Front plane
	if (standalone) add(new Sphere(eps, Vec(-1.9, 0, -3)), Vec(0, 0, 0), 120, 1); // Light, radius eps (standalone)
	else add(new Sphere(0.5, Vec(-1.9, 0, -3)), Vec(0, 0, 0), 120, 1); // Light (GUI)
}

// Per-pixel outputs. Pixel (row, col) is at index row * size + col. sum holds three doubles per pixel.
struct Film {
	int size = 0;
	vector<double> sum;        // trace colour summed over passes (pix, smallpaint_painterly.cpp:295-297)
	vector<uint64_t> k;        // diffuse draws consumed over all passes (hal.index deltas)
	vector<int32_t> object_id; // scene-list index hit by the unjittered primary ray, or -1
};

// One sample of pixel (row, col) in pass `pass` (smallpaint_painterly.cpp:289-297), with the oracle's jitter (SPEC §7).
// hal and hal2 are the sequence state of the chain; the sample advances them by its own diffuse draws.
void take_sample(const Scene& scene, pl& params, Halton& hal, Halton& hal2, Film& film, uint32_t seed,
	int row, int col, int pass) {
	Vec c;
	Ray ray;
	ray.o = (Vec(0, 0, 0));
	Vec cam = camcr(row, col);
	cam.x = cam.x + rng_signed(seed, PURPOSE_JITTER_X, 0, (uint32_t)row, (uint32_t)col, (uint32_t)pass) * g_jitter;
	cam.y = cam.y + rng_signed(seed, PURPOSE_JITTER_Y, 0, (uint32_t)row, (uint32_t)col, (uint32_t)pass) * g_jitter;
	ray.d = (cam - ray.o).norm();
	const uint64_t k_before = hal.index;
	g_path = PathContext{seed, row, col, pass};
	trace(ray, scene, 0, c, params, hal, hal2);
	const size_t px = (size_t)row * (size_t)film.size + (size_t)col;
	film.k[px] += hal.index - k_before;
	film.sum[3 * px + 0] += c.x;
	film.sum[3 * px + 1] += c.y;
	film.sum[3 * px + 2] += c.z;
}

// object_id: the scene-list index hit by the unjittered primary ray of each pixel, or -1 (SPEC §9).
void compute_object_ids(const Scene& scene, Film& film) {
	for (int row = 0; row < film.size; ++row) {
		for (int col = 0; col < film.size; ++col) {
			Ray ray;
			ray.o = (Vec(0, 0, 0));
			Vec cam = camcr(row, col);
			ray.d = (cam - ray.o).norm();
			const Intersection hit = scene.intersect(ray);
			film.object_id[(size_t)row * (size_t)film.size + (size_t)col] = hit.object ? scene.index_of(hit.object) : -1;
		}
	}
}

// Runs work(unit, params) for every unit in [0, units) on min(threads, units) workers. Each worker owns a copy of
// params, because unordered_map::operator[] (used by trace) is not safe to share. Units write disjoint pixels.
template <typename Work>
void run_units(const int units, const int threads, const pl& params, Work work) {
	atomic<int> next_unit{0};
	auto worker = [&]() {
		pl own_params = params;
		for (;;) {
			const int unit = next_unit.fetch_add(1);
			if (unit >= units) break;
			work(unit, own_params);
		}
	};
	const int workers = min(threads, units);
	vector<thread> pool;
	for (int t = 0; t < workers; ++t) pool.emplace_back(worker);
	for (thread& th : pool) th.join();
}

// K0 of a chain segment (SPEC §3): rng_u32(seed, PURPOSE_LANE_K0, 0, row, lane_in_row, pass) mod 2^22.
// The mask is 2^22 - 1. It keeps every chain segment below the 2^23 wrap of the incremental generator.
constexpr uint32_t K0_MASK = (1u << 22) - 1;
inline int lane_k0(const uint32_t seed, const int row, const int lane, const int pass) {
	return (int)(rng_u32(seed, PURPOSE_LANE_K0, 0, (uint32_t)row, (uint32_t)lane, (uint32_t)pass) & K0_MASK);
}

struct Options {
	string scene = "gui";
	int size = 400;
	int passes = 50;
	double refr = 1.5;
	uint32_t seed = 0;
	string chain_text = "image";
	ChainKind chain = ChainKind::image;
	int chain_param = 0;
	string halton = "incremental";
	string ghost = "all";
	double alpha = 0.0;
	string u2 = "same";
	string continue_after_emitter = "yes";
	double jitter = 1.0 / 700.0;
	int threads = 1;
	string out;
	int base2 = 2; // base of hal2: 3 with --u2 base3, otherwise 2 (SPEC §3, §4)
};

// Chain drivers (SPEC §3). Each unit is one independent chain. Inside a chain, passes and pixels run in the order the
// chain defines, so the sum of every pixel is taken in increasing pass order, for any thread count.
void run_chain(const Options& o, const Scene& scene, Film& film, const pl& params) {
	const int n = o.size;
	const int passes = o.passes;
	switch (o.chain) {
	case ChainKind::image:
		run_units(1, 1, params, [&](int, pl& p) {
			Halton hal, hal2;
			hal.number(0, 2);
			hal2.number(0, o.base2);
			for (int s = 0; s < passes; ++s)
				for (int i = 0; i < n; ++i)
					for (int j = 0; j < n; ++j) take_sample(scene, p, hal, hal2, film, o.seed, i, j, s);
		});
		break;
	case ChainKind::row:
		run_units(n, o.threads, params, [&](int i, pl& p) {
			for (int s = 0; s < passes; ++s) {
				Halton hal, hal2;
				const int k0 = lane_k0(o.seed, i, 0, s);
				hal.number(k0, 2);
				hal2.number(k0, o.base2);
				for (int j = 0; j < n; ++j) take_sample(scene, p, hal, hal2, film, o.seed, i, j, s);
			}
		});
		break;
	case ChainKind::lane: {
		const int lane_length = o.chain_param;
		const int lanes = (n + lane_length - 1) / lane_length; // ceil(n / L)
		run_units(n * lanes, o.threads, params, [&](int unit, pl& p) {
			const int i = unit / lanes;
			const int l = unit % lanes;
			const int j0 = l * lane_length;
			const int j1 = min(j0 + lane_length, n);
			for (int s = 0; s < passes; ++s) {
				Halton hal, hal2;
				const int k0 = lane_k0(o.seed, i, l, s);
				hal.number(k0, 2);
				hal2.number(k0, o.base2);
				for (int j = j0; j < j1; ++j) take_sample(scene, p, hal, hal2, film, o.seed, i, j, s);
			}
		});
		break;
	}
	case ChainKind::omp_restart: {
		const int threads_v = o.chain_param;
		run_units(threads_v, o.threads, params, [&](int t, pl& p) {
			Halton hal, hal2;
			for (int s = 0; s < passes; ++s) {
				hal.number(0, 2);
				hal2.number(0, o.base2);
				for (int i = t; i < n; i += threads_v)
					for (int j = 0; j < n; ++j) take_sample(scene, p, hal, hal2, film, o.seed, i, j, s);
			}
		});
		break;
	}
	case ChainKind::pixel_major:
		run_units(1, 1, params, [&](int, pl& p) {
			Halton hal, hal2;
			hal.number(0, 2);
			hal2.number(0, o.base2);
			for (int i = 0; i < n; ++i)
				for (int j = 0; j < n; ++j)
					for (int s = 0; s < passes; ++s) take_sample(scene, p, hal, hal2, film, o.seed, i, j, s);
		});
		break;
	case ChainKind::pixel_major_omp: {
		const int threads_v = o.chain_param;
		run_units(threads_v, o.threads, params, [&](int t, pl& p) {
			Halton hal, hal2;
			hal.number(0, 2);
			hal2.number(0, o.base2);
			for (int i = t; i < n; i += threads_v)
				for (int j = 0; j < n; ++j)
					for (int s = 0; s < passes; ++s) take_sample(scene, p, hal, hal2, film, o.seed, i, j, s);
		});
		break;
	}
	}
}

// Writes a NumPy .npy file, format version 1.0. Data are little-endian (x86-64 and arm64 hosts).
bool write_npy(const filesystem::path& path, const string& descr, const vector<size_t>& shape, const void* data,
	size_t bytes) {
	string dims;
	for (size_t k = 0; k < shape.size(); ++k) dims += (k > 0 ? ", " : "") + to_string(shape[k]);
	const string header = "{'descr': '" + descr + "', 'fortran_order': False, 'shape': (" + dims + "), }";
	// Layout: magic (6 bytes), version (2), header length (2, little-endian), header, '\n'. NumPy pads the header with
	// spaces so that the total length is a multiple of 64 bytes.
	const size_t prefix_bytes = 10;
	const size_t alignment = 64;
	const size_t unpadded = header.size() + 1;
	const size_t pad = (alignment - (prefix_bytes + unpadded) % alignment) % alignment;
	const size_t header_len = unpadded + pad;
	const unsigned char head[10] = {0x93, 'N', 'U', 'M', 'P', 'Y', 1, 0, (unsigned char)(header_len & 0xFF),
		(unsigned char)(header_len >> 8)};
	const string tail = header + string(pad, ' ') + "\n";
	FILE* f = fopen(path.string().c_str(), "wb");
	if (!f) return false;
	bool ok = fwrite(head, 1, sizeof head, f) == sizeof head;
	ok = (fwrite(tail.data(), 1, tail.size(), f) == tail.size()) && ok;
	ok = (fwrite(data, 1, bytes, f) == bytes) && ok;
	return (fclose(f) == 0) && ok;
}

// image.ppm (binary P6): byte = min((int)sum / passes, 255) per channel, C truncation then integer division (SPEC §7).
bool write_ppm(const filesystem::path& path, const Film& film, const int passes) {
	FILE* f = fopen(path.string().c_str(), "wb");
	if (!f) return false;
	fprintf(f, "P6\n%d %d\n255\n", film.size, film.size);
	vector<unsigned char> bytes(film.sum.size());
	for (size_t k = 0; k < film.sum.size(); ++k) bytes[k] = (unsigned char)min((int)film.sum[k] / passes, 255);
	const bool ok = fwrite(bytes.data(), 1, bytes.size(), f) == bytes.size();
	return (fclose(f) == 0) && ok;
}

bool write_meta(const filesystem::path& path, const Options& o, const double wall_seconds, const uint64_t total_k) {
	FILE* f = fopen(path.string().c_str(), "w");
	if (!f) return false;
	fprintf(f, "{\n");
	fprintf(f, "  \"oracle_version\": \"1\",\n");
	fprintf(f, "  \"scene\": \"%s\",\n", o.scene.c_str());
	fprintf(f, "  \"width\": %d,\n", o.size);
	fprintf(f, "  \"height\": %d,\n", o.size);
	fprintf(f, "  \"passes\": %d,\n", o.passes);
	fprintf(f, "  \"refr\": %.17g,\n", o.refr);
	fprintf(f, "  \"seed\": %u,\n", (unsigned int)o.seed);
	fprintf(f, "  \"chain\": \"%s\",\n", o.chain_text.c_str());
	fprintf(f, "  \"halton\": \"%s\",\n", o.halton.c_str());
	fprintf(f, "  \"ghost\": \"%s\",\n", o.ghost.c_str());
	fprintf(f, "  \"alpha\": %.17g,\n", o.alpha);
	fprintf(f, "  \"u2\": \"%s\",\n", o.u2.c_str());
	fprintf(f, "  \"continue_after_emitter\": \"%s\",\n", o.continue_after_emitter.c_str());
	fprintf(f, "  \"jitter\": %.17g,\n", o.jitter);
	fprintf(f, "  \"threads\": %d,\n", o.threads);
	fprintf(f, "  \"wall_seconds\": %.6f,\n", wall_seconds);
	fprintf(f, "  \"total_k_consumed\": %llu\n", (unsigned long long)total_k);
	fprintf(f, "}\n");
	return fclose(f) == 0;
}

const char* const kUsage =
	"usage: smallpaint_oracle --out DIR [options]\n"
	"  --scene gui|standalone              reference scene (default gui)\n"
	"  --size N                            image side in pixels (gui 400, standalone 900)\n"
	"  --passes N                          passes (gui 50, standalone 8)\n"
	"  --refr X                            glass IOR, X > 0 (gui 1.5, standalone 1.9)\n"
	"  --seed N                            uint32 seed (default 0)\n"
	"  --chain image|row|lane:L|omp-restart:T|pixel-major|pixel-major-omp:T\n"
	"                                      (default image; standalone default pixel-major)\n"
	"  --halton incremental|exact          (default incremental)\n"
	"  --ghost all|lights|none             (default all)\n"
	"  --alpha X                           (default 0)\n"
	"  --u2 same|independent|base3         (default same)\n"
	"  --continue-after-emitter yes|no     (default yes)\n"
	"  --jitter X                          image-plane jitter (default 1/700)\n"
	"  --threads N                         worker threads (default hardware concurrency)\n"
	"  --out DIR                           output directory, created if missing (required)\n";

int usage_error(const string& message) {
	fprintf(stderr, "smallpaint_oracle: %s\n%s", message.c_str(), kUsage);
	return 2;
}

bool parse_int_arg(const string& text, const long long lo, const long long hi, long long& value) {
	if (text.empty()) return false;
	char* end = nullptr;
	errno = 0;
	const long long v = strtoll(text.c_str(), &end, 10);
	if (errno != 0 || *end != '\0' || v < lo || v > hi) return false;
	value = v;
	return true;
}

bool parse_double_arg(const string& text, double& value) {
	if (text.empty()) return false;
	char* end = nullptr;
	const double v = strtod(text.c_str(), &end);
	if (*end != '\0' || !std::isfinite(v)) return false;
	value = v;
	return true;
}

// image, row, lane:L, omp-restart:T, pixel-major, pixel-major-omp:T
bool parse_chain(const string& text, ChainKind& kind, int& param) {
	const size_t colon = text.find(':');
	const string name = text.substr(0, colon);
	const bool has_param = colon != string::npos;
	const string arg = has_param ? text.substr(colon + 1) : string();
	long long v = 0;
	if (!has_param && name == "image") kind = ChainKind::image;
	else if (!has_param && name == "row") kind = ChainKind::row;
	else if (!has_param && name == "pixel-major") kind = ChainKind::pixel_major;
	else if (has_param && name == "lane" && parse_int_arg(arg, 1, INT_MAX, v)) kind = ChainKind::lane;
	else if (has_param && name == "omp-restart" && parse_int_arg(arg, 1, INT_MAX, v)) kind = ChainKind::omp_restart;
	else if (has_param && name == "pixel-major-omp" && parse_int_arg(arg, 1, INT_MAX, v)) kind = ChainKind::pixel_major_omp;
	else return false;
	param = has_param ? (int)v : 0;
	return true;
}

int oracle_main(int argc, char** argv) {
	Options o;
	o.threads = (int)max(1u, thread::hardware_concurrency());
	bool size_given = false;
	bool passes_given = false;
	bool refr_given = false;
	bool chain_given = false;

	for (int a = 1; a < argc; ++a) {
		const string flag = argv[a];
		const bool known = flag == "--scene" || flag == "--size" || flag == "--passes" || flag == "--refr" ||
			flag == "--seed" || flag == "--chain" || flag == "--halton" || flag == "--ghost" || flag == "--alpha" ||
			flag == "--u2" || flag == "--continue-after-emitter" || flag == "--jitter" || flag == "--threads" ||
			flag == "--out";
		if (!known) return usage_error("unknown option '" + flag + "'");
		if (a + 1 >= argc) return usage_error("missing value for " + flag);
		const string val = argv[++a];
		const string bad = "invalid value '" + val + "' for " + flag;
		long long iv = 0;
		double dv = 0;
		if (flag == "--scene") {
			if (val != "gui" && val != "standalone") return usage_error(bad);
			o.scene = val;
		} else if (flag == "--size") {
			if (!parse_int_arg(val, 1, INT_MAX, iv)) return usage_error(bad);
			o.size = (int)iv;
			size_given = true;
		} else if (flag == "--passes") {
			if (!parse_int_arg(val, 1, INT_MAX, iv)) return usage_error(bad);
			o.passes = (int)iv;
			passes_given = true;
		} else if (flag == "--refr") {
			if (!parse_double_arg(val, dv) || dv <= 0) return usage_error(bad);
			o.refr = dv;
			refr_given = true;
		} else if (flag == "--seed") {
			if (!parse_int_arg(val, 0, 4294967295LL, iv)) return usage_error(bad);
			o.seed = (uint32_t)iv;
		} else if (flag == "--chain") {
			o.chain_text = val;
			chain_given = true;
		} else if (flag == "--halton") {
			if (val != "incremental" && val != "exact") return usage_error(bad);
			o.halton = val;
		} else if (flag == "--ghost") {
			if (val != "all" && val != "lights" && val != "none") return usage_error(bad);
			o.ghost = val;
		} else if (flag == "--alpha") {
			if (!parse_double_arg(val, dv)) return usage_error(bad);
			o.alpha = dv;
		} else if (flag == "--u2") {
			if (val != "same" && val != "independent" && val != "base3") return usage_error(bad);
			o.u2 = val;
		} else if (flag == "--continue-after-emitter") {
			if (val != "yes" && val != "no") return usage_error(bad);
			o.continue_after_emitter = val;
		} else if (flag == "--jitter") {
			if (!parse_double_arg(val, dv)) return usage_error(bad);
			o.jitter = dv;
		} else if (flag == "--threads") {
			if (!parse_int_arg(val, 1, INT_MAX, iv)) return usage_error(bad);
			o.threads = (int)iv;
		} else if (flag == "--out") {
			o.out = val;
		}
	}

	if (o.out.empty()) return usage_error("--out DIR is required");
	const bool standalone = o.scene == "standalone";
	// Scene defaults (SPEC §9), each used unless the flag was given.
	if (!size_given) o.size = standalone ? 900 : 400;
	if (!passes_given) o.passes = standalone ? 8 : 50;
	if (!refr_given) o.refr = standalone ? 1.9 : 1.5;
	if (!chain_given) o.chain_text = standalone ? "pixel-major" : "image";
	if (!parse_chain(o.chain_text, o.chain, o.chain_param)) {
		return usage_error("invalid value '" + o.chain_text + "' for --chain");
	}

	// Knobs are set here, before any worker thread exists.
	g_halton_exact = o.halton == "exact";
	g_ghost = o.ghost == "lights" ? GhostPolicy::lights : (o.ghost == "none" ? GhostPolicy::none : GhostPolicy::all);
	g_alpha = o.alpha;
	g_u2 = o.u2 == "independent" ? U2Mode::independent : (o.u2 == "base3" ? U2Mode::base3 : U2Mode::same);
	g_continue_after_emitter = o.continue_after_emitter == "yes";
	g_scene = standalone ? SceneKind::standalone : SceneKind::gui;
	g_jitter = o.jitter;
	o.base2 = g_u2 == U2Mode::base3 ? 3 : 2;
	width = o.size;
	height = o.size;

	Scene scene;
	build_scene(scene);
	pl params;
	params["refr_index"] = o.refr;
	params["spp"] = o.passes; // samples per pixel (smallpaint_painterly.cpp:265)

	const size_t pixels = (size_t)o.size * (size_t)o.size;
	Film film;
	film.size = o.size;
	film.sum.assign(pixels * 3, 0.0);
	film.k.assign(pixels, 0);
	film.object_id.assign(pixels, -1);
	compute_object_ids(scene, film);

	const chrono::steady_clock::time_point start = chrono::steady_clock::now();
	run_chain(o, scene, film, params);
	const double wall_seconds = chrono::duration<double>(chrono::steady_clock::now() - start).count();

	uint64_t total_k = 0;
	for (const uint64_t k : film.k) total_k += k;

	const filesystem::path dir = o.out;
	error_code ec;
	filesystem::create_directories(dir, ec);
	if (ec) return usage_error("cannot create output directory '" + o.out + "'");

	const vector<size_t> pixel_shape = {(size_t)o.size, (size_t)o.size};
	const vector<size_t> rgb_shape = {(size_t)o.size, (size_t)o.size, 3};
	bool ok = write_npy(dir / "sum.npy", "<f8", rgb_shape, film.sum.data(), film.sum.size() * sizeof(double));
	ok = write_npy(dir / "k_consumed.npy", "<u8", pixel_shape, film.k.data(), film.k.size() * sizeof(uint64_t)) && ok;
	ok = write_npy(dir / "object_id.npy", "<i4", pixel_shape, film.object_id.data(),
		film.object_id.size() * sizeof(int32_t)) && ok;
	ok = write_ppm(dir / "image.ppm", film, o.passes) && ok;
	ok = write_meta(dir / "meta.json", o, wall_seconds, total_k) && ok;
	if (!ok) {
		fprintf(stderr, "smallpaint_oracle: failed to write outputs to '%s'\n", o.out.c_str());
		return 1;
	}
	printf("smallpaint_oracle: wrote %s wall_seconds=%.3f total_k_consumed=%llu\n", o.out.c_str(), wall_seconds,
		(unsigned long long)total_k);
	return 0;
}

}

int main(int argc, char** argv) {
	return smallpaint_painterly::oracle_main(argc, argv);
}

// clang-format on
