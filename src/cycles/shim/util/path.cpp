/* Shim: replaces Cycles util/path.cpp without OIIO (upstream includes
 * OpenImageIO/filesystem.h, strutil.h and sysutil.h, and zstd.h) */
/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: defines only path_fopen, the one function of upstream
 * util/path.cpp that vendored code calls (util/md5.cpp, MD5Hash::append_file). The rest of
 * upstream's file needs OpenImageIO, zstd and Blender's kernel cache directories, which M3 does
 * not use. path_fopen is copied from upstream: std::fopen, or _wfopen of the UTF-16 path on
 * Windows. */

#include "util/path.h"
#include "util/string.h"

#include <cstdio>

CCL_NAMESPACE_BEGIN

FILE *path_fopen(const string &path, const string &mode)
{
#ifdef _WIN32
  wstring path_wc = string_to_wstring(path);
  wstring mode_wc = string_to_wstring(mode);
  return _wfopen(path_wc.c_str(), mode_wc.c_str());
#else
  return fopen(path.c_str(), mode.c_str());
#endif
}

CCL_NAMESPACE_END
