/* Shim: replaces Cycles util/param.h without OIIO (upstream includes
 * OpenImageIO/paramlist.h, typedesc.h and ustring.h) */
/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* ustring: an interned, immutable string that stands in for OpenImageIO's ustring, the only
 * parameter type that vendored graph reflection uses (graph/node.h, graph/node_type.h,
 * graph/node_enum.h). Equal strings share one interned copy, so
 * == and != compare pointers. Interned copies are never freed, so c_str() and string() stay valid
 * for the whole run. ustringhash is the same type: it is hashed by pointer, and no vendored file
 * needs OpenImageIO's precomputed hash. Upstream's TypeDesc and ParamValue are not provided,
 * because no vendored file in M3 uses them. */

#pragma once

#include <cstddef>
#include <functional>
#include <mutex>
#include <string>
#include <string_view>
#include <unordered_set>

CCL_NAMESPACE_BEGIN

class ustring {
 public:
  /* The empty string. */
  ustring() : str_(empty_string()) {}
  /* A null pointer is the empty string, as in OpenImageIO. */
  ustring(const char *str) : str_(str ? intern(str) : empty_string()) {}
  ustring(std::string_view str) : str_(intern(str)) {}

  const char *c_str() const
  {
    return str_->c_str();
  }

  /* The interned copy. It is never modified, and it lives until the process exits. */
  const std::string &string() const
  {
    return *str_;
  }

  size_t size() const
  {
    return str_->size();
  }

  bool empty() const
  {
    return str_->empty();
  }

  /* Hash of the interned pointer: equal strings have equal hashes, which is all unordered
   * containers need. */
  size_t hash() const
  {
    return std::hash<const std::string *>()(str_);
  }

  bool operator==(const ustring &other) const
  {
    return str_ == other.str_;
  }

  bool operator!=(const ustring &other) const
  {
    return str_ != other.str_;
  }

  /* Lexicographic order of the contents, so that ordered containers do not depend on addresses. */
  bool operator<(const ustring &other) const
  {
    return *str_ < *other.str_;
  }

 private:
  static const std::string *empty_string()
  {
    static const std::string *empty = intern(std::string_view());
    return empty;
  }

  static const std::string *intern(std::string_view str);

  const std::string *str_;
};

using ustringhash = ustring;

CCL_NAMESPACE_END

namespace std {

/* Lets ustring key unordered containers, such as NodeEnum and NodeType::find's registry. */
template<> struct hash<painterly::ustring> {
  size_t operator()(const painterly::ustring &str) const noexcept
  {
    return str.hash();
  }
};

}  // namespace std

CCL_NAMESPACE_BEGIN

/* An inline function's static local is one object in the whole program, so every translation unit
 * shares one table. std::unordered_set keeps its elements at stable addresses, so the pointers
 * handed out stay valid as the table grows. */
inline const std::string *ustring::intern(std::string_view str)
{
  struct Table {
    std::mutex mutex;
    std::unordered_set<std::string> strings;
  };
  static Table table;
  std::lock_guard<std::mutex> lock(table.mutex);
  return &*table.strings.emplace(str).first;
}

CCL_NAMESPACE_END
