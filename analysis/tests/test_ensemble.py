"""Permutation, sign-flip, Holm and Student-t statistics (T1.2).

The expected values are exact. The only tolerance is the bisection's xtol.
"""

import math

import pytest
from painterly_analysis import (
    compare_ensembles,
    diffuse_key_family,
    holm,
    min_attainable_pvalue,
    permutation_pvalue,
    sign_flip_pvalue,
    student_t_ppf,
)
from painterly_analysis.ensemble import PERMUTATION_RESAMPLES, effect_summary

NON_FINITE_MESSAGE = "samples must be finite (got NaN or inf)"


def test_identical_samples_give_p_one() -> None:
    x = [1.0, 2.0, 3.0, 5.0]
    # Every split has |mean(x') - mean(y')| >= 0 = |observed|, so every split counts.
    assert permutation_pvalue(x, x, "two-sided") == 1.0


def test_fully_separated_groups_give_two_over_choose_16_8() -> None:
    # Only the split {9..16} vs {1..8} and its mirror reach |mean difference| = 8.
    # The next split reaches 7.75.
    p = permutation_pvalue(list(range(9, 17)), list(range(1, 9)), "two-sided")
    assert p == 2 / math.comb(16, 8)


def test_holm_rejects_exactly_a_and_b() -> None:
    decisions = holm({"a": 0.005, "b": 0.01, "c": 0.03, "d": 0.04}, alpha=0.05)
    # Thresholds 0.05/4, 0.05/3, 0.05/2, 0.05/1. a and b pass. c (0.03 > 0.025) stops the
    # procedure.
    assert {key for key, rejected in decisions.items() if rejected} == {"a", "b"}


def test_student_t_ppf_matches_reference_within_xtol() -> None:
    # Bisection stops when the bracket is narrower than xtol, the method's convergence parameter.
    xtol = 1e-12
    assert abs(student_t_ppf(0.975, 7, xtol=xtol) - 2.3646242515927849) <= xtol


def test_sign_flip_one_sided_all_positive_gives_one_over_256() -> None:
    # All-plus is the only pattern at the maximal mean. Flipping any value lowers the mean by at
    # least 0.125.
    x = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    assert sign_flip_pvalue(x, "greater") == 1 / 256


def test_permutation_rejects_nan_in_x() -> None:
    with pytest.raises(ValueError) as info:
        permutation_pvalue([1.0, math.nan, 3.0], [4.0, 5.0], "two-sided")
    assert str(info.value) == NON_FINITE_MESSAGE


def test_permutation_rejects_nan_in_y() -> None:
    with pytest.raises(ValueError) as info:
        permutation_pvalue([1.0, 2.0, 3.0], [4.0, math.nan], "two-sided")
    assert str(info.value) == NON_FINITE_MESSAGE


def test_sign_flip_rejects_nan() -> None:
    with pytest.raises(ValueError) as info:
        sign_flip_pvalue([0.5, math.nan, -1.0], "two-sided")
    assert str(info.value) == NON_FINITE_MESSAGE


def test_compare_ensembles_names_the_key_of_a_nan_sample() -> None:
    a = [{"speed": 1.0, "bad": 2.0}, {"speed": 2.0, "bad": math.nan}]
    b = [{"speed": 3.0, "bad": 1.0}, {"speed": 4.0, "bad": 2.0}]
    with pytest.raises(ValueError) as info:
        compare_ensembles(a, b, ["speed", "bad"])
    assert str(info.value) == f"bad: {NON_FINITE_MESSAGE}"
    assert isinstance(info.value.__cause__, ValueError)


@pytest.mark.parametrize(("offset", "step"), [(0.0, 1.0), (1e6, 1.0 / 3.0)])
def test_two_sided_exact_counts_mirror_split(offset: float, step: float) -> None:
    # The observed split and its mirror have mean differences of +d and -d, with d = 8 * step.
    # With offset 1e6 and step 1/3 the float64 rounding of the group sums is of order offset * eps,
    # far larger than the statistic's own scale. A tolerance tied to |statistic| would drop the
    # mirror split there, which halves the p-value. The tolerance must scale with the data instead.
    x = [offset + step * k for k in range(9, 17)]
    y = [offset + step * k for k in range(1, 9)]
    assert permutation_pvalue(x, y, "two-sided") == 2 / math.comb(16, 8)


def test_power_guard_raises_when_no_key_can_be_rejected() -> None:
    # 3 vs 3 has C(6, 3) = 20 splits, so the smallest attainable p is 2 / 20 = 0.1. With 2 keys the
    # first Holm threshold is 0.01 / 2 = 0.005, which 0.1 cannot reach.
    a = [{"k": 1.0, "j": 1.0}, {"k": 2.0, "j": 2.0}, {"k": 3.0, "j": 3.0}]
    b = [{"k": 4.0, "j": 4.0}, {"k": 5.0, "j": 5.0}, {"k": 6.0, "j": 6.0}]
    with pytest.raises(ValueError) as info:
        compare_ensembles(a, b, ["k", "j"])
    assert str(info.value) == (
        "2 keys at alpha=0.01: the smallest attainable p 0.1 exceeds the first Holm threshold "
        "0.005, so no key can be rejected"
    )


def test_min_attainable_p_exact_branch_for_equal_sizes() -> None:
    a = [{"k": float(v)} for v in range(9, 17)]
    b = [{"k": float(v)} for v in range(1, 9)]
    comparison = compare_ensembles(a, b, ["k"])
    # n == m, so the mirror split is equally extreme: two splits reach the minimum.
    assert comparison.min_attainable_p == 2 / math.comb(16, 8)
    assert comparison.rejected == {"k": True}


