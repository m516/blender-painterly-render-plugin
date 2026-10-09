"""Look metrics on synthetic images (T1.2)."""

import numpy as np
import pytest
from painterly_analysis import (
    block_rmse,
    erode,
    highpass,
    pearson,
    radial_spectral_slope,
    realization_free_key_family,
    structure_std,
)


def test_highpass_of_constant_image_is_exactly_zero() -> None:
    # 37 is an integer, so every box sum and the division by 81 are exact in float64.
    img = np.full((20, 30), 37.0)
    assert np.array_equal(np.asarray(highpass(img, 9)), np.zeros((20, 30)))


def test_erode_known_7x7_masks() -> None:
    full = np.ones((7, 7), dtype=bool)
    interior = np.zeros((7, 7), dtype=bool)
    interior[1:6, 1:6] = True
    # Radius 1 keeps the 5x5 interior, since a 3x3 square must lie inside the image.
    assert np.array_equal(np.asarray(erode(full, 1)), interior)
    # One hole at the centre also removes its 3x3 neighbourhood: 5x5 minus that 3x3 leaves 16.
    holed = full.copy()
    holed[3, 3] = False
    holed_expected = interior.copy()
    holed_expected[2:5, 2:5] = False
    assert np.array_equal(np.asarray(erode(holed, 1)), holed_expected)
    # Radius 3 keeps only the centre, the one pixel whose 7x7 square lies in the image.
    centre = np.zeros((7, 7), dtype=bool)
    centre[3, 3] = True
    assert np.array_equal(np.asarray(erode(full, 3)), centre)


def test_pearson_of_field_with_itself_is_one() -> None:
    rng = np.random.default_rng(0)
    a = rng.normal(size=(16, 16))
    mask = rng.uniform(size=(16, 16)) < 0.5
    # The identity is analytic. The tolerance covers float64 round-off only.
    np.testing.assert_allclose(float(pearson(a, a, mask)), 1.0, rtol=1e-12, atol=0.0)


def test_structure_std_of_field_with_itself_is_masked_std() -> None:
    rng = np.random.default_rng(1)
    a = rng.normal(size=(16, 16))
    mask = rng.uniform(size=(16, 16)) < 0.5
    # structure_std uses the population covariance (ddof 0), which is np.std's default.
    # The tolerance covers float64 round-off only.
    expected = np.std(a[mask])
    np.testing.assert_allclose(float(structure_std(a, a, mask)), expected, rtol=1e-12, atol=0.0)


def test_block_rmse_of_image_with_itself_is_zero() -> None:
    x = np.random.default_rng(2).uniform(0.0, 255.0, size=(60, 75, 3))
    assert float(block_rmse(x, x)) == 0.0


def _power_law_field(size: int, seed: int) -> np.ndarray:
    """Real field with |F|^2 = r^-2 exactly (r = integer frequency radius) and random phases."""
    freq = np.fft.fftfreq(size) * size
    ky, kx = np.meshgrid(freq, freq, indexing="ij")
    rho = np.hypot(ky, kx)
    amp = np.zeros_like(rho)
    amp[rho > 0] = 1.0 / rho[rho > 0]
    phase = np.random.default_rng(seed).uniform(0.0, 2.0 * np.pi, size=rho.shape)
    # Odd phase, phi(-k) = -phi(k), makes the spectrum Hermitian, so the inverse transform is real.
    neg = (-np.arange(size)) % size
    phase = 0.5 * (phase - phase[np.ix_(neg, neg)])
    return np.fft.ifft2(amp * np.exp(1j * phase)).real


def _radial_profile(x: np.ndarray, f_min: int = 2) -> tuple[np.ndarray, np.ndarray]:
    """(log_r, log_p) of the windowed radial power profile, as radial_spectral_slope defines it.

    The profile uses a Hann window, |FFT|^2 and integer radii rint(r) averaged over
    [f_min, min(H, W) // 4].
    """
    h, w = x.shape
    f_max = min(h, w) // 4
    window = np.outer(np.hanning(h), np.hanning(w))
    power = np.abs(np.fft.fft2(x * window)) ** 2
    ky = np.rint(np.fft.fftfreq(h) * h)
    kx = np.rint(np.fft.fftfreq(w) * w)
    bins = np.rint(np.hypot(ky[:, None], kx[None, :])).astype(np.int64).ravel()
    length = (h + w) // 2 + 2
    sums = np.bincount(bins, weights=power.ravel(), minlength=length)
    counts = np.bincount(bins, minlength=length)
    radii = np.arange(f_min, f_max + 1)
    log_r = np.log(radii)
    log_p = np.log(sums[radii] / counts[radii])
    return log_r, log_p


def _radial_fit_residual_rms(x: np.ndarray, f_min: int = 2) -> float:
    """RMS residual of the least-squares log-log fit to the radial power profile.

    The residuals are the scatter that the power law does not explain.
    """
    log_r, log_p = _radial_profile(x, f_min)
    slope, intercept = np.polyfit(log_r, log_p, 1)
    residual = log_p - (intercept + slope * log_r)
    return float(np.sqrt(np.mean(residual**2)))


def test_radial_spectral_slope_equals_polyfit_of_radial_profile() -> None:
    x = _power_law_field(256, seed=0)
    log_r, log_p = _radial_profile(x)
    # The same least-squares formula, computed two ways. The tolerance covers float64 round-off
    # only.
    expected = np.polyfit(log_r, log_p, 1)[0]
    assert float(radial_spectral_slope(x)) == pytest.approx(expected, rel=1e-12)


def test_radial_spectral_slope_of_power_law_is_minus_two() -> None:
    x = _power_law_field(256, seed=0)
    slope = float(radial_spectral_slope(x))
    # Sanity bound, not a tolerance on the implementation: a slope within the fit scatter of -2 is
    # what the power law predicts. The scatter is the RMS residual of the least-squares log-log
    # fit to this field's own radial profile, left by the Hann window and the finite number of
    # bins per radius. It is computed from the data, so it is not a hand-picked number.
    tolerance = _radial_fit_residual_rms(x)
    assert abs(slope - (-2.0)) <= tolerance


def test_realization_free_key_family_drops_reference_realization_keys() -> None:
    keys = [
        "r2.mean.R",
        "r2.mean.G",
        "r2.mean.B",
        "r2.structure_std",
        "r2.lag1.x",
        "r2.lag1.y",
        "r2.pattern_corr",
        "r2.spectral_slope",
        "all.pattern_corr",
        "all.block_rmse",
        "all.clip_fraction",
        "all.spectral_slope",
    ]
    # pattern_corr and block_rmse compare with the reference's realization. The raw lag-1 keys
    # are not in the family. The rest keep their order.
    assert realization_free_key_family(keys) == [
        "r2.mean.R",
        "r2.mean.G",
        "r2.mean.B",
        "r2.structure_std",
        "r2.spectral_slope",
        "all.clip_fraction",
        "all.spectral_slope",
    ]
