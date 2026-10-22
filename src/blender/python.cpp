/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

// Native core of the Painterly render engine: the nanobind module _painterly. Every public name,
// argument, default, shape and dtype is the contract of src/blender/_painterly.pyi (T3.15); this
// file implements it and never changes it. The conversions below are the thin layer between
// Python objects and the host classes PainterlyScene (painterly/scene/scene.h) and
// PainterlySession (painterly/session/session.h), which are the C++ classes the Python `Scene` and
// `Session` bind.

#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
// std::string <-> Python str. Without this caster nanobind raises std::bad_cast
// when the dict is filled.
#include <nanobind/stl/optional.h>
#include <nanobind/stl/string.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <limits>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "painterly/integrator/buffers.h"
#include "painterly/kernel/sample/sampler.h"
#include "painterly/kernel/types.h"
#include "painterly/scene/integrator.h"
#include "painterly/scene/scene.h"
#include "painterly/session/session.h"
#include "painterly/util/math_double3.h"
#include "painterly/util/types_double3.h"
#include "selftest.h"

namespace nb = nanobind;

#define PAINTERLY_STR_(x) #x
#define PAINTERLY_STR(x) PAINTERLY_STR_(x)

// The compiler string is "<id> <version>", for example "GCC 13.3.0". Clang also defines __GNUC__,
// so __clang__ is tested first. Apple's Clang defines __apple_build_version__ and is reported as
// AppleClang.
#if defined(__clang__)
#  if defined(__apple_build_version__)
#    define PAINTERLY_COMPILER_ID "AppleClang"
#  else
#    define PAINTERLY_COMPILER_ID "Clang"
#  endif
#  define PAINTERLY_COMPILER_VERSION \
    PAINTERLY_STR(__clang_major__) \
    "." PAINTERLY_STR(__clang_minor__) "." PAINTERLY_STR(__clang_patchlevel__)
#elif defined(__GNUC__)
#  define PAINTERLY_COMPILER_ID "GCC"
#  define PAINTERLY_COMPILER_VERSION \
    PAINTERLY_STR(__GNUC__) \
    "." PAINTERLY_STR(__GNUC_MINOR__) "." PAINTERLY_STR(__GNUC_PATCHLEVEL__)
#elif defined(_MSC_VER)
#  define PAINTERLY_COMPILER_ID "MSVC"
#  define PAINTERLY_COMPILER_VERSION PAINTERLY_STR(_MSC_FULL_VER)
#else
#  error \
      "unknown compiler: add a branch for its id and version to PAINTERLY_COMPILER in python.cpp"
#endif
#define PAINTERLY_COMPILER PAINTERLY_COMPILER_ID " " PAINTERLY_COMPILER_VERSION

// NDEBUG is the standard C/C++ switch for optimised builds (CMake Release sets it).
#if defined(NDEBUG)
#  define PAINTERLY_BUILD_TYPE "Release"
#else
#  define PAINTERLY_BUILD_TYPE "Debug"
#endif

CCL_NAMESPACE_BEGIN

