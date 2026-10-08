"""Statistics for deciding look fidelity without hand-picked thresholds (JAX).

``alpha`` is a *knob*: the family-wise error rate of a decision, Holm-corrected across the keys
of a comparison. The default of 0.01 is a convention, not a fitted value. Every p-value here is a
permutation or sign-flip p-value, so no distributional assumption is made. The Student-t
functions are needed only for prediction intervals.
"""

import itertools
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import jax
import jax.numpy as jnp
import numpy as np
from jax import Array
from jax.scipy.special import betainc

_ALTERNATIVES = ("two-sided", "greater", "less")
# Ties are counted within 64 eps of the largest |statistic|: float64 summation round-off, as in
# SciPy's permutation tests.
_TIE_ULPS = 64
_EPS = float(np.finfo(np.float64).eps)
# Sign-flip tests enumerate all 2**n patterns exactly up to this n (2**20 float64 values: 8 MiB).
SIGN_FLIP_EXACT_MAX_N = 20
# Patterns evaluated per block in the exact sign-flip enumeration, to bound memory.
_SIGN_FLIP_BLOCK = 2**16


def _check_alternative(alternative: str) -> None:
    if alternative not in _ALTERNATIVES:
        raise ValueError(f"alternative must be one of {_ALTERNATIVES}, got {alternative!r}")


def _tie_tolerance(stats: np.ndarray) -> float:
    # Mirror-image splits can differ by a few ulps of the largest statistic through float64
    # summation round-off.
    return _TIE_ULPS * _EPS * float(np.max(np.abs(stats)))


def _check_finite(*samples: np.ndarray) -> None:
    # A NaN or inf sample would make every statistic NaN and every p-value meaningless.
    if not all(bool(np.all(np.isfinite(sample))) for sample in samples):
        raise ValueError("samples must be finite (got NaN or inf)")


def _count_as_extreme(stats: np.ndarray, observed: float, alternative: str) -> int:
    """Count the statistics at least as extreme as ``observed`` in the direction of the test."""
    tol = _tie_tolerance(np.append(stats, observed))
    if alternative == "two-sided":
        return int(np.count_nonzero(np.abs(stats) >= abs(observed) - tol))
    if alternative == "greater":
        return int(np.count_nonzero(stats >= observed - tol))
    return int(np.count_nonzero(stats <= observed + tol))


def permutation_pvalue(
    x,
    y,
    alternative: str = "two-sided",
    *,
    max_exact: int = 100_000,
    n_resamples: int = 100_000,
) -> float:
    """Two-sample permutation p-value for the statistic ``mean(x) - mean(y)``.

    The test is exact when ``C(n + m, n) <= max_exact``: every split of the pooled sample into
    groups of sizes n and m is enumerated. Otherwise it uses ``n_resamples`` random permutations
    drawn with ``jax.random.PRNGKey(0)``, and the p-value is ``(k + 1) / (N + 1)``.

    Raises ValueError if any sample is NaN or inf.
    """
    _check_alternative(alternative)
    xs = np.asarray(x, dtype=np.float64).ravel()
    ys = np.asarray(y, dtype=np.float64).ravel()
    n, m = xs.size, ys.size
    if n < 1 or m < 1:
        raise ValueError("both groups need at least one value")
    _check_finite(xs, ys)
    pooled = jnp.asarray(np.concatenate([xs, ys]))
    total = jnp.sum(pooled)

    def stat_from_sum(sum_x):
        # mean(y) = (total - sum_x) / m, so the statistic depends only on the sum of the x group.
        return sum_x / n - (total - sum_x) / m

    comb = math.comb(n + m, n)
    if comb <= max_exact:
        idx = np.fromiter(
            itertools.chain.from_iterable(itertools.combinations(range(n + m), n)),
            dtype=np.int64,
            count=comb * n,
        ).reshape(comb, n)
        stats = np.asarray(stat_from_sum(jnp.sum(pooled[jnp.asarray(idx)], axis=1)))
        # itertools.combinations yields (0, ..., n-1) first: that is the observed split.
        return _count_as_extreme(stats, float(stats[0]), alternative) / comb

    keys = jax.random.split(jax.random.PRNGKey(0), n_resamples)

    def one_permutation(key):
        perm = jax.random.permutation(key, n + m)
        return jnp.sum(pooled[perm[:n]])

    stats = np.asarray(stat_from_sum(jax.lax.map(one_permutation, keys)))
    observed = float(stat_from_sum(jnp.sum(pooled[:n])))
    count = _count_as_extreme(stats, observed, alternative)
    return (count + 1) / (n_resamples + 1)


