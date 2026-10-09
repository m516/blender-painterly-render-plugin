"""Look metrics for the painterly render (pure JAX).

Units: images are SPEC §7 display bytes (0..255) held as float64 unless a function says
otherwise. Masks are boolean (H, W) arrays selecting pixels. Coordinates are (row, col) = (y, x).
Every function casts its inputs to float64 first, so uint8 display images can be passed directly.
"""

import re
from collections.abc import Iterable

import jax.numpy as jnp
import numpy as np
from jax import Array

from .io import smallpaint_display

LUMA_REC709 = (0.2126, 0.7152, 0.0722)  # ITU-R BT.709 luma coefficients (definition)
# the plan's acceptance metrics: 9×9-box high-pass luminance
HIGHPASS_SIZE = 9

# SPEC §9 object ids of type diffuse, excluding the light (id 9). The scene-list order is the
# object id (painterly.cpp:252-262).
DIFFUSE_REGION_IDS = (2, 3, 4, 5, 6, 7, 8)
# Metric keys of one region start with "r{id}." (see ``measure``).
_REGION_KEY = re.compile(r"r(\d+)\.")


def _f64(x) -> Array:
    return jnp.asarray(x, dtype=jnp.float64)


def _bool(mask) -> Array:
    return jnp.asarray(mask, dtype=bool)


def _count(mask: Array) -> int:
    n = int(jnp.sum(mask))
    if n == 0:
        raise ValueError("mask selects no pixels")
    return n


def _masked_mean(x: Array, mask: Array) -> Array:
    return jnp.sum(jnp.where(mask, x, 0.0)) / _count(mask)


def luminance(rgb) -> Array:
    """Rec.709 luma of (..., 3) display bytes. Returns (...) float64 display bytes."""
    return _f64(rgb) @ _f64(LUMA_REC709)


def box_blur(x, size: int) -> Array:
    """Centred mean over a ``size`` x ``size`` window on the first two axes.

    Edges are replicated. Units are those of ``x``. ``size`` must be odd and positive. The box is
    computed as two separable 1-D sums, so integer-valued input gives exact results.
    """
    if size < 1 or size % 2 == 0:
        raise ValueError("size must be a positive odd integer")
    x = _f64(x)
    r = size // 2
    h, w = x.shape[0], x.shape[1]
    pad = ((r, r), (r, r)) + ((0, 0),) * (x.ndim - 2)
    xp = jnp.pad(x, pad, mode="edge")
    vertical = sum(xp[i : i + h] for i in range(size))
    total = sum(vertical[:, j : j + w] for j in range(size))
    return total / (size * size)


def highpass(x, size: int = HIGHPASS_SIZE) -> Array:
    """``x - box_blur(x, size)``: the texture left after removing the local mean. Units of ``x``."""
    x = _f64(x)
    return x - box_blur(x, size)


def gaussian_highpass(x, sigma: float) -> Array:
    """``x - G_sigma * x``: the texture left after removing a Gaussian blur. Units of ``x``.

    ``x`` is a 2-D field (H, W). ``G_sigma`` is a Gaussian of standard deviation ``sigma`` pixels,
    ``sigma >= 0``. The blur acts on the half-sample-symmetric extension of ``x`` to 2H x 2W (``x``
    followed by its mirror image on each axis), so no wrap-around enters at the border. The result
    is cropped back to H x W. In the frequency domain the transfer of ``G_sigma`` at frequency
    ``f`` (cycles per pixel of the extended grid) is ``exp(-2 pi^2 sigma^2 (f_x^2 + f_y^2))``. This
    is the Fourier transform of a Gaussian of standard deviation ``sigma`` (a definition, not a
    tuned value). Its value at ``f = 0`` is 1, so a constant field has no high-pass.
    """
    x = _f64(x)
    if x.ndim != 2:
        raise ValueError("x must be a 2-D field")
    if sigma < 0:
        raise ValueError("sigma must be >= 0")
    h, w = x.shape
    ext = jnp.concatenate([x, x[:, ::-1]], axis=1)
    ext = jnp.concatenate([ext, ext[::-1, :]], axis=0)
    fy = jnp.fft.fftfreq(2 * h)
    fx = jnp.fft.rfftfreq(2 * w)
    transfer = jnp.exp(-2.0 * jnp.pi**2 * sigma**2 * (fy[:, None] ** 2 + fx[None, :] ** 2))
    low = jnp.fft.irfft2(jnp.fft.rfft2(ext) * transfer, s=(2 * h, 2 * w))[:h, :w]
    return x - low


