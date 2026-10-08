#include <math.h>
#include <algorithm>
#include <vector>

using namespace std;

namespace smallpaint {
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
	Vec operator%(const Vec &b) const { return Vec(y*b.z - z*b.y, z*b.x - x*b.z, x*b.y - y*b.x); }
	//	double& operator[](size_t i) { return data[i]; }
	const double& operator[](size_t i) const { return i == 0 ? x : (i == 1 ? y : z); }
};
}

namespace smallpaint_fixed {
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
	Vec operator%(const Vec &b) const { return Vec(y*b.z - z*b.y, z*b.x - x*b.z, x*b.y - y*b.x); }
	//	double& operator[](size_t i) { return data[i]; }
	const double& operator[](size_t i) const { return i == 0 ? x : (i == 1 ? y : z); }
};
}

namespace smallpaint_painterly {
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
}

namespace smallpaint_bvh {
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
	Vec operator%(const Vec &b) const { return Vec(y*b.z - z*b.y, z*b.x - x*b.z, x*b.y - y*b.x); }
	const double& operator[](size_t i) const { return i == 0 ? x : (i == 1 ? y : z); }
};
}

namespace smallpaint_pssmlt {
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
	Vec operator%(const Vec &b) const { return Vec(y*b.z - z*b.y, z*b.x - x*b.z, x*b.y - y*b.x); }
	//	double& operator[](size_t i) { return data[i]; }
	const double& operator[](size_t i) const { return i == 0 ? x : (i == 1 ? y : z); }
};
}

namespace smallpaint_smallmedia {
struct Vec {
	double x, y, z;
	Vec(double x0, double y0, double z0) { x = x0; y = y0; z = z0; }
	Vec(double xyz0 = 0) { x = xyz0; y = xyz0; z = xyz0; }
	Vec operator+(const Vec &b) const { return Vec(x + b.x, y + b.y, z + b.z); }
	Vec operator+=(const Vec &b) { x += b.x; y += b.y; z += b.z; return (*this); }
	Vec operator-(const Vec &b) const { return Vec(x - b.x, y - b.y, z - b.z); }
	Vec operator*(double b) const { return Vec(x*b, y*b, z*b); }
	Vec operator*(const Vec &b) const { return Vec(x*b.x, y*b.y, z*b.z); }
	Vec operator*=(const Vec &b) { x *= b.x; y *= b.y; z *= b.z; return (*this); }
	Vec operator/(double b) const { return Vec(x / b, y / b, z / b); }
	Vec operator/(const Vec &b) const { return Vec(x / b.x, y / b.y, z / b.z); }
	bool operator<(const Vec &b) const { return x < b.x && y < b.y && z < b.z; }
	bool operator>(const Vec &b) const { return x > b.x && y > b.y && z > b.z; }
	Vec& norm() { return *this = *this * (1 / sqrt(x*x + y*y + z*z)); }
	double length() const { return sqrt(x*x + y*y + z*z); }
	double dot(const Vec &b) const { return x*b.x + y*b.y + z*b.z; }
	double avg() const { return (x + y + z) / 3.0; }
	double max() const { return x > y ? (x > z ? x : z) : (y > z ? y : z); }
	double min() const { return x < y ? (x < z ? x : z) : (y < z ? y : z); }
	Vec operator%(const Vec &b) const { return Vec(y*b.z - z*b.y, z*b.x - x*b.z, x*b.y - y*b.x); }
	const double& operator[](size_t i) const { return i == 0 ? x : (i == 1 ? y : z); }
};
Vec operator*(double a, const Vec &b); // double * Vec
}

namespace smallpaint_ppm {

#define MIN(a,b) (((a)<(b))?(a):(b))
#define MAX(a,b) (((a)>(b))?(a):(b))

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
	double max() const { return x > y&&x > z ? x : y > z ? y : z; }
	Vec minValues(const Vec &b) const { return Vec(MIN(x, b.x), MIN(y, b.y), MIN(z, b.z)); }
	Vec maxValues(const Vec &b) const { return Vec(MAX(x, b.x), MAX(y, b.y), MAX(z, b.z)); }
	Vec operator%(const Vec &b) const { return Vec(y*b.z - z*b.y, z*b.x - x*b.z, x*b.y - y*b.x); }
	Vec absolute() const { return Vec(abs(x), abs(y), abs(z)); }
	//	double& operator[](size_t i) { return data[i]; }
	const double& operator[](size_t i) const { return i == 0 ? x : (i == 1 ? y : z); }
};
}

namespace smallpaint_vrl {

struct Vec {
    double x, y, z;
    Vec(double x0, double y0, double z0) { x = x0; y = y0; z = z0; }
    Vec(double x0) { x = x0; y = x0; z = x0; }
    Vec() { x = 0; y = 0; z = 0; }
    Vec operator+(const Vec &b) const { return Vec(x + b.x, y + b.y, z + b.z); }
    Vec operator-(const Vec &b) const { return Vec(x - b.x, y - b.y, z - b.z); }
    Vec operator*(double b) const { return Vec(x*b, y*b, z*b); }
    Vec operator*(const Vec &b) const { return Vec(x*b.x, y*b.y, z*b.z); }
    Vec operator/(double b) const { return Vec(x / b, y / b, z / b); }
    Vec operator/(const Vec &b) const { return Vec(x / b.x, y / b.y, z / b.z); }
    Vec& norm() { return *this = *this * (1 / std::sqrt(x*x + y * y + z * z)); }
    double length() { return std::sqrt(x*x + y * y + z * z); }
    double dot(const Vec &b) const { return x * b.x + y * b.y + z * b.z; }
    Vec operator%(const Vec &b) const { return Vec(y*b.z - z * b.y, z*b.x - x * b.z, x*b.y - y * b.x); }
    double dist(const Vec &b) const { return std::sqrt((x - b.x)*(x - b.x) + (y - b.y)*(y - b.y) + (z - b.z)*(z - b.z)); }
    double average() const { return (x + y + z) / 3.0; }
};
}