def sign_flip_pvalue(x, alternative: str, *, n_resamples: int = 100_000) -> float:
    """One-sample sign-flip p-value for the statistic ``mean(x)`` under the null of mean 0.

    Under the null each value's sign is equally likely to be + or -. The test is exact over all
    ``2**n`` sign patterns when ``n <= SIGN_FLIP_EXACT_MAX_N``. Otherwise it draws
    ``n_resamples`` Rademacher patterns with ``jax.random.PRNGKey(0)``, and the p-value is
    ``(k + 1) / (N + 1)``.

    Raises ValueError if any sample is NaN or inf.
    """
    _check_alternative(alternative)
    xs = np.asarray(x, dtype=np.float64).ravel()
    n = xs.size
    if n < 1:
        raise ValueError("need at least one value")
    _check_finite(xs)
    values = jnp.asarray(xs)
    observed = float(jnp.mean(values))

    if n <= SIGN_FLIP_EXACT_MAX_N:
        total = 2**n
        blocks = []
        for start in range(0, total, _SIGN_FLIP_BLOCK):
            codes = jnp.arange(start, min(start + _SIGN_FLIP_BLOCK, total))
            bits = (codes[:, None] >> jnp.arange(n)) & 1
            signs = (1 - 2 * bits).astype(jnp.float64)
            blocks.append(signs @ values)
        stats = np.asarray(jnp.concatenate(blocks)) / n
        # Pattern code 0 (all signs +) is the observed sample.
        return _count_as_extreme(stats, observed, alternative) / total

    keys = jax.random.split(jax.random.PRNGKey(0), n_resamples)

    def one_flip(key):
        signs = jax.random.rademacher(key, (n,), dtype=jnp.float64)
        return jnp.dot(signs, values) / n

    stats = np.asarray(jax.lax.map(one_flip, keys))
    count = _count_as_extreme(stats, observed, alternative)
    return (count + 1) / (n_resamples + 1)


def holm(pvalues: Mapping[str, float], alpha: float) -> dict[str, bool]:
    """Holm-Bonferroni step-down decisions at family-wise level ``alpha``.

    Hypotheses are sorted by increasing p, with ties broken by key. The i-th smallest (1-based) is
    rejected if ``p_(i) <= alpha / (m - i + 1)``. The procedure stops at the first failure.
    Returns a decision for every key, in the input order.
    """
    m = len(pvalues)
    order = sorted(pvalues, key=lambda key: (pvalues[key], key))
    rejected = {key: False for key in pvalues}
    for rank, key in enumerate(order):
        if pvalues[key] <= alpha / (m - rank):
            rejected[key] = True
        else:
            break
    return rejected


def student_t_cdf(t, dof: float) -> Array:
    """CDF of Student's t with ``dof`` degrees of freedom, via the regularised incomplete beta.

    For t >= 0 the upper tail is ``I_x(dof/2, 1/2) / 2`` with ``x = dof / (dof + t**2)``.
    """
    t = jnp.asarray(t, dtype=jnp.float64)
    nu = jnp.asarray(dof, dtype=jnp.float64)
    tail = 0.5 * betainc(nu / 2.0, 0.5, nu / (nu + t * t))
    return jnp.where(t >= 0, 1.0 - tail, tail)


def student_t_ppf(q: float, dof: float, xtol: float = 1e-12) -> float:
    """Quantile of Student's t, found by bisection on ``student_t_cdf``.

    ``xtol`` is the bisection's convergence parameter: iteration stops when the bracket is
    narrower than ``xtol``. The bracket starts at [-1, 1] and grows geometrically until it
    contains ``q``.
    """
    if not 0.0 < q < 1.0:
        raise ValueError("q must be in (0, 1)")
    cdf = jax.jit(student_t_cdf)
    lo, hi = -1.0, 1.0
    while float(cdf(lo, dof)) > q:
        lo *= 2.0
    while float(cdf(hi, dof)) < q:
        hi *= 2.0
    while hi - lo > xtol:
        mid = 0.5 * (lo + hi)
        if float(cdf(mid, dof)) < q:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def prediction_interval(samples, alpha: float) -> tuple[float, float]:
    """Prediction interval for one new draw: ``mean +- t_{1-alpha/2, n-1} * s * sqrt(1 + 1/n)``.

    ``s`` is the sample standard deviation with ddof 1. Requires at least two samples.
    """
    values = np.asarray(samples, dtype=np.float64).ravel()
    n = values.size
    if n < 2:
        raise ValueError("need at least two samples")
    mean = float(np.mean(values))
    s = float(np.std(values, ddof=1))
    half = student_t_ppf(1.0 - alpha / 2.0, n - 1) * s * math.sqrt(1.0 + 1.0 / n)
    return mean - half, mean + half


@dataclass
class Comparison:
    """Result of ``compare_ensembles``: per-key p-values and Holm decisions."""

    pvalues: dict
    rejected: dict

    @property
    def indistinguishable(self) -> bool:
        """True when no key is rejected, so the two ensembles are not distinguished on any key."""
        return not any(self.rejected.values())


def compare_ensembles(
    a: list[dict], b: list[dict], keys: Iterable[str], alpha: float = 0.01
) -> Comparison:
    """Compare two ensembles of metric dicts key by key.

    For each key, a two-sided permutation test is run between the values in ``a`` and in ``b``.
    The p-values are then Holm-corrected at family-wise level ``alpha``.

    A ValueError from any key is re-raised with the key name prefixed, e.g. ``"key: samples must
    be finite (got NaN or inf)"``.
    """
    pvalues: dict[str, float] = {}
    for key in keys:
        xs = [run[key] for run in a]
        ys = [run[key] for run in b]
        try:
            pvalues[key] = permutation_pvalue(xs, ys, "two-sided")
        except ValueError as e:
            raise ValueError(f"{key}: {e}") from e
    return Comparison(pvalues=pvalues, rejected=holm(pvalues, alpha))


def separated(pos: list[float], neg: list[float], alternative: str, alpha: float = 0.01) -> bool:
    """True when the permutation p-value of ``pos`` against ``neg`` is at most ``alpha``."""
    return permutation_pvalue(pos, neg, alternative) <= alpha
