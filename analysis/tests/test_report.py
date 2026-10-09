"""Unit tests of the shared experiment helpers in painterly_analysis.report (T1.11).

The permutation p-values are exact: fully separated 8-vs-8 samples have p = 2 / C(16, 8) two-sided
and 1 / C(16, 8) one-sided, so the expected values are closed forms, not tolerances.
"""

import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from painterly_analysis import report
from painterly_analysis.experiment import Job, ensemble_jobs

SEPARATED = 2 / math.comb(16, 8)  # two-sided minimum for fully separated 8 vs 8
ONE_SIDED = 1 / math.comb(16, 8)


def _runs(columns: dict[str, list[float]]) -> list[dict[str, float]]:
    """Per-run metric dicts from columns: run i holds the i-th value of every key."""
    count = len(next(iter(columns.values())))
    return [{key: values[i] for key, values in columns.items()} for i in range(count)]


HIGH = _runs({"k": [float(v) for v in range(9, 17)]})  # mean 12.5
LOW = _runs({"k": [float(v) for v in range(1, 9)]})  # mean 4.5


def test_largest_abs_rel_diff_skips_none_and_breaks_ties_by_name() -> None:
    summary = {
        "a": {"rel_diff": -0.5, "cohen_d": None},
        "b": {"rel_diff": 0.5, "cohen_d": 1.0},
        "c": {"rel_diff": None, "cohen_d": 2.0},
    }
    # |a| and |b| tie at 0.5, and the larger key name wins. c is skipped.
    assert report.largest_abs_rel_diff(summary) == {"key": "b", "value": 0.5}


def test_largest_abs_rel_diff_is_none_when_undefined() -> None:
    assert report.largest_abs_rel_diff({"x": {"rel_diff": None}}) is None


def test_largest_abs_cohen_d_uses_the_cohen_field() -> None:
    summary = {
        "a": {"rel_diff": 9.0, "cohen_d": -3.0},
        "b": {"rel_diff": 0.1, "cohen_d": None},
        "c": {"rel_diff": 0.2, "cohen_d": 2.0},
    }
    assert report.largest_abs_cohen_d(summary) == {"key": "a", "value": 3.0}
    assert report.largest_abs_cohen_d({"x": {"cohen_d": None}}) is None


def test_pair_test_separated_two_sided_and_one_sided() -> None:
    test = report.pair_test(HIGH, LOW, "k", "two-sided", 0.01)
    assert test["p_value"] == SEPARATED
    assert test["min_attainable_p"] == SEPARATED
    assert test["rejected"] is True
    assert test["effect"]["diff"] == 8.0  # mean 12.5 minus mean 4.5, both exact in float64
    # "less" asks whether LOW is lower than HIGH: only the observed split is as extreme.
    assert report.pair_test(LOW, HIGH, "k", "less", 0.01)["p_value"] == ONE_SIDED
    assert report.pair_test(HIGH, LOW, "k", "greater", 0.01)["p_value"] == ONE_SIDED


def test_pair_test_identical_samples_are_not_rejected() -> None:
    test = report.pair_test(LOW, LOW, "k", "two-sided", 0.01)
    assert test["p_value"] == 1.0
    assert test["rejected"] is False


def test_family_test_powered_46_keys_rejects_every_key() -> None:
    keys = [f"k{i}" for i in range(46)]
    a = _runs({key: [float(v) for v in range(9, 17)] for key in keys})
    b = _runs({key: [float(v) for v in range(1, 9)] for key in keys})
    record = report.family_test(a, b, keys, 0.01)
    assert record["powered"] is True
    assert record["holm_first_threshold"] == 0.01 / 46
    assert record["min_attainable_p"] == SEPARATED
    assert record["rejected_keys"] == keys
    assert record["pvalues"] == {key: SEPARATED for key in keys}
    assert record["n_keys"] == 46
    assert record["largest_abs_rel_diff"] is not None
    assert record["largest_abs_cohen_d"] is not None


