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


def test_directional_pair_test_both_one_sided_directions() -> None:
    test = report.directional_pair_test(LOW, HIGH, "k", 0.01, labels=("low", "high"))
    assert set(test) == {"comparison", "key", "p_less", "p_greater", "min_attainable_p", "effect"}
    assert test["comparison"] == "low vs high"
    assert test["key"] == "k"
    # LOW is lower than HIGH: only the observed split is as extreme, so p_less = 1 / C(16, 8).
    assert test["p_less"] == ONE_SIDED
    # The "greater" question (LOW higher than HIGH) cannot be answered with a split this extreme.
    assert test["p_greater"] == 1.0
    assert test["min_attainable_p"] == ONE_SIDED
    assert test["effect"]["diff"] == -8.0  # mean 4.5 minus mean 12.5, both exact in float64


def test_directional_pair_test_default_labels_and_order() -> None:
    test = report.directional_pair_test(HIGH, LOW, "k", 0.01)
    assert test["comparison"] == "a vs b"
    assert test["p_less"] == 1.0
    assert test["p_greater"] == ONE_SIDED
    assert test["effect"]["diff"] == 8.0


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


def test_ab8_of_pair_sums_the_halves_then_maps_at_twice_the_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    halves = {
        0: SimpleNamespace(sum=np.full((2, 2, 3), 101.0), passes=4, object_id=None),
        1: SimpleNamespace(sum=np.full((2, 2, 3), 60.0), passes=4, object_id=None),
    }
    monkeypatch.setattr(report, "load", lambda job: halves[job.seed])
    img = report.ab8_of_pair(ensemble_jobs("x", 1, size=2, passes=4))
    # (101 + 60) / (4 + 4) = 20.125, which SPEC §7 truncates to 20 in every channel.
    assert img.dtype == np.uint8
    assert np.array_equal(img, np.full((2, 2, 3), 20, dtype=np.uint8))


def test_block_preview_rounds_each_block_mean() -> None:
    # Block means over 2 x 2: 1.75 rounds to 2, 3 stays 3, 0.25 rounds to 0, 255 stays 255.
    grid = np.array(
        [[1, 2, 3, 3], [2, 2, 3, 3], [0, 0, 255, 255], [0, 1, 255, 255]], dtype=np.uint8
    )
    img = np.repeat(grid[:, :, None], 3, axis=2)
    preview = report.block_preview(img, 2)
    assert preview.dtype == np.uint8
    assert preview.shape == (2, 2, 3)
    assert np.array_equal(preview[:, :, 0], np.array([[2, 3], [0, 255]], dtype=np.uint8))
    assert np.array_equal(preview[:, :, 1], preview[:, :, 0])


def test_block_preview_rejects_sides_that_are_not_multiples() -> None:
    with pytest.raises(ValueError, match="multiple of 4"):
        report.block_preview(np.zeros((6, 8, 3), dtype=np.uint8), 4)
    with pytest.raises(ValueError, match="factor"):
        report.block_preview(np.zeros((4, 4, 3), dtype=np.uint8), 0)


def test_mosaic_fills_row_major_and_pads_the_last_row_with_black() -> None:
    previews = [
        np.full((2, 2, 3), 1, dtype=np.uint8),
        np.full((2, 2, 3), 2, dtype=np.uint8),
        np.full((2, 2, 3), 3, dtype=np.uint8),
    ]
    grid = report.mosaic(previews, columns=2)
    assert grid.dtype == np.uint8
    assert grid.shape == (4, 4, 3)
    assert np.all(grid[0:2, 0:2] == 1)
    assert np.all(grid[0:2, 2:4] == 2)
    assert np.all(grid[2:4, 0:2] == 3)
    assert np.all(grid[2:4, 2:4] == 0)


def test_mosaic_keeps_the_order_of_the_sequence() -> None:
    # Row-major in the given order: the first tile is top left, whatever its value.
    tiles = [np.full((1, 1, 3), v, dtype=np.uint8) for v in (9, 4, 7, 1)]
    grid = report.mosaic(tiles, columns=2)
    assert grid[:, :, 0].tolist() == [[9, 4], [7, 1]]


def test_mosaic_one_row_and_errors() -> None:
    tile = np.full((1, 1, 3), 7, dtype=np.uint8)
    row = report.mosaic([tile, tile], columns=2)
    assert row.shape == (1, 2, 3)
    with pytest.raises(ValueError, match="columns"):
        report.mosaic([tile], columns=0)
    with pytest.raises(ValueError, match="at least one"):
        report.mosaic([], columns=2)
    with pytest.raises(ValueError, match="same shape"):
        report.mosaic([tile, np.zeros((2, 1, 3), dtype=np.uint8)], columns=2)


def test_summary_table_mean_and_sample_sd_per_key() -> None:
    # Values 1, 3, 5: mean 3, squared deviations 4, 0, 4 with sum 8. Divided by n - 1 = 2 that is
    # 4, whose root is 2 exactly. ddof=0 would give sqrt(8 / 3), so this pins ddof=1.
    runs = {"a": _runs({"k": [1.0, 3.0, 5.0], "m": [2.0, 2.0, 2.0]})}
    table = report.summary_table(runs, ["k", "m"])
    assert table == {"a": {"k": {"mean": 3.0, "sd": 2.0}, "m": {"mean": 2.0, "sd": 0.0}}}


