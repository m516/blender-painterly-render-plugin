"""Scale-equivariant metrics: Gaussian high-pass and noise-corrected lag (T1.13, experiment 006).

The along-row high-pass ``gaussian_highpass_axis`` of experiment 007 was added here too, because
it is the scale-equivariant metric of the same family.
"""

import numpy as np
import pytest
from painterly_analysis import gaussian_highpass, gaussian_highpass_axis, noise_corrected_lag


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


def test_gaussian_highpass_axis_of_a_constant_field_is_zero() -> None:
    # The transfer of the blur at f = 0 is 1, so a constant field leaves nothing. The only error
    # is the float64 round-off of an FFT of 2H x 2W values of magnitude 37.
    field = np.full((12, 20), 37.0)
    hp = np.asarray(gaussian_highpass_axis(field, 2.5, 1))
    np.testing.assert_allclose(hp, 0.0, rtol=0.0, atol=1e-12 * 37.0)


@pytest.mark.parametrize("axis", [0, 1])
def test_gaussian_highpass_axis_passes_a_sinusoid_with_its_transfer_gain(axis: int) -> None:
    # nu = k / (2 L) is a frequency of the 2L-point extended axis, and cos(2 pi nu (n + 1/2)) is
    # invariant under the half-sample mirror about -1/2 and L - 1/2. Its extension is therefore one
    # DFT bin, so the high-pass multiplies it by 1 - exp(-2 pi^2 sigma^2 nu^2) exactly.
    h, w, k, sigma = 8, 32, 3, 1.5
    length = w if axis == 1 else h  # samples along the sinusoid's axis
    nu = k / (2 * length)  # cycles per pixel of the extended axis, which has 2 * length points
    profile = np.cos(2.0 * np.pi * nu * (np.arange(length) + 0.5))
    if axis == 1:
        field = np.broadcast_to(profile[None, :], (h, w)).copy()
    else:
        field = np.broadcast_to(profile[:, None], (h, w)).copy()
    gain = 1.0 - np.exp(-2.0 * np.pi**2 * sigma**2 * nu**2)
    # The inputs have amplitude 1, so the tolerance is float64 round-off of the FFT.
    np.testing.assert_allclose(
        np.asarray(gaussian_highpass_axis(field, sigma, axis)), gain * field, rtol=1e-12, atol=1e-12
    )


@pytest.mark.parametrize("axis", [0, 1])
def test_gaussian_highpass_axis_of_a_field_constant_along_the_axis_is_zero(axis: int) -> None:
    # The blur acts along the axis only, so a field that does not vary along it is unchanged by the
    # blur and its high-pass is zero, whatever it does across the axis.
    rng = np.random.default_rng(6)
    h, w = 9, 13
    across = rng.normal(size=(h, 1) if axis == 1 else (1, w))
    field = np.broadcast_to(across, (h, w)).copy()
    hp = np.asarray(gaussian_highpass_axis(field, 1.9, axis))
    # The only error is the float64 round-off of the FFT, relative to the largest magnitude.
    np.testing.assert_allclose(hp, 0.0, rtol=0.0, atol=1e-12 * float(np.max(np.abs(field))))


@pytest.mark.parametrize("axis", [0, 1])
def test_gaussian_highpass_axis_equals_the_isotropic_high_pass_along_that_axis(axis: int) -> None:
    # A field that varies only along the blurred axis has no frequency across it, so the 2-D
    # transfer of gaussian_highpass is the 1-D transfer of the axis filter.
    rng = np.random.default_rng(7)
    h, w = 10, 16
    profile = rng.normal(size=w if axis == 1 else h)
    if axis == 1:
        field = np.broadcast_to(profile[None, :], (h, w)).copy()
    else:
        field = np.broadcast_to(profile[:, None], (h, w)).copy()
    axis_hp = np.asarray(gaussian_highpass_axis(field, 2.3, axis))
    iso_hp = np.asarray(gaussian_highpass(field, 2.3))
    # The two computations are the same identity in different arithmetic, so the difference is the
    # float64 round-off of the two FFTs.
    np.testing.assert_allclose(
        axis_hp, iso_hp, rtol=1e-12, atol=1e-12 * float(np.max(np.abs(field)))
    )


def test_gaussian_highpass_axis_of_the_transposed_field_is_the_transposed_high_pass() -> None:
    # The filter acts on one axis only, so swapping the axes swaps the roles of the axes.
    rng = np.random.default_rng(8)
    field = rng.normal(size=(7, 11))
    along_rows = np.asarray(gaussian_highpass_axis(field, 1.4, 1))
    along_columns = np.asarray(gaussian_highpass_axis(field.T, 1.4, 0).T)
    # Identity: the axis=0 branch is gaussian_highpass_axis(x.T, sigma, 1).T, so both sides
    # compute x - G_sigma * x along the same 11-pixel rows of the same values, and each differs
    # from that exact result only by the float64 round-off of its own FFT (unit round-off
    # u = 2**-53 = 1.11e-16). One row is filtered by an rfft and an irfft of its 22-point
    # half-sample extension (m = 2 * 11). The standard radix-2 bound puts a transform within
    # gamma_k * ||x||_1 of the exact sum, where gamma_k = k u / (1 - k u) bounds k chained
    # roundings and k = 3 log2(m) counts one complex twiddle multiply and two additions per
    # butterfly stage; a real-input transform of m points costs no more than the complex one of
    # m points, so this bounds it. With k = 3 log2(22) = 13.38 and ||x||_1 <= m * max|field|,
    # gamma_13.38 * 22 = 3.27e-14 * max|field|. A forward and inverse pair, the elementwise
    # transfer multiply and the subtraction add 2u, giving 6.56e-14 * max|field| per side and
    # 1.31e-13 * max|field| for the two sides. The atol term 1e-12 * max|field| alone is 7.6x
    # that bound, so the atol term already covers the round-off; the rtol term adds the
    # non-negative 1e-12 * |along_rows|, so it can only widen what is allowed.
    np.testing.assert_allclose(
        along_columns, along_rows, rtol=1e-12, atol=1e-12 * float(np.max(np.abs(field)))
    )


def test_gaussian_highpass_axis_filters_each_row_from_that_row_alone() -> None:
    # The axis-1 filter acts on each row separately, so changing one row leaves every other row
    # bitwise unchanged.
    rng = np.random.default_rng(9)
    field = rng.normal(size=(6, 12))
    changed = field.copy()
    changed[2] += 100.0
    hp = np.asarray(gaussian_highpass_axis(field, 1.1, 1))
    hp_changed = np.asarray(gaussian_highpass_axis(changed, 1.1, 1))
    for row in range(field.shape[0]):
        if row == 2:
            continue
        assert np.array_equal(hp[row], hp_changed[row])


def test_gaussian_highpass_axis_rejects_a_bad_field_sigma_or_axis() -> None:
    with pytest.raises(ValueError, match="2-D"):
        gaussian_highpass_axis(np.zeros(4), 1.0, 1)
    with pytest.raises(ValueError, match="sigma"):
        gaussian_highpass_axis(np.zeros((4, 5)), -1.0, 1)
    with pytest.raises(ValueError, match="axis"):
        gaussian_highpass_axis(np.zeros((4, 5)), 1.0, 2)