def test_family_test_underpowered_is_not_run_through_compare_ensembles() -> None:
    keys = [f"k{i}" for i in range(46)]
    a = _runs({key: [1.0, 2.0] for key in keys})
    b = _runs({key: [3.0, 4.0] for key in keys})
    record = report.family_test(a, b, keys, 0.01)
    # 2 vs 2 has a smallest p of 2 / C(4, 2) = 1/3, above the first threshold 0.01 / 46.
    assert record["powered"] is False
    assert record["min_attainable_p"] == 2 / math.comb(4, 2)
    assert record["rejected_keys"] is None
    assert set(record["pvalues"]) == set(keys)


def test_family_test_needs_a_key() -> None:
    with pytest.raises(ValueError, match="at least one key"):
        report.family_test(HIGH, LOW, [], 0.01)


def test_adjacent_tests_increasing_ladder_is_significant_increases() -> None:
    ladder = {
        "low": LOW,
        "mid": _runs({"k": [float(v) for v in range(9, 17)]}),
        "top": _runs({"k": [float(v) for v in range(17, 25)]}),
    }
    result = report.adjacent_tests(ladder, ["low", "mid", "top"], "k", 0.01)
    assert set(result["steps"]) == {"low->mid", "mid->top"}
    assert result["steps"]["low->mid"]["comparison"] == "mid vs low"
    assert result["significant_increases"] == ["low->mid", "mid->top"]
    assert result["significant_decreases"] == []
    assert result["powered"] is True  # 1 / C(16, 8) <= 0.01 / 2


def test_adjacent_tests_reversed_order_gives_decreases() -> None:
    ladder = {
        "low": LOW,
        "mid": _runs({"k": [float(v) for v in range(9, 17)]}),
        "top": _runs({"k": [float(v) for v in range(17, 25)]}),
    }
    result = report.adjacent_tests(ladder, ["top", "mid", "low"], "k", 0.01)
    assert result["significant_decreases"] == ["top->mid", "mid->low"]
    assert result["significant_increases"] == []


def test_adjacent_tests_rejects_duplicate_or_short_orders() -> None:
    with pytest.raises(ValueError, match="distinct"):
        report.adjacent_tests({"a": HIGH}, ["a", "a"], "k", 0.01)
    with pytest.raises(ValueError, match="distinct"):
        report.adjacent_tests({"a": HIGH}, ["a"], "k", 0.01)


def test_markdown_table_formats_cells() -> None:
    rows = [
        {"name": "a|b", "x": 0.123456789, "ok": True, "miss": None},
        {"name": "c", "x": 2.0, "ok": False, "miss": 3},
    ]
    text = report.markdown_table(rows, ["name", "x", "ok", "miss"])
    assert text == (
        "| name | x | ok | miss |\n"
        "|---|---|---|---|\n"
        "| a\\|b | 0.123457 | yes | n/a |\n"
        "| c | 2 | no | 3 |"
    )


def test_markdown_table_header_only_and_errors() -> None:
    assert report.markdown_table([], ["a"]) == "| a |\n|---|"
    with pytest.raises(KeyError):
        report.markdown_table([{"a": 1}], ["a", "missing"])
    with pytest.raises(ValueError, match="column"):
        report.markdown_table([], [])


def test_write_results_json_sorts_keys_and_ends_with_newline(tmp_path: Path) -> None:
    path = tmp_path / "results.json"
    report.write_results_json(path, {"b": 1.5, "a": [1, {"d": 2.0, "c": "x"}]})
    assert path.read_text(encoding="utf-8") == (
        '{\n  "a": [\n    1,\n    {\n      "c": "x",\n      "d": 2.0\n    }\n  ],\n  "b": 1.5\n}\n'
    )


