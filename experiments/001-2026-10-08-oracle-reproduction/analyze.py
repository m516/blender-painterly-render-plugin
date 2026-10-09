"""Analysis of experiment 001 (T1.6, amended in T1.10): does the oracle reproduce the reference?

Re-runs from the render cache, so every render must already exist (``jobs.py``). Writes
``results.json`` and the ``fig_*.png`` previews to the output directory (default: next to this
file), and prints the tables. Deterministic: the only random numbers are the bootstrap indices from
``jax.random.PRNGKey(0)``.
"""

import argparse
import math
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
from painterly_analysis import (
    DIFFUSE_REGION_IDS,
    ensemble,
    metrics,
    read_ppm,
    report,
    smallpaint_display,
    write_png,
)
from painterly_analysis.experiment import load
from painterly_analysis.metrics import HIGHPASS_SIZE

EXP_DIR = Path(__file__).resolve().parent
EXPERIMENT = EXP_DIR.name
REPO_ROOT = EXP_DIR.parents[1]
REFERENCE_PPM = REPO_ROOT / "tests" / "data" / "reference" / "smallpaint_painterly.ppm"

ALPHA = 0.01  # family-wise level of every decision (README, Hypothesis)
PAIRS = 8
RENDERS_PER_P = 2 * PAIRS  # single renders per configuration: half a and half b of each pair
BACK_WALL_ID = 4  # SPEC §9 id of the back plane
P_VALUES = (16, 32, 64, 128, 256, 512)
P_MIN = P_VALUES[0]
P_MAX = P_VALUES[-1]
SENSITIVITY_P_MIN = 32  # sensitivity fit: OLS over P >= 32 (T1.10 card)
STRUCTURE_P_MIN = 64  # noise-corrected structure correlation over P >= 64 (T1.10 card)
BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_SEED = 0  # jax.random.PRNGKey(0)
CONFIDENCE = 0.95
DIFF_GAIN = 4  # fig_absdiff_P512: |ab8 - ref8| scaled by this factor, then clipped
DISPLAY_MAX = 255  # SPEC §7 display maximum


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analysis of experiment 001 (T1.6, T1.10).")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=EXP_DIR,
        help="directory for results.json and the figures (default: this directory)",
    )
    return parser.parse_args(argv)


def _masked_var(x, mask) -> float:
    """Population variance (ddof 0) of ``x`` over the pixels where ``mask`` is true."""
    values = jnp.asarray(x, dtype=jnp.float64)
    m = jnp.asarray(mask, dtype=bool)
    n = jnp.sum(m)
    mean = jnp.sum(jnp.where(m, values, 0.0)) / n
    return float(jnp.sum(jnp.where(m, (values - mean) ** 2, 0.0)) / n)


# Kept local rather than report.format_number: experiment 001 is final, and its printed tables and
# committed outputs are frozen byte for byte (T1.11, T1.15).
def _fmt(value, spec: str) -> str:
    return "undefined" if value is None else format(value, spec)


def _ab8(first, second) -> np.ndarray:
    """``ab8`` of a pair: the display image of the summed half renders at 2 * passes."""
    a = load(first)
    b = load(second)
    if a.passes != b.passes:
        raise ValueError(f"pair passes differ: {a.passes} vs {b.passes}")
    return smallpaint_display(np.asarray(a.sum) + np.asarray(b.sum), 2 * a.passes)


def _h1(ref8: np.ndarray, jobs: list, masks: dict, present: list[int]) -> dict:
    """Reference region means inside the prediction intervals of the img256 single renders."""
    m = 3 * len(present)
    alpha_each = ALPHA / m  # Bonferroni: each interval is at level 1 - alpha / m
    renders = [load(job) for job in jobs]
    rows = []
    for region in present:
        mask = masks[region]
        singles = np.array(
            [
                np.asarray(metrics.region_mean_rgb(smallpaint_display(r.sum, r.passes), mask))
                for r in renders
            ]
        )
        ref_mean = np.asarray(metrics.region_mean_rgb(ref8, mask))
        for channel, name in enumerate("RGB"):
            samples = singles[:, channel]
            lo, hi = ensemble.prediction_interval(samples, alpha_each)
            rows.append(
                {
                    "region": region,
                    "channel": name,
                    "n_single_renders": int(samples.size),
                    "mean": float(np.mean(samples)),
                    "sd": float(np.std(samples, ddof=1)),
                    "lo": lo,
                    "hi": hi,
                    "reference": float(ref_mean[channel]),
                    "inside": bool(lo <= ref_mean[channel] <= hi),
                }
            )
    inside = sum(row["inside"] for row in rows)
    return {
        "m": m,
        "alpha_per_interval": alpha_each,
        "rows": rows,
        "n_inside": inside,
        "supported": inside == m,
    }