def erode(mask, radius: int) -> Array:
    """Morphological erosion with a (2r+1) x (2r+1) square.

    A pixel survives iff its whole square lies inside the image and inside the mask. Pixels
    within ``radius`` of the border therefore never survive.
    """
    if radius < 0:
        raise ValueError("radius must be >= 0")
    m = _bool(mask)
    h, w = m.shape
    padded = jnp.pad(
        m, ((radius, radius), (radius, radius)), mode="constant", constant_values=False
    )
    vertical = jnp.ones((h, w + 2 * radius), dtype=bool)
    for i in range(2 * radius + 1):
        vertical = vertical & padded[i : i + h]
    out = jnp.ones((h, w), dtype=bool)
    for j in range(2 * radius + 1):
        out = out & vertical[:, j : j + w]
    return out


def region_masks(object_id, radius: int) -> dict[int, Array]:
    """Eroded mask for each object id in ``object_id``, keeping only non-empty masks.

    Negative ids (primary-ray misses, T1.1) are not regions and are skipped. The default erosion
    radius of ``measure`` is ``highpass_size // 2``.
    """
    ids = np.unique(np.asarray(object_id))
    obj = jnp.asarray(object_id)
    masks: dict[int, Array] = {}
    for region in ids:
        if region < 0:
            continue
        eroded = erode(obj == region, radius)
        if bool(jnp.any(eroded)):
            masks[int(region)] = eroded
    return masks


def region_mean_rgb(img, mask) -> Array:
    """Mean (R, G, B) of an (H, W, 3) image over the mask. Units of ``img``."""
    x = _f64(img)
    m = _bool(mask)
    return jnp.sum(jnp.where(m[..., None], x, 0.0), axis=(0, 1)) / _count(m)


def _masked_cov(x: Array, y: Array, mask: Array) -> Array:
    """Population covariance of x and y over the pixels where mask is true, each centred by its own
    masked mean."""
    n = _count(mask)
    mean_x = jnp.sum(jnp.where(mask, x, 0.0)) / n
    mean_y = jnp.sum(jnp.where(mask, y, 0.0)) / n
    dx = jnp.where(mask, x - mean_x, 0.0)
    dy = jnp.where(mask, y - mean_y, 0.0)
    return jnp.sum(dx * dy) / n


def noise_corrected_lag(hp_a, hp_b, mask, axis: int, lag: int = 1) -> Array:
    """Lag-``lag`` autocorrelation of the structure shared by two independent half renders.

    Dimensionless. ``hp_a`` and ``hp_b`` are high-passed fields of two half renders that share the
    structure and have independent noise. ``axis=0`` pairs rows (y) and ``axis=1`` pairs columns
    (x): the pairs are ``(p, p + lag)`` along ``axis``, and only pairs whose two pixels both lie in
    ``mask`` count. The covariance of ``hp_a[p]`` and ``hp_b[p + lag]`` estimates the structure's
    lagged covariance. The covariance of ``hp_a`` and ``hp_b`` over ``mask`` estimates its variance.
    Their ratio is the structure's autocorrelation at that lag, free of the noise-to-structure
    ratio. Each covariance is in population form, centred by its own masked mean. ``lag=1`` is the
    lag-1 estimator of experiment 004.
    """
    if lag < 1:
        raise ValueError("lag must be >= 1")
    a = _f64(hp_a)
    b = _f64(hp_b)
    m = _bool(mask)
    if axis == 0:
        x, y, pair = a[:-lag], b[lag:], m[:-lag] & m[lag:]
    elif axis == 1:
        x, y, pair = a[:, :-lag], b[:, lag:], m[:, :-lag] & m[:, lag:]
    else:
        raise ValueError("axis must be 0 or 1")
    return _masked_cov(x, y, pair) / _masked_cov(a, b, m)


