/* Shim: replaces Cycles util/log.h without OIIO (upstream includes util/string.h) */
/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* Minimal logging for vendored Cycles code. LOG_ERROR, LOG_WARNING and LOG_INFO stream to
 * std::cerr, each prefixed with its level. Upstream's LogMessage, level filtering and string-based
 * log configuration are not needed until a card vendors code that calls them. */

#pragma once

#include <iostream>

#define LOG_ERROR (std::cerr << "Error: ")
#define LOG_WARNING (std::cerr << "Warning: ")
#define LOG_INFO (std::cerr << "Info: ")