namespace {

// ---------------------------------------------------------------------------------------------
// version_info and selftest
// ---------------------------------------------------------------------------------------------

nb::dict version_info()
{
  // Py_LIMITED_API is defined by nanobind's STABLE_ABI option.
#if defined(Py_LIMITED_API)
  const bool stable_abi = true;
#else
  const bool stable_abi = false;
#endif

  nb::dict info;
  info["version"] = PAINTERLY_VERSION;
  info["compiler"] = PAINTERLY_COMPILER;
  info["build_type"] = PAINTERLY_BUILD_TYPE;
  info["stable_abi"] = stable_abi;
  return info;
}

nb::dict selftest()
{
  const painterly::SelftestResult result = painterly::selftest_embree();
  nb::dict info;
  info["embree_version"] = result.embree_version;
  info["tasking_system"] = result.tasking_system;
  info["hit"] = result.hit;
  info["t"] = result.t;
  info["prim_id"] = result.prim_id;
  return info;
}

// ---------------------------------------------------------------------------------------------
// integrator_sockets(): the NodeType socket data merged with painterly_integrator_ui_info()
// ---------------------------------------------------------------------------------------------

// The pyi's SocketInfo["type"] spelling of a NodeType socket type. The pyi's literal list is
// "boolean", "int", "uint", "float", "enum", "vector", and PainterlyIntegrator uses exactly these
// six (painterly/scene/integrator.h).
const char *socket_type_name(const SocketType::Type type)
{
  switch (type) {
    case SocketType::BOOLEAN:
      return "boolean";
    case SocketType::INT:
      return "int";
    case SocketType::UINT:
      return "uint";
    case SocketType::FLOAT:
      return "float";
    case SocketType::ENUM:
      return "enum";
    case SocketType::VECTOR:
      return "vector";
    default:
      throw std::runtime_error("integrator_sockets: unsupported socket type " +
                               SocketType::type_name(type).string());
  }
}

// The identifier of an enum value, looked up in the socket's own items (graph/node_enum.h maps
// value -> identifier).
std::string enum_identifier(const NodeEnum &values, const int value, const std::string &what)
{
  for (auto it = values.begin(); it != values.end(); ++it) {
    if (it->second == value) {
      return it->first.string();
    }
  }
  throw std::runtime_error(what + ": enum value " + std::to_string(value) +
                           " is not one of the socket's items");
}

// The socket's default, converted by its type: bool, int, float, the enum identifier string, or
// the (x, y, z) tuple of a vector. The NodeType stores the default as a pointer to a static of the
// socket's own type (graph/node_type.h, the SOCKET_* macros), which is what the casts read.
nb::object socket_default(const SocketType &socket)
{
  switch (socket.type) {
    case SocketType::BOOLEAN:
      return nb::bool_(*static_cast<const bool *>(socket.default_value));
    case SocketType::INT:
      return nb::int_(*static_cast<const int *>(socket.default_value));
    case SocketType::UINT:
      return nb::int_(*static_cast<const uint *>(socket.default_value));
    case SocketType::FLOAT:
      return nb::float_(*static_cast<const float *>(socket.default_value));
    case SocketType::ENUM:
      return nb::str(enum_identifier(*socket.enum_values,
                                     *static_cast<const int *>(socket.default_value),
                                     "integrator_sockets")
                         .c_str());
    case SocketType::VECTOR: {
      const float3 value = *static_cast<const float3 *>(socket.default_value);
      return nb::make_tuple(nb::float_(value.x), nb::float_(value.y), nb::float_(value.z));
    }
    default:
      throw std::runtime_error("integrator_sockets: unsupported socket type " +
                               SocketType::type_name(socket.type).string());
  }
}

// A std::optional<double> limit as a Python float or None (painterly/scene/integrator.h, D17).
nb::object socket_limit(const std::optional<double> &limit)
{
  if (!limit.has_value()) {
    return nb::none();
  }
  return nb::float_(*limit);
}

// The enum items in C++ value order (D16). NodeEnum iterates its hash map, which is not the C++
// value order, so the items are sorted by their integer value.
std::vector<std::string> socket_enum_items(const SocketType &socket)
{
  std::vector<std::pair<int, std::string>> keyed;
  const NodeEnum &values = *socket.enum_values;
  for (auto it = values.begin(); it != values.end(); ++it) {
    keyed.emplace_back(it->second, it->first.string());
  }
  std::sort(keyed.begin(), keyed.end());
  std::vector<std::string> items;
  items.reserve(keyed.size());
  for (const auto &entry : keyed) {
    items.push_back(entry.second);
  }
  return items;
}

nb::list integrator_sockets()
{
  const NodeType *type = PainterlyIntegrator::get_node_type();
  const std::vector<PainterlySocketUIInfo> &ui_info = painterly_integrator_ui_info();

  nb::list sockets;
  for (const SocketType &socket : type->inputs) {
    // One UI entry per socket, in socket order (painterly/scene/integrator.h; a doctest asserts
    // it). The lookup is by name, so a reordering cannot silently pair the wrong texts.
    const PainterlySocketUIInfo *ui = nullptr;
    for (const PainterlySocketUIInfo &entry : ui_info) {
      if (socket.name == ustring(entry.name)) {
        ui = &entry;
        break;
      }
    }
    if (ui == nullptr) {
      throw std::runtime_error("integrator_sockets: no UI info for socket " +
                               socket.name.string());
    }

    nb::list enum_items;
    if (socket.type == SocketType::ENUM) {
      for (const std::string &item : socket_enum_items(socket)) {
        enum_items.append(item);
      }
    }

    nb::dict info;
    info["name"] = socket.name.string();
    info["type"] = socket_type_name(socket.type);
    info["default"] = socket_default(socket);
    info["enum_items"] = enum_items;
    info["min"] = socket_limit(ui->min);
    info["max"] = socket_limit(ui->max);
    info["soft_min"] = socket_limit(ui->soft_min);
    info["soft_max"] = socket_limit(ui->soft_max);
    info["ui_name"] = ui->ui_name;
    info["description"] = ui->description;
    info["group"] = ui->group;
    sockets.append(info);
  }
  return sockets;
}

// ---------------------------------------------------------------------------------------------
// Value conversion by socket type (Scene.set_integrator / Scene.get_integrator)
// ---------------------------------------------------------------------------------------------

// A Python real number as a C double, exactly as PyFloat_AsDouble converts one: any object with
// __float__ (int, float and numpy scalars included) is accepted. The pyi types the knobs by
// socket, never by a strict PyFloat_Check, because T3.16 and T4.3 pass numpy float32 scalars and
// ints.
double as_real(nb::handle value, const std::string &what)
{
  const double converted = PyFloat_AsDouble(value.ptr());
  if (converted == -1.0 && PyErr_Occurred()) {
    PyErr_Clear();
    throw nb::type_error((what + " must be a real number").c_str());
  }
  return converted;
}

// A Python integer through __index__ (int, numpy integers and anything else with __index__), as a
// C long long. A bool is not an integer here: it is a wrong type for every int socket.
long long as_integer(nb::handle value, const std::string &what)
{
  if (PyBool_Check(value.ptr())) {
    throw nb::type_error((what + " must be an int, not a bool").c_str());
  }
  PyObject *indexed = PyNumber_Index(value.ptr());
  if (indexed == nullptr) {
    PyErr_Clear();
    throw nb::type_error((what + " must be an int").c_str());
  }
  const nb::object owned = nb::steal(indexed);
  const long long converted = PyLong_AsLongLong(owned.ptr());
  if (converted == -1 && PyErr_Occurred()) {
    PyErr_Clear();
    throw nb::value_error((what + " is out of range").c_str());
  }
  return converted;
}

// The three kernel preconditions of painterly/kernel/types.h (T3.15, T3.20). Every other range is
// a UI limit (T3.13), not a behaviour, so it is not checked here.
void check_integrator_precondition(const std::string &name, const long long value)
{
  if (name == "lane_length" && value < 1) {
    throw nb::value_error("set_integrator: lane_length must be >= 1");
  }
  // SPEC §3: K0 has PAINTERLY_K0_BITS = 22 bits (painterly/kernel/sample/sampler.h), and `1u << q`
  // is undefined from q = 32, so the phase lock accepts 0…22 and nothing else.
  if (name == "k0_phase_lock_bits" && (value < 0 || value > PAINTERLY_K0_BITS)) {
    throw nb::value_error("set_integrator: k0_phase_lock_bits must be in 0…22");
  }
  // T3.20: the oracle's --max-depth is N >= 1, and PainterlyPathTrace throws below it.
  if (name == "max_depth" && value < 1) {
    throw nb::value_error("set_integrator: max_depth must be >= 1");
  }
}

// One socket value from Python, converted by the socket's type and written to `integrator`. The
// type table is the pyi's: a boolean is a bool, an int/uint an integer, a float any real number
// stored as float32, an enum an identifier string of the socket's items, a vector a 3-sequence of
// reals.
void set_socket_from_python(PainterlyIntegrator &integrator,
                            const SocketType &socket,
                            nb::handle value)
{
  const std::string name = socket.name.string();
  const std::string what = "set_integrator: " + name;
  switch (socket.type) {
    case SocketType::BOOLEAN:
      // bool only: the check is the type, not the truthiness, so set_integrator(two_sided=1) is a
      // wrong type rather than a silent conversion.
      if (!PyBool_Check(value.ptr())) {
        throw nb::type_error((what + " must be a bool").c_str());
      }
      integrator.set(socket, value.ptr() == Py_True);
      return;
    case SocketType::INT:
    case SocketType::UINT: {
      const long long converted = as_integer(value, what);
      if (socket.type == SocketType::UINT) {
        // seed is the one uint socket. The Node stores a 32-bit unsigned value.
        if (converted < 0 ||
            static_cast<unsigned long long>(converted) > std::numeric_limits<unsigned int>::max())
        {
          throw nb::value_error((what + " is out of range").c_str());
        }
        integrator.set(socket, static_cast<uint>(converted));
        return;
      }
      if (converted < std::numeric_limits<int>::min() ||
          converted > std::numeric_limits<int>::max())
      {
        throw nb::value_error((what + " is out of range").c_str());
      }
      check_integrator_precondition(name, converted);
      integrator.set(socket, static_cast<int>(converted));
      return;
    }
    case SocketType::FLOAT:
      // Any real number, converted as PyFloat_AsDouble does; the socket stores its float32 value
      // (the pyi's "stores its float32 value").
      integrator.set(socket, static_cast<float>(as_real(value, what)));
      return;
    case SocketType::ENUM: {
      if (!PyUnicode_Check(value.ptr())) {
        throw nb::type_error((what + " must be an enum identifier string").c_str());
      }
      const std::string identifier = nb::cast<std::string>(value);
      const NodeEnum &values = *socket.enum_values;
      if (!values.exists(ustring(identifier))) {
        throw nb::value_error((what + " has no item \"" + identifier + "\"").c_str());
      }
      integrator.set(socket, values[ustring(identifier)]);
      return;
    }
    case SocketType::VECTOR: {
      nb::sequence sequence;
      if (!nb::try_cast<nb::sequence>(value, sequence) || nb::len(sequence) != 3) {
        throw nb::type_error((what + " must be a (x, y, z) sequence").c_str());
      }
      const double x = as_real(sequence[0], what);
      const double y = as_real(sequence[1], what);
      const double z = as_real(sequence[2], what);
      integrator.set(socket, make_float3(float(x), float(y), float(z)));
      return;
    }
    default:
      throw nb::type_error((what + ": unsupported socket type").c_str());
  }
}

// The current value of a socket, converted by its type (Scene.get_integrator). A float value is
// the socket's float32, widened to a Python float.
nb::object get_socket(const PainterlyIntegrator &integrator, const SocketType &socket)
{
  switch (socket.type) {
    case SocketType::BOOLEAN:
      return nb::bool_(integrator.get_bool(socket));
    case SocketType::INT:
      return nb::int_(integrator.get_int(socket));
    case SocketType::UINT:
      return nb::int_(integrator.get_uint(socket));
    case SocketType::FLOAT:
      return nb::float_(double(integrator.get_float(socket)));
    case SocketType::ENUM:
      return nb::str(
          enum_identifier(*socket.enum_values, integrator.get_int(socket), "get_integrator")
              .c_str());
    case SocketType::VECTOR: {
      const float3 value = integrator.get_float3(socket);
      return nb::make_tuple(
          nb::float_(double(value.x)), nb::float_(double(value.y)), nb::float_(double(value.z)));
    }
    default:
      throw std::runtime_error("get_integrator: unsupported socket type for " +
                               socket.name.string());
  }
}

// ---------------------------------------------------------------------------------------------
// Array inputs and the other typed arguments of Scene. The pyi makes every dtype and shape part of
// the contract, so a wrong one raises TypeError: there is no silent conversion (nanobind's
// convert = false).
// ---------------------------------------------------------------------------------------------

template<typename T>
nb::ndarray<nb::numpy, const T, nb::c_contig> cast_array(nb::handle value, const std::string &what)
{
  nb::ndarray<nb::numpy, const T, nb::c_contig> array;
  if (!nb::try_cast<nb::ndarray<nb::numpy, const T, nb::c_contig>>(value, array, false)) {
    throw nb::type_error((what + ": expected a C-contiguous numpy array of the exact dtype " +
                          std::string(nb::detail::dtype_traits<T>::name.text))
                             .c_str());
  }
  return array;
}

// A (rows, cols) array of `T`, row-major and C-contiguous, as `std::vector<T>`.
template<typename T>
std::vector<T> matrix_from_python(nb::handle value,
                                  const std::string &what,
                                  const size_t rows,
                                  const size_t cols)
{
  const auto array = cast_array<T>(value, what);
  if (array.ndim() != 2 || array.shape(0) != rows || array.shape(1) != cols) {
    throw nb::type_error(
        (what + ": expected shape (" + std::to_string(rows) + ", " + std::to_string(cols) + ")")
            .c_str());
  }
  return std::vector<T>(array.data(), array.data() + rows * cols);
}

// The pyi's LobeKind spellings of PainterlyLobeKind (painterly/kernel/types.h, SPEC §6).
int lobe_kind_from_python(nb::handle value)
{
  if (!PyUnicode_Check(value.ptr())) {
    throw nb::type_error("Scene.add_material: a lobe kind must be a string");
  }
  const std::string kind = nb::cast<std::string>(value);
  if (kind == "diffuse") {
    return LOBE_DIFFUSE;
  }
  if (kind == "mirror") {
    return LOBE_MIRROR;
  }
  if (kind == "glass") {
    return LOBE_GLASS;
  }
  if (kind == "transparent") {
    return LOBE_TRANSPARENT;
  }
  throw nb::value_error(("Scene.add_material: unknown lobe kind \"" + kind + "\"").c_str());
}

// The pyi's "ghost" / "exact" (PainterlySphereIntersection, SPEC §5, §9).
int sphere_intersection_from_python(nb::handle value)
{
  if (!PyUnicode_Check(value.ptr())) {
    throw nb::type_error("Scene.add_sphere: intersection must be \"ghost\" or \"exact\"");
  }
  const std::string intersection = nb::cast<std::string>(value);
  if (intersection == "ghost") {
    return SPHERE_GHOST;
  }
  if (intersection == "exact") {
    return SPHERE_EXACT;
  }
  throw nb::value_error(
      ("Scene.add_sphere: unknown intersection \"" + intersection + "\"").c_str());
}

// The pyi's "horizontal" / "vertical" (PainterlyCameraFit, SPEC §7).
PainterlyCameraFit camera_fit_from_python(nb::handle value)
{
  if (!PyUnicode_Check(value.ptr())) {
    throw nb::type_error("Scene: fit must be \"horizontal\" or \"vertical\"");
  }
  const std::string fit = nb::cast<std::string>(value);
  if (fit == "horizontal") {
    return PainterlyCameraFit::FIT_HORIZONTAL;
  }
  if (fit == "vertical") {
    return PainterlyCameraFit::FIT_VERTICAL;
  }
  throw nb::value_error(("Scene: unknown fit \"" + fit + "\"").c_str());
}

// A (x, y, z) sequence of real numbers as a double3, converted as PyFloat_AsDouble does.
double3 double3_from_python(nb::handle value, const std::string &what)
{
  nb::sequence sequence;
  if (!nb::try_cast<nb::sequence>(value, sequence) || nb::len(sequence) != 3) {
    throw nb::type_error((what + ": expected a (x, y, z) sequence").c_str());
  }
  const double x = as_real(sequence[0], what);
  const double y = as_real(sequence[1], what);
  const double z = as_real(sequence[2], what);
  return make_double3(x, y, z);
}

// The (3, 4) or (4, 4) row-major object_to_world of the pyi, as the 3x4 affine the core stores. A
// 4x4's last row is the affine's (0, 0, 0, 1), so its first three rows are the 3x4.
std::array<float, 12> object_to_world_from_python(nb::handle value, const std::string &what)
{
  const auto array = cast_array<float>(value, what);
  if (array.ndim() != 2) {
    throw nb::type_error((what + ": expected a 2-dimensional array").c_str());
  }
  const size_t rows = array.shape(0);
  const size_t cols = array.shape(1);
  if (!((rows == 3 && cols == 4) || (rows == 4 && cols == 4))) {
    throw nb::type_error((what + ": expected shape (3, 4) or (4, 4)").c_str());
  }
  std::array<float, 12> transform{};
  for (size_t row = 0; row < 3; row++) {
    for (size_t col = 0; col < 4; col++) {
      transform[4 * row + col] = array.data()[cols * row + col];
    }
  }
  return transform;
}

// A (4, 4) or (3, 4) row-major float64 matrix as a 3x4 affine (camera_to_world of the pyi).
std::array<double, 12> affine_3x4_from_python(nb::handle value, const std::string &what)
{
  const auto array = cast_array<double>(value, what);
  if (array.ndim() != 2) {
    throw nb::type_error((what + ": expected a 2-dimensional array").c_str());
  }
  const size_t rows = array.shape(0);
  const size_t cols = array.shape(1);
  if (!((rows == 3 && cols == 4) || (rows == 4 && cols == 4))) {
    throw nb::type_error((what + ": expected shape (3, 4) or (4, 4)").c_str());
  }
  std::array<double, 12> transform{};
  for (size_t row = 0; row < 3; row++) {
    for (size_t col = 0; col < 4; col++) {
      transform[4 * row + col] = array.data()[cols * row + col];
    }
  }
  return transform;
}

// The session's report as the pyi's progress() dict (D13's state strings).
const char *session_state_name(const PainterlySessionState state)
{
  switch (state) {
    case PainterlySessionState::STATE_IDLE:
      return "idle";
    case PainterlySessionState::STATE_RENDERING:
      return "rendering";
    case PainterlySessionState::STATE_DONE:
      return "done";
    case PainterlySessionState::STATE_CANCELLED:
      return "cancelled";
    case PainterlySessionState::STATE_ERROR:
      return "error";
  }
  throw std::runtime_error("progress: unknown session state");
}

// A fresh numpy array that owns a copy of `values` (combined(), k_consumed(), object_id()). The
// caller can never see a later batch through it (T3.15).
template<typename T>
nb::ndarray<nb::numpy, T> numpy_copy(const std::vector<T> &values,
                                     const std::vector<size_t> &shape)
{
  auto *heap = new std::vector<T>(values);
  if (heap->empty()) {
    // numpy wants a non-null data pointer even for a zero-size array; the shape stays as given.
    heap->resize(1);
  }
  nb::capsule owner(heap,
                    [](void *pointer) noexcept { delete static_cast<std::vector<T> *>(pointer); });
  return nb::ndarray<nb::numpy, T>(heap->data(), shape.size(), shape.data(), owner);
}

// ---------------------------------------------------------------------------------------------
// The module
// ---------------------------------------------------------------------------------------------

void bind_module(nb::module_ &m)
{
  m.doc() = "Native core of the Painterly render engine (mirrors Cycles' _cycles).";
  m.def("version_info", &version_info, "Return version and build information as a dict.");
  m.def("selftest",
        &selftest,
        "Trace one triangle through painterly_bvh. Return a dict with embree_version, "
        "tasking_system, hit, t and prim_id.");
  m.def("integrator_sockets",
        &integrator_sockets,
        "Reflection of PainterlyIntegrator (SPEC §8): one dict per socket, in socket order.");

  nb::class_<PainterlyScene>(m, "Scene")
      .def(nb::init<>())
      .def("clear", [](PainterlyScene &self) { self.clear(); })
      .def(
          "add_material",
          [](PainterlyScene &self, nb::object lobes, nb::object emission) {
            nb::sequence lobe_list;
            if (!nb::try_cast<nb::sequence>(lobes, lobe_list)) {
              throw nb::type_error("Scene.add_material: lobes must be a list of lobes");
            }
            std::vector<KernelPainterlyLobe> converted;
            for (size_t i = 0; i < nb::len(lobe_list); i++) {
              nb::sequence lobe;
              if (!nb::try_cast<nb::sequence>(lobe_list[i], lobe) || nb::len(lobe) != 3) {
                throw nb::type_error("Scene.add_material: a lobe is (kind, (r, g, b), ior)");
              }
              KernelPainterlyLobe kernel_lobe{};
              kernel_lobe.kind = lobe_kind_from_python(lobe[0]);
              kernel_lobe.weight = double3_from_python(lobe[1], "add_material");
              kernel_lobe.ior = as_real(lobe[2], "Scene.add_material: ior");
              converted.push_back(kernel_lobe);
            }
            return self.add_material(converted,
                                     double3_from_python(emission, "add_material: emission"));
          },
          nb::arg("lobes"),
          nb::arg("emission") = nb::make_tuple(0.0, 0.0, 0.0))
      .def(
          "add_sphere",
          [](PainterlyScene &self,
             nb::object center,
             nb::object radius,
             const int material,
             nb::object intersection,
             const int object_id,
             nb::object spot) {
            KernelPainterlySpotProfile profile{0, make_double3(0.0), 1.0, 0.0};
            if (!spot.is_none()) {
              nb::sequence fields;
              if (!nb::try_cast<nb::sequence>(spot, fields) || nb::len(fields) != 3) {
                throw nb::type_error(
                    "Scene.add_sphere: spot must be (axis, cos_half_angle, blend) or None");
              }
              nb::sequence axis;
              if (!nb::try_cast<nb::sequence>(fields[0], axis) || nb::len(axis) != 3) {
                throw nb::type_error("Scene.add_sphere: the spot axis must be (x, y, z)");
              }
              profile.enabled = 1;
              profile.direction = double3_from_python(fields[0], "add_sphere: spot axis");
              profile.cos_half_angle = as_real(fields[1], "Scene.add_sphere: cos_half_angle");
              profile.blend = as_real(fields[2], "Scene.add_sphere: blend");
            }
            return self.add_sphere(double3_from_python(center, "add_sphere: center"),
                                   as_real(radius, "Scene.add_sphere: radius"),
                                   material,
                                   static_cast<PainterlySphereIntersection>(
                                       sphere_intersection_from_python(intersection)),
                                   object_id,
                                   spot.is_none() ? nullptr : &profile);
          },
          nb::arg("center"),
          nb::arg("radius"),
          nb::arg("material"),
          nb::arg("intersection") = "ghost",
          nb::arg("object_id") = -1,
          nb::arg("spot") = nb::none())
      .def(
          "add_plane",
          [](PainterlyScene &self,
             nb::object normal,
             nb::object d,
             const int material,
             const int object_id) {
            return self.add_plane(double3_from_python(normal, "add_plane: normal"),
                                  as_real(d, "Scene.add_plane: d"),
                                  material,
                                  object_id);
          },
          nb::arg("normal"),
          nb::arg("d"),
          nb::arg("material"),
          nb::arg("object_id") = -1)
      .def(
          "add_mesh",
          [](PainterlyScene &self,
             nb::object vertices,
             nb::object triangles,
             nb::object tri_material,
             nb::object corner_normals) {
            const auto vertex_array = cast_array<float>(vertices, "Scene.add_mesh: vertices");
            if (vertex_array.ndim() != 2 || vertex_array.shape(1) != PAINTERLY_POINT_FLOATS) {
              throw nb::type_error("Scene.add_mesh: vertices must have shape (V, 3)");
            }
            const auto triangle_array = cast_array<uint32_t>(triangles,
                                                             "Scene.add_mesh: triangles");
            if (triangle_array.ndim() != 2 ||
                triangle_array.shape(1) != PAINTERLY_TRIANGLE_CORNERS) {
              throw nb::type_error("Scene.add_mesh: triangles must have shape (T, 3)");
            }
            const auto material_array = cast_array<int32_t>(tri_material,
                                                            "Scene.add_mesh: tri_material");
            if (material_array.ndim() != 1 || material_array.shape(0) != triangle_array.shape(0)) {
              throw nb::type_error("Scene.add_mesh: tri_material must have shape (T,)");
            }
            std::vector<float> corner_normal_values;
            if (!corner_normals.is_none()) {
              const auto normal_array = cast_array<float>(corner_normals,
                                                          "Scene.add_mesh: corner_normals");
              if (normal_array.ndim() != 3 || normal_array.shape(0) != triangle_array.shape(0) ||
                  normal_array.shape(1) != PAINTERLY_TRIANGLE_CORNERS ||
                  normal_array.shape(2) != PAINTERLY_POINT_FLOATS)
              {
                throw nb::type_error("Scene.add_mesh: corner_normals must have shape (T, 3, 3)");
              }
              corner_normal_values.assign(normal_array.data(),
                                          normal_array.data() + normal_array.size());
            }
            std::vector<float> vertex_values(vertex_array.data(),
                                             vertex_array.data() + vertex_array.size());
            std::vector<uint32_t> triangle_values(triangle_array.data(),
                                                  triangle_array.data() + triangle_array.size());
            std::vector<int> material_values(material_array.data(),
                                             material_array.data() + material_array.size());
            return self.add_mesh(
                vertex_values, triangle_values, material_values, corner_normal_values);
          },
          nb::arg("vertices"),
          nb::arg("triangles"),
          nb::arg("tri_material"),
          nb::arg("corner_normals") = nb::none())
      .def(
          "add_object",
          [](PainterlyScene &self,
             const int mesh,
             nb::object object_to_world,
             const int object_id) {
            const std::array<float, 12> transform = object_to_world_from_python(
                object_to_world, "Scene.add_object: object_to_world");
            return self.add_object(mesh, transform.data(), object_id);
          },
          nb::arg("mesh"),
          nb::arg("object_to_world"),
          nb::arg("object_id") = -1)
      .def(
          "set_camera_smallpaint",
          [](PainterlyScene &self, const int width, const int height) {
            self.set_camera_smallpaint(width, height);
          },
          nb::arg("width"),
          nb::arg("height"))
      .def(
          "set_camera_perspective",
          [](PainterlyScene &self,
             const int width,
             const int height,
             nb::object raster_to_camera,
             nb::object camera_to_world,
             nb::object fit) {
            const std::vector<double> raster = matrix_from_python<double>(
                raster_to_camera, "Scene.set_camera_perspective: raster_to_camera", 4, 4);
            const std::array<double, 12> world = affine_3x4_from_python(
                camera_to_world, "Scene.set_camera_perspective: camera_to_world");
            self.set_camera_perspective(
                width, height, raster.data(), world.data(), camera_fit_from_python(fit));
          },
          nb::arg("width"),
          nb::arg("height"),
          nb::arg("raster_to_camera"),
          nb::arg("camera_to_world"),
          nb::arg("fit"))
      .def(
          "set_camera_orthographic",
          [](PainterlyScene &self,
             const int width,
             const int height,
             nb::object raster_to_camera,
             nb::object camera_to_world,
             nb::object fit) {
            const std::vector<double> raster = matrix_from_python<double>(
                raster_to_camera, "Scene.set_camera_orthographic: raster_to_camera", 4, 4);
            const std::array<double, 12> world = affine_3x4_from_python(
                camera_to_world, "Scene.set_camera_orthographic: camera_to_world");
            self.set_camera_orthographic(
                width, height, raster.data(), world.data(), camera_fit_from_python(fit));
          },
          nb::arg("width"),
          nb::arg("height"),
          nb::arg("raster_to_camera"),
          nb::arg("camera_to_world"),
          nb::arg("fit"))
      .def(
          "set_background",
          [](PainterlyScene &self, nb::object radiance) {
            self.set_background(double3_from_python(radiance, "set_background"));
          },
          nb::arg("radiance"))
      .def(
          "set_spiral_object",
          [](PainterlyScene &self, nb::object rotation) {
            const std::vector<double> values = matrix_from_python<double>(
                rotation, "Scene.set_spiral_object: rotation", 3, 3);
            self.set_spiral_object(values.data());
          },
          nb::arg("rotation"))
      .def(
          "add_sun",
          [](PainterlyScene &self, nb::object direction, nb::object angle, nb::object radiance) {
            return self.add_sun(double3_from_python(direction, "add_sun: direction"),
                                as_real(angle, "Scene.add_sun: angle"),
                                double3_from_python(radiance, "add_sun: radiance"));
          },
          nb::arg("direction"),
          nb::arg("angle"),
          nb::arg("radiance"))
      .def(
          "set_integrator",
          [](PainterlyScene &self, nb::kwargs knobs) {
            const NodeType *type = PainterlyIntegrator::get_node_type();
            for (const auto &item : knobs) {
              const std::string name = nb::cast<std::string>(nb::str(item.first));
              const SocketType *socket = type->find_input(ustring(name));
              if (socket == nullptr) {
                throw nb::value_error(("set_integrator: unknown socket \"" + name + "\"").c_str());
              }
              set_socket_from_python(self.integrator, *socket, item.second);
            }
          },
          nb::arg("knobs"))
      .def("get_integrator", [](const PainterlyScene &self) {
        const NodeType *type = PainterlyIntegrator::get_node_type();
        nb::dict values;
        for (const SocketType &socket : type->inputs) {
          values[socket.name.string().c_str()] = get_socket(self.integrator, socket);
        }
        return values;
      });

  nb::class_<PainterlySession>(m, "Session")
      .def(nb::init<const PainterlyScene &, int>(),
           nb::arg("scene"),
           nb::arg("threads") = 0,
           // The session holds a reference to its scene until start() takes the snapshot, so the
           // Python Scene must outlive the Session (T3.15).
           nb::keep_alive<1, 2>())
      .def(
          "start",
          [](PainterlySession &self, const int passes, const int batch) {
            self.start(passes, batch);
          },
          nb::arg("passes"),
          nb::arg("batch") = 1,
          // The snapshot of start() and the start-up of the render thread happen while this call
          // runs, and nothing in it needs the GIL, so it is released (T3.15).
          nb::call_guard<nb::gil_scoped_release>())
      .def(
          "wait",
          [](PainterlySession &self, const std::optional<double> timeout) {
            // session.h: a negative timeout waits forever, which is the pyi's None.
            return self.wait(timeout.has_value() ? *timeout : -1.0);
          },
          nb::arg("timeout") = nb::none(),
          // Blocking with the GIL held would freeze every Python thread for the whole render, so
          // the GIL is released for the wait (T3.15).
          nb::call_guard<nb::gil_scoped_release>())
      .def("cancel", [](PainterlySession &self) { self.cancel(); })
      .def("progress",
           [](const PainterlySession &self) {
             const PainterlySessionProgress progress = self.progress();
             nb::dict report;
             report["state"] = session_state_name(progress.state);
             report["passes_done"] = progress.passes_done;
             report["passes_total"] = progress.passes_total;
             report["elapsed"] = progress.elapsed;
             report["error"] = progress.error;
             return report;
           })
      .def("combined",
           [](const PainterlySession &self) {
             const PainterlyRenderBuffers buffers = self.buffers_copy();
             return numpy_copy<double>(
                 buffers.combined,
                 {size_t(buffers.height), size_t(buffers.width), size_t(PAINTERLY_CHANNELS)});
           })
      .def("k_consumed",
           [](const PainterlySession &self) {
             const PainterlyRenderBuffers buffers = self.buffers_copy();
             return numpy_copy<uint64_t>(buffers.k_consumed,
                                         {size_t(buffers.height), size_t(buffers.width)});
           })
      .def("object_id", [](const PainterlySession &self) {
        const PainterlyRenderBuffers buffers = self.buffers_copy();
        return numpy_copy<int32_t>(buffers.object_id,
                                   {size_t(buffers.height), size_t(buffers.width)});
      });
}

}  // namespace

CCL_NAMESPACE_END

NB_MODULE(_painterly, m)
{
  painterly::bind_module(m);
}