def test_min_attainable_p_monte_carlo_branch() -> None:
    # C(40, 20) exceeds PERMUTATION_MAX_EXACT, so the test resamples and the minimum is 1 / (N + 1).
    a = [{"k": float(v)} for v in range(20)]
    b = [{"k": float(v) + 100.0} for v in range(20)]
    comparison = compare_ensembles(a, b, ["k"])
    assert comparison.min_attainable_p == 1 / 100_001
    assert comparison.rejected == {"k": True}


def test_effect_summary_values_and_constant_key_gives_none() -> None:
    a = [{"k": 1.0, "c": 240.0}, {"k": 2.0, "c": 240.0}, {"k": 3.0, "c": 240.0}]
    b = [{"k": 4.0, "c": 240.0}, {"k": 5.0, "c": 240.0}, {"k": 6.0, "c": 240.0}]
    summary = effect_summary(a, b, ["k", "c"])
    # Means 2 and 5, sd 1 each, so the pooled sd is 1 and cohen_d = -3 / 1.
    assert summary["k"] == {
        "mean_a": 2.0,
        "sd_a": 1.0,
        "mean_b": 5.0,
        "sd_b": 1.0,
        "diff": -3.0,
        "rel_diff": -0.6,
        "cohen_d": -3.0,
    }
    # The constant key has pooled sd 0, so cohen_d is None (never NaN). Its other fields are
    # defined.
    assert summary["c"]["cohen_d"] is None
    assert summary["c"]["mean_a"] == 240.0
    assert summary["c"]["sd_a"] == 0.0
    assert summary["c"]["diff"] == 0.0


def _separated_runs(keys: list[str], low: range, high: range) -> tuple[list[dict], list[dict]]:
    """Two ensembles of metric dicts, one run per value, identical for every key."""
    a = [{key: float(v) for key in keys} for v in high]
    b = [{key: float(v) for key in keys} for v in low]
    return a, b


def test_power_guard_boundary_on_fully_separated_8_vs_8() -> None:
    # The first Holm threshold is alpha / keys. With 8 vs 8 the smallest attainable p is
    # 2 / C(16, 8) = 1.55e-4, which is at most 0.01 / 46 = 2.17e-4 and above 0.01 / 67 = 1.49e-4.
    keys46 = [f"k{i}" for i in range(46)]
    a, b = _separated_runs(keys46, range(1, 9), range(9, 17))
    comparison = compare_ensembles(a, b, keys46, alpha=0.01)
    assert comparison.min_attainable_p == 2 / math.comb(16, 8)
    assert not comparison.indistinguishable

    keys67 = [f"k{i}" for i in range(67)]
    a, b = _separated_runs(keys67, range(1, 9), range(9, 17))
    with pytest.raises(ValueError, match="67 keys"):
        compare_ensembles(a, b, keys67, alpha=0.01)


def test_eight_vs_seven_minimum_is_one_over_c_15_7() -> None:
    a = [{"k": float(v)} for v in range(9, 17)]
    b = [{"k": float(v)} for v in range(1, 8)]
    comparison = compare_ensembles(a, b, ["k"], alpha=0.01)
    # Unequal sizes have no mirror split, so the two-sided minimum is 1 / C(15, 7).
    assert comparison.min_attainable_p == 1 / math.comb(15, 7)


def test_monte_carlo_minimum_is_one_over_resamples_plus_one() -> None:
    # 20 vs 20 has C(40, 20) > PERMUTATION_MAX_EXACT, so the test is Monte Carlo.
    assert min_attainable_pvalue(20, 20) == 1 / (PERMUTATION_RESAMPLES + 1)
    assert min_attainable_pvalue(20, 20, "greater") == 1 / (PERMUTATION_RESAMPLES + 1)
    # The exact branch takes over when the split count is within max_exact.
    assert min_attainable_pvalue(8, 8, max_exact=10, n_resamples=99) == 1 / 100
    assert min_attainable_pvalue(8, 8, max_exact=math.comb(16, 8)) == 2 / math.comb(16, 8)


def test_one_sided_minimum_has_no_mirror_factor() -> None:
    assert min_attainable_pvalue(8, 8, "greater") == 1 / math.comb(16, 8)
    assert min_attainable_pvalue(8, 8, "less") == 1 / math.comb(16, 8)
    assert min_attainable_pvalue(8, 8, "two-sided") == 2 / math.comb(16, 8)


def test_min_attainable_pvalue_rejects_bad_arguments() -> None:
    with pytest.raises(ValueError, match="alternative"):
        min_attainable_pvalue(8, 8, "sideways")
    with pytest.raises(ValueError, match="at least one value"):
        min_attainable_pvalue(0, 8)


def test_diffuse_key_family() -> None:
    keys = [
        "r2.mean.R",
        "r9.mean.R",
        "all.clip_fraction",
        "r4.lag1.x",
        "r10.mean.R",
        "r8.structure_std",
        "all.spectral_slope",
        "r0.structure_std",
    ]
    # Region 9 (the light) and regions 0 and 10 are outside DIFFUSE_REGION_IDS. Order is kept.
    assert diffuse_key_family(keys) == [
        "r2.mean.R",
        "all.clip_fraction",
        "r4.lag1.x",
        "r8.structure_std",
        "all.spectral_slope",
    ]