def _compare(measures: dict, keys: list[str], a: str, b: str) -> dict:
    """Holm comparison over ``keys`` (the diffuse family) with the effect summary of each key."""
    test = report.family_test(measures[a], measures[b], keys, ALPHA)
    if not test["powered"]:
        raise ValueError(f"{a} vs {b} is underpowered: compare_ensembles would raise")
    rejected_keys = test["rejected_keys"]
    worst = test["largest_abs_cohen_d"]
    return {
        "a": a,
        "b": b,
        "n_keys": len(keys),
        "min_attainable_p": test["min_attainable_p"],
        "pvalues": test["pvalues"],
        "rejected": {key: key in rejected_keys for key in keys},
        "n_rejected": len(rejected_keys),
        "indistinguishable": not rejected_keys,
        "min_p": min(test["pvalues"].values()),
        "effect_summary": test["effect_summary"],
        "max_abs_cohen_d": worst["value"] if worst is not None else None,
        "max_abs_cohen_d_key": worst["key"] if worst is not None else None,
    }


def _backwall_fit(v_pairs, idx, x_design_pinv) -> tuple[jnp.ndarray, jnp.ndarray]:
    """Least-squares fit of v(P) = sigma_s^2 + sigma_n^2 / P for each resample.

    ``v_pairs`` is (len(P_VALUES), PAIRS, 2): the back-wall high-pass variance of each single
    render. ``idx`` is (R, PAIRS): the pairs of each resample. Returns (sigma_s^2, sigma_n^2), each
    of shape (R,).
    """
    sel = v_pairs[:, idx, :].reshape(len(P_VALUES), idx.shape[0], 2 * PAIRS)
    vbar = jnp.mean(sel, axis=2)  # (P, R): mean variance over the renders of each P
    coef = x_design_pinv @ vbar  # (2, R)
    return coef[0], coef[1]


def _ols(
    passes: np.ndarray, vbar: np.ndarray, weights: np.ndarray | None = None
) -> tuple[float, float]:
    """Least-squares fit of ``vbar = sigma_s^2 + sigma_n^2 / P``, weighted if ``weights`` is given.

    Returns (sigma_s^2, sigma_n^2).
    """
    design = np.stack([np.ones_like(passes), 1.0 / passes], axis=1)
    w = np.ones_like(vbar) if weights is None else np.sqrt(weights)
    coef = np.linalg.lstsq(design * w[:, None], vbar * w, rcond=None)[0]
    return float(coef[0]), float(coef[1])


def _p_from_q(q) -> float:
    """``P = 1 / q`` where ``q = (var_ref - sigma_s^2) / sigma_n^2``. inf when ``q <= 0``."""
    value = float(q)
    return 1.0 / value if value > 0 else math.inf


def _p_ref(var_ref: float, sigma_s2: float, sigma_n2: float) -> tuple[float, bool]:
    """Effective pass count from one fit: ``(P_ref, finite)``.

    ``q <= 0`` means the reference's variance is at or below the converged floor sigma_s^2, so no
    finite pass count reaches it. Then P_ref is inf and ``finite`` is False. Nothing is raised.
    """
    q = (np.float64(var_ref) - sigma_s2) / np.float64(sigma_n2)
    return _p_from_q(q), bool(q > 0)


def _fit_summary(var_ref: float, sigma_s2: float, sigma_n2: float) -> dict:
    p_ref, finite = _p_ref(var_ref, sigma_s2, sigma_n2)
    return {"sigma_s2": sigma_s2, "sigma_n2": sigma_n2, "P_ref": p_ref, "P_ref_finite": finite}


