"""Permutation, sign-flip, Holm and Student-t statistics (T1.2).

The expected values are exact. The only tolerance is the bisection's xtol.
"""

import math

from painterly_analysis import holm, permutation_pvalue, sign_flip_pvalue, student_t_ppf


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