def test_write_results_json_is_deterministic(tmp_path: Path) -> None:
    obj = {"z": [0.1, 1e-5], "y": {"q": 3, "p": 0.30000000000000004}}
    first, second = tmp_path / "one.json", tmp_path / "two.json"
    report.write_results_json(first, obj)
    report.write_results_json(second, dict(reversed(list(obj.items()))))
    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text(encoding="utf-8")) == obj


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, np.float64("nan")])
def test_write_results_json_rejects_non_finite_numbers(tmp_path: Path, bad: float) -> None:
    path = tmp_path / "results.json"
    with pytest.raises(ValueError, match="finite"):
        report.write_results_json(path, {"outer": [{"inner": bad}]})
    assert not path.exists()


def test_load_jobs_module_imports_a_file_by_path(tmp_path: Path) -> None:
    directory = tmp_path / "010-exp"
    directory.mkdir()
    jobs = directory / "jobs.py"
    jobs.write_text("VALUE = 7\nJOBS = []\n", encoding="utf-8")
    module = report.load_jobs_module(jobs)
    assert module.VALUE == 7
    assert module.JOBS == []


def test_diffuse_only_sets_other_ids_to_minus_one() -> None:
    object_id = np.array([[0, 2], [9, 4]], dtype=np.int64)
    kept = report.diffuse_only(object_id, [2, 4])
    assert kept.tolist() == [[-1, 2], [-1, 4]]
    assert object_id.tolist() == [[0, 2], [9, 4]]  # the input is not modified


def _fake_render(seed: int, passes: int = 4, object_id=None) -> SimpleNamespace:
    ids = np.array([[2, 4], [2, 4]]) if object_id is None else object_id
    return SimpleNamespace(sum=np.full((2, 2, 3), float(seed)), passes=passes, object_id=ids)


@pytest.fixture
def fake_renders(monkeypatch: pytest.MonkeyPatch) -> dict[int, SimpleNamespace]:
    """Stand-ins for the cached renders, keyed by seed, with a stub for metrics.measure."""
    renders: dict[int, SimpleNamespace] = {seed: _fake_render(seed) for seed in range(4)}
    monkeypatch.setattr(report, "load", lambda job: renders[job.seed])

    def stub_measure(sum_a, sum_b, passes, ref8, object_id):
        return {
            "sum_a": float(sum_a[0, 0, 0]),
            "sum_b": float(sum_b[0, 0, 0]),
            "passes": passes,
            "object_id": object_id.tolist(),
        }

    monkeypatch.setattr(report.metrics, "measure", stub_measure)
    return renders


def test_ensemble_metrics_measures_each_pair_in_order(fake_renders) -> None:
    jobs = ensemble_jobs("x", 2, size=2, passes=4)
    results = report.ensemble_metrics(jobs, None, regions=[2])
    assert [(r["sum_a"], r["sum_b"]) for r in results] == [(0.0, 1.0), (2.0, 3.0)]
    assert results[0]["object_id"] == [[2, -1], [2, -1]]
    assert results[0]["passes"] == 4


def test_ensemble_metrics_without_regions_passes_the_raw_map(fake_renders) -> None:
    results = report.ensemble_metrics(ensemble_jobs("x", 1, size=2, passes=4), None)
    assert results[0]["object_id"] == [[2, 4], [2, 4]]


def test_ensemble_metrics_rejects_a_render_with_another_object_id(fake_renders) -> None:
    fake_renders[3] = _fake_render(3, object_id=np.array([[2, 4], [4, 4]]))
    with pytest.raises(ValueError, match="object id"):
        report.ensemble_metrics(ensemble_jobs("x", 2, size=2, passes=4), None)


def test_ensemble_metrics_rejects_pairs_with_different_passes(fake_renders) -> None:
    fake_renders[1] = _fake_render(1, passes=8)
    with pytest.raises(ValueError, match="passes differ"):
        report.ensemble_metrics(ensemble_jobs("x", 1, size=2, passes=4), None)


@pytest.mark.parametrize("count", [0, 3])
def test_ensemble_metrics_needs_whole_pairs(fake_renders, count: int) -> None:
    jobs: list[Job] = [Job.make("x", seed, size=2, passes=4) for seed in range(count)]
    with pytest.raises(ValueError, match="pairs"):
        report.ensemble_metrics(jobs, None)