def _convergence(jobs_by_p: dict[int, list], ref8: np.ndarray, mask: jnp.ndarray) -> dict:
    """H4 effective pass count: solve v(P_ref) = var_ref with the fit of v(P) on the back wall."""
    v = np.zeros((len(P_VALUES), PAIRS, 2))
    for i, passes in enumerate(P_VALUES):
        # Jobs are in pair order: index 2k is half a of pair k, index 2k + 1 is half b.
        for j, job in enumerate(jobs_by_p[passes]):
            render = load(job)
            if render.passes != passes:
                raise ValueError(f"render passes {render.passes} != {passes}")
            hp = metrics.highpass(
                metrics.luminance(smallpaint_display(render.sum, passes)), HIGHPASS_SIZE
            )
            v[i, j // 2, j % 2] = _masked_var(hp, mask)
    v_pairs = jnp.asarray(v)
    var_ref = _masked_var(metrics.highpass(metrics.luminance(ref8), HIGHPASS_SIZE), mask)

    passes_arr = np.array(P_VALUES, dtype=np.float64)
    inverse_passes = jnp.asarray(1.0 / passes_arr)
    design = jnp.stack([jnp.ones_like(inverse_passes), inverse_passes], axis=1)
    design_pinv = jnp.linalg.pinv(design)

    # Point estimate: OLS of v(P) on 1/P over the six P values, all eight pairs.
    point_idx = jnp.arange(PAIRS)[None, :]
    s2, n2 = _backwall_fit(v_pairs, point_idx, design_pinv)
    sigma_s2, sigma_n2 = float(s2[0]), float(n2[0])
    point, point_defined = _p_ref(var_ref, sigma_s2, sigma_n2)
    if not bool(point_defined):
        print("H4: point estimate P_ref is inf (q <= 0), reported as inf")

    # Bootstrap: every resample is kept. Percentiles are taken on q = 1 / P_ref and mapped to P.
    key = jax.random.PRNGKey(BOOTSTRAP_SEED)
    boot_idx = jax.random.randint(key, (BOOTSTRAP_RESAMPLES, PAIRS), 0, PAIRS)
    boot_s2, boot_n2 = _backwall_fit(v_pairs, boot_idx, design_pinv)
    boot_s2 = np.asarray(boot_s2)
    boot_n2 = np.asarray(boot_n2)
    q_boot = (np.float64(var_ref) - boot_s2) / boot_n2
    tail = 100.0 * (1.0 - CONFIDENCE) / 2.0
    q_lo, q_hi = np.percentile(q_boot, [tail, 100.0 - tail])
    # P = 1 / q is decreasing in q, so the q-interval [q_lo, q_hi] maps to [1/q_hi, 1/q_lo].
    p_lo, p_hi = _p_from_q(q_hi), _p_from_q(q_lo)

    # Sensitivity fits, reported without intervals. The WLS weights are 1 / var(vbar), where vbar
    # averages RENDERS_PER_P renders, so var(vbar) = var16 / RENDERS_PER_P.
    v16 = v.reshape(len(P_VALUES), RENDERS_PER_P)
    vbar = v16.mean(axis=1)
    var16 = v16.var(axis=1, ddof=1)
    wls_s2, wls_n2 = _ols(passes_arr, vbar, RENDERS_PER_P / var16)
    high = passes_arr >= SENSITIVITY_P_MIN
    ols_s2, ols_n2 = _ols(passes_arr[high], vbar[high])
    weighted = _fit_summary(var_ref, wls_s2, wls_n2)
    ols_high = _fit_summary(var_ref, ols_s2, ols_n2)

    return {
        "v_mean_by_P": {str(p): float(np.mean(v[i])) for i, p in enumerate(P_VALUES)},
        "var_ref": var_ref,
        "sigma_s2": sigma_s2,
        "sigma_n2": sigma_n2,
        "P_ref": point,
        "P_ref_finite": bool(point_defined),
        "P_ref_ci": [p_lo, p_hi],
        "confidence": CONFIDENCE,
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "bootstrap_q_nonpositive": int(np.count_nonzero(q_boot <= 0)),
        "bootstrap_sigma_n2_nonpositive": int(np.count_nonzero(boot_n2 <= 0)),
        "interval_outside_tested_range": not (p_lo >= P_MIN and p_hi <= P_MAX),
        "recommended_passes": int(round(point)) if math.isfinite(point) else None,
        "weighted_fit_P_ref": weighted["P_ref"],
        "weighted_fit": weighted,
        "ols_p_ge_32_P_ref": ols_high["P_ref"],
        "ols_p_ge_32": ols_high,
    }


def _noise_structure_ratio(sigma_s2: float, sigma_n2: float) -> dict:
    """``sigma_n^2 / (sigma_s^2 * P)`` for each P, from the point fit. None when sigma_s^2 <= 0."""
    return {str(p): (sigma_n2 / (sigma_s2 * p) if sigma_s2 > 0 else None) for p in P_VALUES}


def _structure_correlation(measures: dict, conv: dict) -> dict:
    """Noise-corrected correlation of the back-wall structure with the reference, for P >= 64.

    Attenuation correction: ``rho = r_obs / sqrt(rel_render * rel_ref)``, where the reliability of a
    field is its structure share of the variance, ``rel = sigma_s^2 / var``. ``img{P}`` renders are
    ab8 (the sum of two renders at 2P passes), so ``var_render = sigma_s^2 + sigma_n^2 / (2P)``, and
    ``var_ref`` is the reference's variance. ``r_obs`` is the mean over the pairs of
    ``r4.pattern_corr``, the same back wall as the variance fit. An entry is None when a
    reliability is not positive.
    """
    s2 = conv["sigma_s2"]
    n2 = conv["sigma_n2"]
    var_ref = conv["var_ref"]
    key = f"r{BACK_WALL_ID}.pattern_corr"
    rel_ref = s2 / var_ref if var_ref > 0 else None
    out = {}
    for passes in P_VALUES:
        if passes < STRUCTURE_P_MIN:
            continue
        r_obs = float(np.mean([m[key] for m in measures[f"img{passes}"]]))
        var_render = s2 + n2 / (2 * passes)
        rel_render = s2 / var_render if var_render > 0 else None
        rho = None
        if rel_render is not None and rel_ref is not None and rel_render > 0 and rel_ref > 0:
            rho = r_obs / math.sqrt(rel_render * rel_ref)
        out[str(passes)] = {
            "r_obs": r_obs,
            "reliability_render": rel_render,
            "reliability_reference": rel_ref,
            "rho_corrected": rho,
        }
    return out


def _h4(measures: dict, jobs_by_p: dict[int, list], ref8: np.ndarray, mask: jnp.ndarray) -> dict:
    pattern = {p: [m["all.pattern_corr"] for m in measures[f"img{p}"]] for p in P_VALUES}
    # Adjacent steps lo -> hi of P. hi is tested against lo: "greater" is a rise, "less" a fall.
    steps = report.adjacent_tests(
        {str(p): measures[f"img{p}"] for p in P_VALUES},
        [str(p) for p in P_VALUES],
        "all.pattern_corr",
        ALPHA,
    )
    p_up = {name: step["p_greater"] for name, step in steps["steps"].items()}
    p_down = {name: step["p_less"] for name, step in steps["steps"].items()}
    up_rejected = steps["holm_rejected_greater"]
    down_rejected = steps["holm_rejected_less"]
    if all(up_rejected.values()):
        decision = "supported"
    elif any(down_rejected.values()):
        decision = "refuted"
    else:
        decision = "inconclusive"
    means = {
        str(p): {"mean": float(np.mean(pattern[p])), "sd": float(np.std(pattern[p], ddof=1))}
        for p in P_VALUES
    }
    conv = _convergence(jobs_by_p, ref8, mask)
    conv["noise_structure_ratio_by_P"] = _noise_structure_ratio(conv["sigma_s2"], conv["sigma_n2"])
    conv["structure_correlation_by_P"] = _structure_correlation(measures, conv)
    return {
        "all_pattern_corr_by_P": means,
        "p_greater": p_up,
        "p_less": p_down,
        "holm_rejected_greater": up_rejected,
        "holm_rejected_less": down_rejected,
        "decision": decision,
        "convergence": conv,
    }


def _h5(measures: dict) -> dict:
    pm = [m["all.pattern_corr"] for m in measures["pm64"]]
    img = [m["all.pattern_corr"] for m in measures["img64"]]
    p_less = ensemble.permutation_pvalue(pm, img, "less")
    p_greater = ensemble.permutation_pvalue(pm, img, "greater")
    if ensemble.separated(pm, img, "less", ALPHA):
        decision = "supported"
    elif p_greater <= ALPHA:
        decision = "refuted"
    else:
        decision = "inconclusive"
    return {
        "pm64_mean": float(np.mean(pm)),
        "img64_mean": float(np.mean(img)),
        "p_less": p_less,
        "p_greater": p_greater,
        "decision": decision,
    }


def _print_h1(h1: dict) -> None:
    print(
        f"H1 reference match: m={h1['m']}, interval alpha per test={h1['alpha_per_interval']:.6g}"
    )
    print(f"{'region':>6} {'ch':>3} {'mean':>9} {'sd':>8} {'lo':>9} {'hi':>9} {'ref':>9} inside")
    for row in h1["rows"]:
        print(
            f"{row['region']:>6} {row['channel']:>3} {row['mean']:9.3f} {row['sd']:8.3f} "
            f"{row['lo']:9.3f} {row['hi']:9.3f} {row['reference']:9.3f} {row['inside']}"
        )
    print(f"inside: {h1['n_inside']}/{h1['m']}  supported={h1['supported']}")


def _print_compare(name: str, cmp: dict) -> None:
    print(
        f"{name} {cmp['a']} vs {cmp['b']}: keys={cmp['n_keys']} rejected={cmp['n_rejected']} "
        f"min_p={cmp['min_p']:.6g} min_attainable_p={cmp['min_attainable_p']:.6g} "
        f"max|cohen_d|={_fmt(cmp['max_abs_cohen_d'], '.4g')} "
        f"({cmp['max_abs_cohen_d_key']}) indistinguishable={cmp['indistinguishable']}"
    )


def _print_h4(h4: dict) -> None:
    print("H4 all.pattern_corr by P (mean +- sd over 8 pairs):")
    for p, stats in h4["all_pattern_corr_by_P"].items():
        print(f"  P={p:>4}: {stats['mean']:.6f} +- {stats['sd']:.6f}")
    for step in h4["p_greater"]:
        print(
            f"  step {step}: p_greater={h4['p_greater'][step]:.6g} p_less={h4['p_less'][step]:.6g}"
        )
    print(f"  decision: {h4['decision']}")
    conv = h4["convergence"]
    print("  back-wall v(P) = mean population variance of single-render high-pass luminance:")
    for p, value in conv["v_mean_by_P"].items():
        print(f"    P={p:>4}: {value:.6f}")
    print(
        f"  var_ref={conv['var_ref']:.6f} sigma_s2={conv['sigma_s2']:.6f} "
        f"sigma_n2={conv['sigma_n2']:.6f}"
    )
    lo, hi = conv["P_ref_ci"]
    print(
        f"  P_ref={_fmt(conv['P_ref'], '.2f')} "
        f"95% bootstrap [{_fmt(lo, '.2f')}, {_fmt(hi, '.2f')}] "
        f"q<=0 resamples={conv['bootstrap_q_nonpositive']} "
        f"recommended={conv['recommended_passes']} "
        f"extrapolated={conv['interval_outside_tested_range']}"
    )
    print(
        f"  sensitivity: WLS P_ref={_fmt(conv['weighted_fit_P_ref'], '.2f')} "
        f"OLS P>=32 P_ref={_fmt(conv['ols_p_ge_32_P_ref'], '.2f')}"
    )
    for p, ratio in conv["noise_structure_ratio_by_P"].items():
        print(f"  sigma_n2/(sigma_s2 P) P={p:>4}: {_fmt(ratio, '.5f')}")
    for p, row in conv["structure_correlation_by_P"].items():
        print(
            f"  P={p:>4}: r_obs={row['r_obs']:.6f} "
            f"rel_render={_fmt(row['reliability_render'], '.4f')} "
            f"rel_ref={_fmt(row['reliability_reference'], '.4f')} "
            f"rho_corrected={_fmt(row['rho_corrected'], '.6f')}"
        )


def _json_safe(value):
    """Encode infinity as the strings "inf" and "-inf", which the results file can hold.

    NaN is left as it is, and ``report.write_results_json`` refuses it.
    """
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and math.isinf(value):
        return "inf" if value > 0 else "-inf"
    return value


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs_module = report.load_jobs_module(EXP_DIR / "jobs.py")
    ensembles = jobs_module.ENSEMBLES
    ref8 = read_ppm(REFERENCE_PPM)

    object_id = load(ensembles["img64"][0]).object_id
    for name, jobs in ensembles.items():
        if not np.array_equal(load(jobs[0]).object_id, object_id):
            raise RuntimeError(f"object id of {name} differs from img64")
    masks = metrics.region_masks(object_id, HIGHPASS_SIZE // 2)
    present = [r for r in DIFFUSE_REGION_IDS if r in masks]
    absent = [r for r in DIFFUSE_REGION_IDS if r not in masks]
    visible = set(np.unique(object_id).tolist())
    if any(r in visible for r in absent):
        raise RuntimeError(f"unmeasured diffuse regions {absent} have pixels")
    mask4 = masks[BACK_WALL_ID]

    measures = {
        name: report.ensemble_metrics(jobs, ref8, object_id=object_id)
        for name, jobs in ensembles.items()
    }
    keys = sorted(measures["img64"][0])
    for name, runs in measures.items():
        if sorted(runs[0]) != keys:
            raise RuntimeError(f"metric keys of {name} differ")
    family = metrics.diffuse_key_family(keys)

    h1 = _h1(ref8, ensembles["img256"], masks, present)
    h2 = [
        _compare(measures, family, "img64", "omp4_64"),
        _compare(measures, family, "img64", "omp16_64"),
    ]
    h2_supported = all(cmp["indistinguishable"] for cmp in h2)
    h3 = _compare(measures, family, "img64", "exact64")
    jobs_by_p = {p: ensembles[f"img{p}"] for p in P_VALUES}
    h4 = _h4(measures, jobs_by_p, ref8, mask4)
    h5 = _h5(measures)

    fig_pair0_512 = _ab8(*ensembles["img512"][:2])
    fig_pair0_pm = _ab8(*ensembles["pm64"][:2])
    write_png(out_dir / "fig_reference.png", ref8)
    write_png(out_dir / "fig_image_P512.png", fig_pair0_512)
    write_png(out_dir / "fig_pixel_major_P64.png", fig_pair0_pm)
    diff = np.clip(
        DIFF_GAIN * np.abs(fig_pair0_512.astype(np.int64) - ref8.astype(np.int64)), 0, DISPLAY_MAX
    ).astype(np.uint8)
    write_png(out_dir / "fig_absdiff_P512.png", diff)
    figures = {
        name: (out_dir / name).stat().st_size
        for name in (
            "fig_reference.png",
            "fig_image_P512.png",
            "fig_pixel_major_P64.png",
            "fig_absdiff_P512.png",
        )
    }

    results = {
        "experiment": EXPERIMENT,
        "alpha": ALPHA,
        "pairs": PAIRS,
        "size": 400,
        "highpass_size": HIGHPASS_SIZE,
        "erosion_radius": HIGHPASS_SIZE // 2,
        "regions": {"diffuse_ids": list(DIFFUSE_REGION_IDS), "measured": present, "absent": absent},
        "object_id_values": sorted(visible),
        "metric_keys": {"all": len(keys), "diffuse_family": len(family), "family": family},
        "configurations": {
            name: {
                "options": dict(jobs[0].options),
                "seeds": [job.seed for job in jobs],
            }
            for name, jobs in ensembles.items()
        },
        "h1": h1,
        "h2": {"decision": "supported" if h2_supported else "refuted", "comparisons": h2},
        "h3": {
            "decision": "supported" if h3["indistinguishable"] else "refuted",
            "comparison": h3,
        },
        "h4": h4,
        "h5": h5,
        "figures": figures,
    }
    report.write_results_json(out_dir / "results.json", _json_safe(results))

    _print_h1(h1)
    for cmp in h2:
        _print_compare("H2", cmp)
    _print_compare("H3", h3)
    _print_h4(h4)
    print(
        f"H5 pm64 vs img64: mean {h5['pm64_mean']:.6f} vs {h5['img64_mean']:.6f} "
        f"p_less={h5['p_less']:.6g} p_greater={h5['p_greater']:.6g} decision={h5['decision']}"
    )
    print(f"keys all={len(keys)} diffuse family={len(family)}")
    print(f"measured regions {present}, absent {absent}")
    print(f"figures (bytes): {figures}")


if __name__ == "__main__":
    main()