def pearson(a, b, mask) -> Array:
    """Pearson correlation of ``a`` and ``b`` over the pixels where ``mask`` is true.

    Dimensionless. Returns NaN when either input is constant over the mask.
    """
    a = _f64(a)
    b = _f64(b)
    m = _bool(mask)
    da = jnp.where(m, a - _masked_mean(a, m), 0.0)
    db = jnp.where(m, b - _masked_mean(b, m), 0.0)
    return jnp.sum(da * db) / jnp.sqrt(jnp.sum(da * da) * jnp.sum(db * db))


def structure_std(hp_a, hp_b, mask) -> Array:
    """``sqrt(max(cov, 0))`` over the mask, with ``cov = mean((a - mean a)(b - mean b))``.

    The covariance is the population form (ddof 0). The inputs are high-passed images, so the
    result is in display bytes. For ``hp_a == hp_b`` it equals the masked population standard
    deviation.
    """
    a = _f64(hp_a)
    b = _f64(hp_b)
    m = _bool(mask)
    da = jnp.where(m, a - _masked_mean(a, m), 0.0)
    db = jnp.where(m, b - _masked_mean(b, m), 0.0)
    return jnp.sqrt(jnp.maximum(_masked_mean(da * db, m), 0.0))


def lag1_autocorrelation(x, mask, axis: int) -> Array:
    """Lag-1 autocorrelation of a 2-D field along ``axis``. Dimensionless.

    ``axis=0`` pairs rows (the y direction) and ``axis=1`` pairs columns (the x direction). Each
    pair is ``x[p]`` with its neighbour one step further along ``axis``. Only pairs whose two
    pixels both lie in ``mask`` count.
    """
    x = _f64(x)
    m = _bool(mask)
    if axis == 0:
        a, b, pair = x[:-1], x[1:], m[:-1] & m[1:]
    elif axis == 1:
        a, b, pair = x[:, :-1], x[:, 1:], m[:, :-1] & m[:, 1:]
    else:
        raise ValueError("axis must be 0 or 1")
    return pearson(a, b, pair)


def block_rmse(img, ref, block: int = 25) -> Array:
    """RMSE between block-averaged images. Units: display bytes.

    The images are cropped to whole ``block`` x ``block`` blocks, and each channel is averaged
    over every block. The result is the RMSE over all blocks and channels. ``block`` is a knob
    whose default of 25 is the value in the plan's acceptance metrics.
    """
    if block < 1:
        raise ValueError("block must be >= 1")
    a = _f64(img)
    b = _f64(ref)
    hb, wb = a.shape[0] // block, a.shape[1] // block
    if hb == 0 or wb == 0:
        raise ValueError("image is smaller than one block")

    def block_means(x: Array) -> Array:
        x = x[: hb * block, : wb * block]
        x = x.reshape(hb, block, wb, block, *x.shape[2:])
        return x.mean(axis=(1, 3))

    diff = block_means(a) - block_means(b)
    return jnp.sqrt(jnp.mean(diff * diff))


def clip_fraction(img8) -> Array:
    """Fraction of pixels in which at least one channel equals 255. Dimensionless, in [0, 1]."""
    x = _f64(img8)
    return jnp.mean(jnp.any(x == 255.0, axis=-1))


