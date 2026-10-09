"""Scale-equivariant metrics: Gaussian high-pass and noise-corrected lag (T1.13, experiment 006)."""

import numpy as np
import pytest
from painterly_analysis import gaussian_highpass, noise_corrected_lag


def test_gaussian_highpass_of_constant_field_is_zero() -> None:
    # A blur of a constant returns the constant (its transfer at f = 0 is 1), so nothing is left.
    # The only error is float64 round-off of an FFT of 2H x 2W values of magnitude 37.
    field = np.full((12, 20), 37.0)
    hp = np.asarray(gaussian_highpass(field, 2.5))
    np.testing.assert_allclose(hp, 0.0, rtol=0.0, atol=1e-12 * 37.0)


def test_gaussian_highpass_ignores_a_constant_offset() -> None:
    # Because the transfer at f = 0 is 1, adding a constant to x leaves the high-pass unchanged.
    rng = np.random.default_rng(3)
    x = rng.normal(size=(10, 16))
    hp = np.asarray(gaussian_highpass(x, 1.7))
    hp_offset = np.asarray(gaussian_highpass(x + 250.0, 1.7))
    # Float64 round-off of an FFT of 2H x 2W values of magnitude at most 250 + max|x|.
    scale = 250.0 + float(np.max(np.abs(x)))
    np.testing.assert_allclose(hp_offset, hp, rtol=0.0, atol=1e-12 * scale)


@pytest.mark.parametrize("axis", [0, 1])
def test_gaussian_highpass_passes_a_sinusoid_with_its_transfer_gain(axis: int) -> None:
    # f = k / (2 W) is a frequency of the 2W-point extended grid, and cos(2 pi f (n + 1/2)) is
    # invariant under the half-sample mirror about -1/2 and W - 1/2. Its extension is therefore one
    # DFT bin, so the high-pass multiplies it by 1 - exp(-2 pi^2 sigma^2 f^2) exactly.
    h, w, k, sigma = 8, 32, 3, 1.5
    length = w if axis == 1 else h  # samples along the sinusoid's axis
    f = k / (2 * length)  # cycles per pixel of the extended grid, which has 2 * length points
    profile = np.cos(2.0 * np.pi * f * (np.arange(length) + 0.5))
    if axis == 1:
        field = np.broadcast_to(profile[None, :], (h, w)).copy()
    else:
        field = np.broadcast_to(profile[:, None], (h, w)).copy()
    gain = 1.0 - np.exp(-2.0 * np.pi**2 * sigma**2 * f**2)
    # The inputs have amplitude 1, so the tolerance is float64 round-off of the FFT.
    np.testing.assert_allclose(
        np.asarray(gaussian_highpass(field, sigma)), gain * field, rtol=1e-12, atol=1e-12
    )


def test_gaussian_highpass_keeps_mirror_symmetry() -> None:
    # A field symmetric about its vertical centre line has a symmetric high-pass, because the
    # extension and the Gaussian kernel are both symmetric about that line.
    rng = np.random.default_rng(4)
    half = rng.normal(size=(10, 7))
    field = np.concatenate([half, half[:, ::-1]], axis=1)
    assert np.array_equal(field, field[:, ::-1])
    hp = np.asarray(gaussian_highpass(field, 2.2))
    # Float64 round-off of an FFT, relative to the largest magnitude of the field.
    np.testing.assert_allclose(
        hp[:, ::-1], hp, rtol=1e-12, atol=1e-12 * float(np.max(np.abs(field)))
    )


@pytest.mark.parametrize("axis", [0, 1])
@pytest.mark.parametrize("lag", [1, 2])
def test_noise_corrected_lag_of_identical_halves_is_the_masked_autocorrelation(
    axis: int, lag: int
) -> None:
    rng = np.random.default_rng(5)
    x = rng.normal(size=(14, 17))
    mask = rng.uniform(size=(14, 17)) < 0.6
    # Direct computation of the definition with identical halves: the lagged covariance over
    # the pixel pairs with both pixels in the mask, each side centred by its own mean over those
    # pairs, divided by the population variance of x over the mask.
    if axis == 0:
        pair = mask[:-lag] & mask[lag:]
        u, v = x[:-lag][pair], x[lag:][pair]
    else:
        pair = mask[:, :-lag] & mask[:, lag:]
        u, v = x[:, :-lag][pair], x[:, lag:][pair]
    lagged_cov = np.mean((u - u.mean()) * (v - v.mean()))
    variance = np.var(x[mask])
    expected = lagged_cov / variance
    # The estimator is an analytic identity, so the tolerance is float64 round-off only.
    got = float(noise_corrected_lag(x, x, mask, axis=axis, lag=lag))
    assert got == pytest.approx(expected, rel=1e-12, abs=0.0)
