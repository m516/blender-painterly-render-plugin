/* Shim: replaces Cycles util/string.cpp without OIIO (upstream's string.h includes
 * OpenImageIO/string_view.h) */
/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: defines only string_endswith, which
 * scene/shader_nodes.cpp:6216 calls, and string_to_wstring, which path_fopen calls on Windows. The
 * functions are copied from upstream util/string.cpp (lines 120-135 and 244-250). The other
 * helpers of upstream's file are not declared in the shim util/string.h, so they are not defined
 * here. */

#include "util/string.h"

#ifdef _WIN32
#  include "util/windows.h"
#endif

CCL_NAMESPACE_BEGIN

bool string_endswith(const string_view s, const string_view end)
{
  const size_t len = end.size();
  if (len > s.size()) {
    return false;
  }

  const size_t offset = s.size() - len;
  for (size_t i = 0; i < len; i++) {
    if (s[offset + i] != end[i]) {
      return false;
    }
  }

  return true;
}

#ifdef _WIN32

wstring string_to_wstring(const string &str)
{
  const int length_wc = MultiByteToWideChar(CP_UTF8, 0, str.c_str(), str.length(), nullptr, 0);
  wstring str_wc(length_wc, 0);
  MultiByteToWideChar(CP_UTF8, 0, str.c_str(), str.length(), &str_wc[0], length_wc);
  return str_wc;
}

#endif /* _WIN32 */

CCL_NAMESPACE_END