def radial_spectral_slope(x, mask=None, f_min: int = 2, f_max: int | None = None) -> Array:
    """Log-log slope of the radially averaged power spectrum of a 2-D field. Dimensionless.

    Steps:
    1. If ``mask`` is given, multiply ``x`` by it.
    2. Apply a separable 2-D Hann window (``jnp.hanning`` on each axis) and take ``|FFT|**2``.
    3. Assign each frequency bin to the integer radius ``rint(sqrt(fy**2 + fx**2))``. Average the
       power over each integer radius in ``[f_min, f_max]``, where ``f_max`` defaults to
       ``min(H, W) // 4``.
    4. Return the least-squares slope of log power against log radius.

    ``f_min`` is a knob. Its default of 2 excludes the DC term and the first frequency.
    """
    a = _f64(x)
    h, w = a.shape[0], a.shape[1]
    if f_max is None:
        f_max = min(h, w) // 4
    if not 1 <= f_min <= f_max:
        raise ValueError("need 1 <= f_min <= f_max")
    if mask is not None:
        a = a * _f64(mask)
    window = jnp.outer(jnp.hanning(h), jnp.hanning(w))
    power = jnp.abs(jnp.fft.fft2(a * window)) ** 2
    ky = jnp.rint(jnp.fft.fftfreq(h) * h)
    kx = jnp.rint(jnp.fft.fftfreq(w) * w)
    bins = jnp.rint(jnp.sqrt(ky[:, None] ** 2 + kx[None, :] ** 2)).astype(jnp.int64).ravel()
    # The largest rounded radius is at most (h + w) / 2, so this length holds every bin.
    length = (h + w) // 2 + 2
    sums = jnp.bincount(bins, weights=power.ravel(), length=length)
    counts = jnp.bincount(bins, length=length)
    radii = jnp.arange(f_min, f_max + 1)
    log_r = jnp.log(radii.astype(jnp.float64))
    log_p = jnp.log(sums[radii] / counts[radii])
    dr = log_r - jnp.mean(log_r)
    dp = log_p - jnp.mean(log_p)
    return jnp.sum(dr * dp) / jnp.sum(dr * dr)


def measure(
    sum_a,
    sum_b,
    passes: int,
    ref8,
    object_id,
    *,
    highpass_size: int = HIGHPASS_SIZE,
    erosion_radius: int | None = None,
    block: int = 25,
) -> dict[str, float]:
    """All look metrics for two independent half renders and a reference image.

    ``sum_a`` and ``sum_b`` are two independent oracle ``sum`` arrays rendered with the same
    ``passes``. Define ``a8 = smallpaint_display(sum_a, passes)``,
    ``b8 = smallpaint_display(sum_b, passes)`` and
    ``ab8 = smallpaint_display(sum_a + sum_b, 2 * passes)``. ``ref8`` is the reference display
    image, and ``object_id`` is the SPEC §9 id map of the same render.

    Per region id ``r``, over the eroded masks:
    - ``r{r}.mean.{R,G,B}``: region mean of ``ab8``;
    - ``r{r}.structure_std``: ``structure_std`` of the high-passed luminance of ``a8`` and ``b8``;
    - ``r{r}.pattern_corr``: ``pearson`` of the high-passed luminance of ``ab8`` and ``ref8``;
    - ``r{r}.lag1.x`` and ``r{r}.lag1.y``: lag-1 autocorrelation of the high-passed luminance of
      ``ab8`` along columns (x) and along rows (y).

    Global:
    - ``all.pattern_corr``: ``pearson`` over the union of the eroded diffuse masks (ids in
      ``DIFFUSE_REGION_IDS``);
    - ``all.block_rmse``: ``block_rmse(ab8, ref8, block)``;
    - ``all.clip_fraction``: ``clip_fraction(ab8)``;
    - ``all.spectral_slope``: ``radial_spectral_slope`` of the high-passed luminance of ``ab8``,
      masked to the same union of eroded diffuse masks as ``all.pattern_corr``. The slope is
      masked on purpose (Opus decision): unmasked, geometry edges dominate the slope.

    ``erosion_radius=None`` means ``highpass_size // 2``. This value is derived, not tuned. It is
    the half-width of the box filter, so no high-pass window of a kept pixel reaches a
    neighbouring region, and geometry edges cannot leak into the texture metrics. Larger values
    are allowed as a knob. ``highpass_size`` and ``block`` are knobs.
    """
    if erosion_radius is None:
        erosion_radius = highpass_size // 2
    a8 = smallpaint_display(sum_a, passes)
    b8 = smallpaint_display(sum_b, passes)
    ab8 = smallpaint_display(np.asarray(sum_a) + np.asarray(sum_b), 2 * passes)

    hp_a = highpass(luminance(a8), highpass_size)
    hp_b = highpass(luminance(b8), highpass_size)
    hp_ab = highpass(luminance(ab8), highpass_size)
    hp_ref = highpass(luminance(ref8), highpass_size)

    masks = region_masks(object_id, erosion_radius)
    out: dict[str, float] = {}
    for region, mask in masks.items():
        prefix = f"r{region}"
        mean = region_mean_rgb(ab8, mask)
        for channel, name in enumerate("RGB"):
            out[f"{prefix}.mean.{name}"] = float(mean[channel])
        out[f"{prefix}.structure_std"] = float(structure_std(hp_a, hp_b, mask))
        out[f"{prefix}.pattern_corr"] = float(pearson(hp_ab, hp_ref, mask))
        out[f"{prefix}.lag1.x"] = float(lag1_autocorrelation(hp_ab, mask, axis=1))
        out[f"{prefix}.lag1.y"] = float(lag1_autocorrelation(hp_ab, mask, axis=0))

    diffuse = [mask for region, mask in masks.items() if region in DIFFUSE_REGION_IDS]
    if not diffuse:
        raise ValueError("no diffuse region survives erosion")
    union = jnp.any(jnp.stack(diffuse), axis=0)
    out["all.pattern_corr"] = float(pearson(hp_ab, hp_ref, union))
    out["all.block_rmse"] = float(block_rmse(ab8, ref8, block))
    out["all.clip_fraction"] = float(clip_fraction(ab8))
    out["all.spectral_slope"] = float(radial_spectral_slope(hp_ab, union))
    return out


