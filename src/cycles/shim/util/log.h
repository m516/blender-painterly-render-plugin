/* Shim: replaces Cycles util/log.h without OIIO (upstream includes util/string.h) */
/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

/* Modified by the Painterly project: LOG_ERROR, LOG_WARNING, LOG_INFO and LOG_TRACE stream to
 * std::cerr, each prefixed with its level, instead of through upstream's LogMessage. LogLevel
 * (util/log.h:17-29), LOG_IS_ON (util/log.h:113) and the float3 stream operator
 * (util/log.cpp:137-141) are upstream's; LOG_LEVEL is upstream's variable (util/log.h:76,
 * util/log.cpp:17) as an inline variable. LOG_TRACE writes only when LOG_IS_ON(LOG_LEVEL_TRACE),
 * as upstream's LOG(LOG_LEVEL_TRACE) does (util/log.h:83-108). Upstream's log configuration is
 * not needed until a card vendors code that calls it. */

#pragma once

#define PAINTERLY_SHIM_UTIL_LOG_H 1

#include <iostream>

#include "util/types.h"

#define LOG_ERROR (std::cerr << "Error: ")
#define LOG_WARNING (std::cerr << "Warning: ")
#define LOG_INFO (std::cerr << "Info: ")

CCL_NAMESPACE_BEGIN

/* Log Levels */

enum LogLevel {
  LOG_LEVEL_FATAL = 0,          /* Fatal error, application will abort */
  LOG_LEVEL_DFATAL = 1,         /* Fatal error in debug build only */
  LOG_LEVEL_ERROR = 2,          /* Error */
  LOG_LEVEL_DERROR = 3,         /* Error in debug build only */
  LOG_LEVEL_WARNING = 4,        /* Warning */
  LOG_LEVEL_DWARNING = 5,       /* Warning in debug build only */
  LOG_LEVEL_INFO_IMPORTANT = 6, /* Important info that is printed by default */
  LOG_LEVEL_INFO = 7,           /* Info about devices, scene contents and features used. */
  LOG_LEVEL_DEBUG = 8,          /* Work being performed and timing/memory stats about that work. */
  LOG_LEVEL_TRACE = 9,          /* Verbose debug messages, to trace code being executed. */
  LOG_LEVEL_UNKNOWN = -1,
};

/* The current level, LOG_LEVEL_INFO_IMPORTANT by default (util/log.cpp:17). */
inline LogLevel LOG_LEVEL = LOG_LEVEL_INFO_IMPORTANT;

/* Check if logging is enabled, to avoid doing expensive work to compute
 * the logging message. Note that any work to the right of LOG(level) will
 * not be evaulated if logging for that level is disabled. */
#define LOG_IS_ON(level) ((level) <= LOG_LEVEL)

/* The streamed expressions compile at every level, and run only when the level is on. */
#define LOG_TRACE \
  if (!LOG_IS_ON(LOG_LEVEL_TRACE)) { \
  } \
  else \
    (std::cerr << "Trace: ")

inline std::ostream &operator<<(std::ostream &os, const float3 &value)
{
  os << "(" << value.x << ", " << value.y << ", " << value.z << ")";
  return os;
}

CCL_NAMESPACE_END
