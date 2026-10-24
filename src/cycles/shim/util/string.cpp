/* Shim: replaces Cycles util/string.cpp without OIIO (upstream's string.h includes
 * OpenImageIO/string_view.h) */
/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: defines only string_printf, which
 * SVMCompiler::Summary::full_report() (scene/svm.cpp:1251-1267) calls, string_endswith, which
 * scene/shader_nodes.cpp:6216 calls, and string_to_wstring, which path_fopen calls on Windows. The
 * functions are copied from upstream util/string.cpp (lines 23-53, 120-135 and 244-250).
 * string_printf calls the C library's vsnprintf on every platform; upstream maps it to _vsnprintf
 * on Windows (lines 14-19), whose -1 on truncation the same loop handles. The other helpers of
 * upstream's file are not declared in the shim util/string.h, so they are not defined here. */

#include <cassert>
#include <cstdarg>
#include <cstdio>

#include "util/string.h"

#ifdef _WIN32
#  include "util/windows.h"
#endif

CCL_NAMESPACE_BEGIN

string string_printf(const char *format, ...)
{
  vector<char> str(128, 0);

  while (true) {
    va_list args;
    int result;

    va_start(args, format);
    result = vsnprintf(str.data(), str.size(), format, args);
    va_end(args);

    if (result == -1) {
      /* not enough space or formatting error */
      if (str.size() > 65536) {
        assert(0);
        return string("");
      }

      str.resize(str.size() * 2, 0);
      continue;
    }
    if (result >= (int)str.size()) {
      /* not enough space */
      str.resize(result + 1, 0);
      continue;
    }

    return string(str.data());
  }
}

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
