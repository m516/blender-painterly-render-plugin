/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "cycles_kernel_layout_probe.h"

#include <iterator>

#include <doctest/doctest.h>

CCL_NAMESPACE_BEGIN

TEST_CASE("cycles kernel layout: two translation units agree")
{
  const PainterlyKernelLayout here = painterly_kernel_layout_record();
  const PainterlyKernelLayout probe = painterly_kernel_layout_probe();

  CHECK(here.max_closure == probe.max_closure);
  CHECK(here.features == probe.features);
  CHECK(here.shader_closure_size == probe.shader_closure_size);
  CHECK(here.shader_closure_align == probe.shader_closure_align);
  CHECK(here.shader_data_size == probe.shader_data_size);
  CHECK(here.shader_data_align == probe.shader_data_align);
  for (size_t i = 0; i < std::size(here.shader_data_offsets); i++) {
    CAPTURE(i);
    CHECK(here.shader_data_offsets[i] == probe.shader_data_offsets[i]);
  }
  CHECK(here.kernel_data_size == probe.kernel_data_size);
  CHECK(here.kernel_data_align == probe.kernel_data_align);
  for (size_t i = 0; i < std::size(here.kernel_data_offsets); i++) {
    CAPTURE(i);
    CHECK(here.kernel_data_offsets[i] == probe.kernel_data_offsets[i]);
  }
  for (size_t i = 0; i < std::size(here.kernel_struct_sizes); i++) {
    CAPTURE(i);
    CHECK(here.kernel_struct_sizes[i] == probe.kernel_struct_sizes[i]);
  }
  CHECK(here.kernel_globals_size == probe.kernel_globals_size);

  CHECK(here == probe);
}

TEST_CASE("cycles kernel layout: global definition set")
{
  const PainterlyKernelLayout here = painterly_kernel_layout_record();

  /* Bits 0-8 are the guards that kernel/features.h:125-147 defines on every CPU build without
   * __KERNEL_FEATURES__. Bits 9-12 must be clear (T6.1 "Definition set"). */
  CHECK(here.features == (size_t(1) << 9) - 1);

  /* closure[MAX_CLOSURE] is ShaderData's last member (kernel/types.h:1094-1095). Both structs are
   * ccl_align(16), so there is no tail padding, and the compiled array holds exactly MAX_CLOSURE
   * slots. */
  CHECK(here.shader_data_offsets[std::size(here.shader_data_offsets) - 1] +
            here.max_closure * here.shader_closure_size ==
        here.shader_data_size);
}

CCL_NAMESPACE_END