def diffuse_key_family(keys: Iterable[str]) -> list[str]:
    """Keys of the diffuse family: every ``r{id}.*`` key with id in ``DIFFUSE_REGION_IDS``, plus
    every ``all.*`` key. Order is that of ``keys``.

    This is the standard family for ``compare_ensembles``. The light (id 9) and any other
    non-diffuse region are left out. For the GUI scene the family has 46 keys: 6 measured diffuse
    regions with 7 keys each, plus 4 ``all.*`` keys.
    """
    family = []
    for key in keys:
        if key.startswith("all."):
            family.append(key)
            continue
        match = _REGION_KEY.match(key)
        if match is not None and int(match.group(1)) in DIFFUSE_REGION_IDS:
            family.append(key)
    return family


# Suffixes of the realization-free keys of ``realization_free_key_family``.
_REALIZATION_FREE_SUFFIXES = (".mean.R", ".mean.G", ".mean.B", ".structure_std", ".spectral_slope")
_REALIZATION_FREE_GLOBAL = "all.clip_fraction"


def realization_free_key_family(keys: Iterable[str]) -> list[str]:
    """Keys of the realization-free family, in the order of ``keys``.

    It keeps every key ending in ``.mean.R``, ``.mean.G``, ``.mean.B``, ``.structure_std`` or
    ``.spectral_slope``, and ``all.clip_fraction``. It drops ``pattern_corr`` and ``block_rmse``,
    and every other key, including the raw lag-1 keys.

    ``pattern_corr`` and ``block_rmse`` measure agreement with the reference's specific
    *realization*: the particular sample sequence of the oracle's K stream. A scene that cannot
    reproduce oracle K consumption exactly (Blender meshes, ghost-lights-only) is judged on this
    realization-free family instead. Regions are not restricted here. Apply ``diffuse_key_family``
    first to restrict the family to the diffuse regions.
    """
    family = []
    for key in keys:
        if key == _REALIZATION_FREE_GLOBAL or key.endswith(_REALIZATION_FREE_SUFFIXES):
            family.append(key)
    return family