def test_summary_table_tabulates_only_the_requested_keys_per_ensemble() -> None:
    runs = {
        "x": _runs({"k": [1.0, 3.0, 5.0], "m": [0.0, 0.0, 0.0]}),
        "y": _runs({"k": [2.0, 2.0, 2.0], "m": [1.0, 3.0, 5.0]}),
    }
    table = report.summary_table(runs, ("m",))
    assert table == {
        "x": {"m": {"mean": 0.0, "sd": 0.0}},
        "y": {"m": {"mean": 3.0, "sd": 2.0}},
    }


def test_format_number_prints_none_as_na() -> None:
    assert report.format_number(None, ".4g") == "n/a"
    assert report.format_number(1.23456, ".4g") == "1.235"
    assert report.format_number(0.5, ".2f") == "0.50"
    assert report.format_number(12.0, ".4g") == "12"


def test_family_test_labels_add_the_comparison_field_only_when_given() -> None:
    named = report.family_test(HIGH, LOW, ["k"], 0.01, labels=("high", "low"))
    assert named["comparison"] == "high vs low"
    plain = report.family_test(HIGH, LOW, ["k"], 0.01)
    assert "comparison" not in plain
    assert {key: value for key, value in named.items() if key != "comparison"} == plain


def _write_jobs(directory: Path, body: str) -> Path:
    """A jobs file in its own new directory, so ``load_jobs_module`` names it apart."""
    directory.mkdir()
    path = directory / "jobs.py"
    path.write_text(body, encoding="utf-8")
    return path


EARLIER_BODY = """
from painterly_analysis.experiment import Job

ENSEMBLES = {
    "base": [Job.make("base", seed, chain="image", size=8) for seed in (0, 1)],
    "other": [Job.make("other", seed, chain="row", size=8) for seed in (2, 3)],
}
JOBS = [job for jobs in ENSEMBLES.values() for job in jobs]
"""


def _jobs(name: str, seeds: tuple[int, ...], **options: object) -> list[Job]:
    return [Job.make(name, seed, **options) for seed in seeds]


def test_check_seed_reuse_accepts_a_declared_identical_reuse(tmp_path: Path) -> None:
    earlier = {"001": _write_jobs(tmp_path / "001-earlier", EARLIER_BODY)}
    ensembles = {
        "mine": _jobs("mine", (0, 1), chain="image", size=8),
        "fresh": _jobs("fresh", (4, 5), chain="image", size=8),
    }
    assert report.check_seed_reuse(ensembles, earlier, {"mine": ("001", "base")}) is None


def test_check_seed_reuse_rejects_an_undeclared_shared_seed(tmp_path: Path) -> None:
    earlier = {"001": _write_jobs(tmp_path / "001-earlier", EARLIER_BODY)}
    ensembles = {"mine": _jobs("mine", (0, 1), chain="image", size=8)}
    with pytest.raises(RuntimeError, match="used by an earlier experiment"):
        report.check_seed_reuse(ensembles, earlier, {})


def test_check_seed_reuse_rejects_a_shared_seed_with_other_options(tmp_path: Path) -> None:
    earlier = {"001": _write_jobs(tmp_path / "001-earlier", EARLIER_BODY)}
    ensembles = {"mine": _jobs("mine", (0, 1), chain="image", size=16)}
    with pytest.raises(RuntimeError, match="with other options"):
        report.check_seed_reuse(ensembles, earlier, {"mine": ("001", "base")})


def test_check_seed_reuse_rejects_a_reuse_whose_seeds_differ_from_its_source(
    tmp_path: Path,
) -> None:
    earlier = {"001": _write_jobs(tmp_path / "001-earlier", EARLIER_BODY)}
    # Seed 7 is not an earlier seed, so only the source comparison can catch this reuse.
    ensembles = {"mine": _jobs("mine", (0, 7), chain="image", size=8)}
    with pytest.raises(RuntimeError, match="seeds or options differ"):
        report.check_seed_reuse(ensembles, earlier, {"mine": ("001", "base")})


def test_check_seed_reuse_rejects_a_reuse_of_a_missing_ensemble(tmp_path: Path) -> None:
    earlier = {"001": _write_jobs(tmp_path / "001-earlier", EARLIER_BODY)}
    ensembles = {"mine": _jobs("mine", (4, 5), chain="image", size=8)}
    with pytest.raises(RuntimeError, match="has no ensemble"):
        report.check_seed_reuse(ensembles, earlier, {"mine": ("001", "absent")})


def test_check_seed_reuse_rejects_seeds_with_two_option_sets_across_experiments(
    tmp_path: Path,
) -> None:
    earlier = {
        "001": _write_jobs(tmp_path / "001-earlier", EARLIER_BODY),
        "002": _write_jobs(
            tmp_path / "002-other",
            EARLIER_BODY.replace('chain="image", size=8', 'chain="image", size=9'),
        ),
    }
    ensembles = {"mine": _jobs("mine", (4, 5), chain="image", size=8)}
    with pytest.raises(RuntimeError, match="two option sets"):
        report.check_seed_reuse(ensembles, earlier, {})
