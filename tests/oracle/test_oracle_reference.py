"""Slow statistical test: the oracle correlates with the reference look, and each SPEC ingredient is
necessary (T1.3).

Four configurations are rendered at 400 pixels with ENSEMBLE_PASSES passes each:
- ``positive``: SPEC reference mode (``chain=image``);
- three negative controls, each with one SPEC ingredient removed.

The test checks two things only: that the positive pattern correlates with the reference image,
and that each negative control correlates significantly worse. It does not claim that the oracle
is indistinguishable from the reference.
"""

import json
from pathlib import Path

import numpy as np
import pytest
from painterly_analysis import ensemble, measure, read_ppm

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_PPM = REPO_ROOT / "tests" / "data" / "reference" / "smallpaint_painterly.ppm"
REPORT_PATH = REPO_ROOT / ".cache" / "test_reports" / "oracle_reference.json"

# Pairs of independent half renders per configuration. Seeds 2k and 2k+1 form pair k.
# 8 pairs give exact permutation p-values down to 1.6e-4 (= 2 / C(16, 8)). With alpha = 0.01 and
# Holm over at most 4 comparisons this is enough.
ENSEMBLE_PAIRS = 8
# Passes per half render. Provisional: the X-oracle experiment estimates the reference's pass
# count, and this constant then cites it.
ENSEMBLE_PASSES = 32
# Significance level of the decisions, Holm-corrected across the negative controls. This is the
# test's own level, not the oracle's ``alpha`` knob (the ``normalized`` control's exponent).
ALPHA = 0.01
IMAGE_SIZE = 400

# The positive configuration is the SPEC reference mode. Each negative control removes one SPEC
# ingredient: per-path random starts (§3), normalisation of the direction (§4), and an
# independent u2 (§4).
CONFIGS = {
    "positive": {"chain": "image"},
    "per_path_random_start": {"chain": "lane:1"},
    "normalized": {"alpha": 1},
    "u2_independent": {"u2": "independent"},
}
NEGATIVE_CONTROLS = ("per_path_random_start", "normalized", "u2_independent")
POSITIVE_KEY = "all.pattern_corr"


def _format_table(means: dict[str, dict[str, float]]) -> str:
    width = 22
    header = f"{'metric':<{width}}" + "".join(f"{name:>{width}}" for name in CONFIGS)
    lines = [header, "-" * len(header)]
    for key in means["positive"]:
        cells = "".join(f"{means[name][key]:>{width}.6g}" for name in CONFIGS)
        lines.append(f"{key:<{width}}{cells}")
    return "\n".join(lines)


@pytest.mark.slow
def test_oracle_correlates_with_reference_and_controls_are_worse(oracle, tmp_path) -> None:
    reference = read_ppm(REFERENCE_PPM)
    seeds_per_config = 2 * ENSEMBLE_PAIRS

    jobs = []
    for name, options in CONFIGS.items():
        for seed in range(seeds_per_config):
            out_dir = tmp_path / name / f"seed-{seed}"
            jobs.append(
                (out_dir, {"size": IMAGE_SIZE, "passes": ENSEMBLE_PASSES, "seed": seed, **options})
            )
    renders = oracle.run_many(jobs)
    by_config = {
        name: renders[i * seeds_per_config : (i + 1) * seeds_per_config]
        for i, name in enumerate(CONFIGS)
    }

    # summary[config][key] is the list of per-pair values of that metric.
    summary: dict[str, dict[str, list[float]]] = {}
    for name in CONFIGS:
        runs = by_config[name]
        per_pair = []
        for k in range(ENSEMBLE_PAIRS):
            object_id = by_config["positive"][2 * k].object_id
            per_pair.append(
                measure(runs[2 * k].sum, runs[2 * k + 1].sum, ENSEMBLE_PASSES, reference, object_id)
            )
        summary[name] = {key: [pair[key] for pair in per_pair] for key in per_pair[0]}

    means = {
        name: {key: float(np.mean(values)) for key, values in summary[name].items()}
        for name in CONFIGS
    }
    print()
    print(_format_table(means))

    positive = summary["positive"][POSITIVE_KEY]
    p_positive = ensemble.sign_flip_pvalue(positive, "greater")
    # separated() is permutation_pvalue(...) <= alpha. The Holm step needs the p-values themselves.
    p_controls = {
        name: ensemble.permutation_pvalue(positive, summary[name][POSITIVE_KEY], "greater")
        for name in NEGATIVE_CONTROLS
    }
    rejected = ensemble.holm(p_controls, ALPHA)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "image_size": IMAGE_SIZE,
        "pairs": ENSEMBLE_PAIRS,
        "passes": ENSEMBLE_PASSES,
        "alpha": ALPHA,
        "means": means,
        "p_positive_pattern_corr_greater_than_zero": p_positive,
        "p_positive_vs_control_pattern_corr": p_controls,
        "holm_rejected": rejected,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    assert p_positive < ALPHA, f"positive pattern correlation not significant: p={p_positive}"
    assert all(rejected.values()), f"control separation failed under Holm: p={p_controls}"
