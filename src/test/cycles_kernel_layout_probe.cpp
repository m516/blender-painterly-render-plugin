/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* The second translation unit of the kernel layout check. It is compiled into its own library,
 * which gets the definition set only through its own link to cycles_kernel. */

#include "cycles_kernel_layout_probe.h"

CCL_NAMESPACE_BEGIN

PainterlyKernelLayout painterly_kernel_layout_probe()
{
  return painterly_kernel_layout_record();
}

CCL_NAMESPACE_END
