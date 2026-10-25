# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The film: the core's radiance sums → the pixels of Blender's Combined pass.

Pure numpy, no ``bpy``, so the mapping is unit-testable without Blender. The render loop of
:mod:`session` calls :func:`display_referred` or :func:`scene_linear`, then
:func:`to_blender_rows`, and writes the result into the render result.

SPEC §8 fixes the two output modes:

- ``display_referred``: ``srgb_to_linear(min(L/255, 1))`` into the Combined pass. Under Blender's
  Standard view transform with dither 0 this reproduces smallpaint's bytes up to rounding.
- ``scene_linear``: ``L/255 · exposure``.

``L`` is the mean radiance of a pixel over the completed passes. The core's
``Session.combined()`` returns the *sum* over those passes (``_painterly.pyi``), so every function
here divides by the pass count.

Row order: the core's buffers have row 0 at the top of the image (SPEC §0, ``_painterly.pyi``),
while Blender's render buffers have row 0 at the bottom, so :func:`to_blender_rows` flips them.
"""

from __future__ import annotations

import numpy as np

# The IEC 61966-2-1 (sRGB) EOTF, i.e. the sRGB → linear-light transfer function:
#
#   linear = x / 12.92                              for x <= 0.04045
#   linear = ((x + 0.055) / 1.055) ** 2.4           for x > 0.04045
#
# The five numbers are definitions of the standard (IEC 61966-2-1:1999, §5.2 and Annex A), not
# tunables: 0.04045 is the junction, 12.92 = 1/0.0773993808 the linear slope, and 0.055 / 1.055 /
# 2.4 the power segment. They are written once, here.
SRGB_JUNCTION = 0.04045
SRGB_LINEAR_SLOPE = 12.92
SRGB_OFFSET = 0.055
SRGB_SCALE = 1.055
SRGB_EXPONENT = 2.4

# SPEC §7: smallpaint's film maps a radiance sum to a byte as ``min((int)sum / s, 255)``, so the
# byte scale of both output modes is 255 (SPEC §8: ``L/255``).
BYTE_MAX = 255.0

# The number of channels of Blender's Combined pass: R, G, B and A.
RGBA_CHANNELS = 4


def srgb_to_linear(x):
    """The IEC 61966-2-1 sRGB EOTF, evaluated in float64.

    Args:
        x: sRGB-encoded values, unitless, in [0, 1] (a scalar or any array shape).

    Returns:
        Linear-light values in [0, 1], as a float64 array of the input's shape.
    """
    values = np.asarray(x, dtype=np.float64)
    return np.where(
        values <= SRGB_JUNCTION,
        values / SRGB_LINEAR_SLOPE,
        ((values + SRGB_OFFSET) / SRGB_SCALE) ** SRGB_EXPONENT,
    )


def _rgba(rgb: np.ndarray) -> np.ndarray:
    """Append the opaque alpha channel and cast to float32.

    The cast is the single rounding of the output: the arithmetic runs in float64 and the
    Combined pass stores float32, which is what ``rect.foreach_set`` writes.

    Args:
        rgb: linear-light (H, W, 3) float64 values.

    Returns:
        A (H, W, 4) float32 array with alpha 1.
    """
    height, width, _ = rgb.shape
    rgba = np.ones((height, width, RGBA_CHANNELS), dtype=np.float32)
    rgba[..., :3] = rgb
    return rgba


def display_referred(sum_rgb, passes: int) -> np.ndarray:
    """The ``display_referred`` output mode of SPEC §8: ``srgb_to_linear(min(L/255, 1))``.

    Args:
        sum_rgb: the (H, W, 3) float64 radiance *sums* of ``Session.combined()``.
        passes: the number of completed passes the sums cover, at least 1.

    Returns:
        A (H, W, 4) float32 array in the core's row order (row 0 is the top row, SPEC §0), alpha
        1. :func:`to_blender_rows` flips it for Blender's bottom-row-first buffers.
    """
    mean = np.asarray(sum_rgb, dtype=np.float64) / passes / BYTE_MAX
    return _rgba(srgb_to_linear(np.minimum(mean, 1.0)))


def scene_linear(sum_rgb, passes: int, exposure: float) -> np.ndarray:
    """The ``scene_linear`` output mode of SPEC §8: ``L/255 · exposure``, no transfer function.

    Args:
        sum_rgb: the (H, W, 3) float64 radiance *sums* of ``Session.combined()``.
        passes: the number of completed passes the sums cover, at least 1.
        exposure: the film exposure scale, unitless (the ``exposure`` integrator socket).

    Returns:
        A (H, W, 4) float32 array in the core's row order (row 0 is the top row, SPEC §0), alpha
        1. :func:`to_blender_rows` flips it for Blender's bottom-row-first buffers.
    """
    mean = np.asarray(sum_rgb, dtype=np.float64) / passes / BYTE_MAX * exposure
    return _rgba(mean)


def to_blender_rows(rgba: np.ndarray) -> np.ndarray:
    """Flip the rows of an image into Blender's row order.

    The core's buffers and :func:`display_referred` / :func:`scene_linear` start at the top row
    (SPEC §0), while Blender's render buffers start at the bottom row, so the last row becomes the
    first.

    Args:
        rgba: an (H, W, 4) float32 image in the top-row-first order of SPEC §0.

    Returns:
        A new C-contiguous (H, W, 4) float32 array in Blender's bottom-row-first order.
    """
    return np.ascontiguousarray(np.asarray(rgba, dtype=np.float32)[::-1])
