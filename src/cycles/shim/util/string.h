/* Shim: replaces Cycles util/string.h without OIIO (upstream includes
 * OpenImageIO/string_view.h) */
/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: string_view is std::string_view, and only the declarations
 * that vendored code uses are kept. Upstream's helpers (string_printf, string_split,
 * string_startswith, ...) are declared when a vendored file calls them. The Windows UTF-8 to
 * UTF-16 conversion stays, because path_fopen needs it. */

#pragma once

#define PAINTERLY_SHIM_UTIL_STRING_H 1

/* Upstream's OpenImageIO/string_view.h provides the fixed-width integer types, and vendored
 * util/md5.h, util/path.h and util/md5.cpp use uint8_t, uint32_t and uint64_t through this header,
 * so the shim provides them too. */
#include <cstdint>
#include <cstring>
#include <string>
#include <string_view>

#include "util/vector.h"

CCL_NAMESPACE_BEGIN

using std::string;

using string_view = std::string_view;

/* Defined in src/cycles/shim/util/string.cpp. */
bool string_endswith(string_view s, string_view end);

/* Defined in src/cycles/shim/util/string.cpp. The lines below are util/string.h:27-33. */
#ifdef __GNUC__
#  define PRINTF_ATTRIBUTE __attribute__((format(printf, 1, 2)))
#else
#  define PRINTF_ATTRIBUTE
#endif

string string_printf(const char *format, ...) PRINTF_ATTRIBUTE;

#ifdef _WIN32
using std::wstring;

/* Defined in src/cycles/shim/util/string.cpp. */
wstring string_to_wstring(const string &str);
#endif

CCL_NAMESPACE_END
