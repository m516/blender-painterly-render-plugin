"""tools/compare_results.py: the leaf-by-leaf report of two results.json documents (EXP-REPRO).

The documents here are hand-written and small. They exercise the report's shape, its numeric
differences and its handling of a leaf that only one document has; no tolerance is involved,
because the comparison is exact equality of the parsed values.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

TOOL = Path(__file__).resolve().parents[2] / "tools" / "compare_results.py"

# The record of a numeric leaf: the fields of every record, plus the two differences.
COMMON_FIELDS = (
    "path",
    "kind",
    "identical",
    "committed_present",
    "new_present",
    "committed",
    "new",
)
NUMBER_FIELDS = (*COMMON_FIELDS, "abs_diff", "rel_diff")

COMMITTED = {
    "experiment": "001-2026-10-08-oracle-reproduction",
    "alpha": 0.01,
    "pairs": 8,
    "smoke": False,
    "rejected_keys": ["a", "b"],
    "verdict": {"h1": "pass"},
    "series": [1.0, 2.0],
    "null_leaf": None,
}


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("compare_results", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


compare_results = _load_tool()


def _records(report: dict, path: str) -> list[dict]:
    return [record for record in report["leaves"] if record["path"] == path]


def _record(report: dict, path: str) -> dict:
    found = _records(report, path)
    assert len(found) == 1, f"expected exactly one leaf at {path}, found {found}"
    return found[0]


def test_identical_documents_report_no_differing_leaf() -> None:
    report = compare_results.compare_objects(COMMITTED, json.loads(json.dumps(COMMITTED)))
    assert report["identical"] is True
    assert report["n_leaves_differing"] == 0
    assert report["n_leaves"] == len(report["leaves"])
    assert all(record["identical"] for record in report["leaves"])


def test_non_numeric_identical_is_the_verdict_restricted_to_other_leaves() -> None:
    """A numeric-only difference leaves non_numeric_identical true; a verdict change clears it."""
    numeric_only = compare_results.compare_objects({"mean": 1.0}, {"mean": 2.0})
    assert numeric_only["identical"] is False
    assert numeric_only["non_numeric_identical"] is True
    verdict_changed = compare_results.compare_objects({"verdict": "pass"}, {"verdict": "fail"})
    assert verdict_changed["identical"] is False
    assert verdict_changed["non_numeric_identical"] is False


def test_every_leaf_gets_one_record_with_the_common_fields() -> None:
    report = compare_results.compare_objects(COMMITTED, COMMITTED)
    paths = [record["path"] for record in report["leaves"]]
    assert len(paths) == len(set(paths))
    for record in report["leaves"]:
        fields = NUMBER_FIELDS if record["kind"] == "number" else COMMON_FIELDS
        assert tuple(record) == fields
        assert record["committed_present"] is True
        assert record["new_present"] is True


def test_differing_numeric_leaf_reports_both_differences() -> None:
    committed = {"block_rmse": 2.0}
    new = {"block_rmse": 1.5}
    report = compare_results.compare_objects(committed, new)
    assert report["identical"] is False
    assert report["n_leaves_differing"] == 1
    record = _record(report, "/block_rmse")
    assert record["kind"] == "number"
    assert record["identical"] is False
    assert record["committed"] == 2.0
    assert record["new"] == 1.5
    # 2.0 - 1.5 and 0.5 / 2.0 are exact in binary floating point.
    assert record["abs_diff"] == 0.5
    assert record["rel_diff"] == 0.25


def test_relative_difference_divides_by_the_committed_magnitude() -> None:
    """The denominator is |committed|, so a negative committed value reports a positive ratio."""
    report = compare_results.compare_objects({"mean": -2.0}, {"mean": -1.5})
    record = _record(report, "/mean")
    assert record["abs_diff"] == 0.5
    assert record["rel_diff"] == 0.25


def test_zero_committed_value_has_no_finite_relative_difference() -> None:
    """0.0 against a non-zero new value: the absolute difference is reported, the ratio is null."""
    report = compare_results.compare_objects({"clip_fraction": 0.0}, {"clip_fraction": 0.5})
    record = _record(report, "/clip_fraction")
    assert record["abs_diff"] == 0.5
    assert record["rel_diff"] is None


def test_zero_against_zero_is_identical_with_zero_differences() -> None:
    report = compare_results.compare_objects({"clip_fraction": 0.0}, {"clip_fraction": 0.0})
    record = _record(report, "/clip_fraction")
    assert record["identical"] is True
    assert record["abs_diff"] == 0
    assert record["rel_diff"] == 0.0


def test_equal_infinities_are_identical() -> None:
    """A JSON document may hold Infinity; equal infinities differ by no finite number."""
    report = compare_results.compare_objects({"hi": float("inf")}, {"hi": float("inf")})
    record = _record(report, "/hi")
    assert record["identical"] is True
    assert record["abs_diff"] == 0
    assert record["rel_diff"] == 0.0


def test_differing_string_leaf_has_no_numeric_fields() -> None:
    committed = {"verdict": {"h1": "pass"}}
    new = {"verdict": {"h1": "fail"}}
    report = compare_results.compare_objects(committed, new)
    assert report["identical"] is False
    record = _record(report, "/verdict/h1")
    assert record["kind"] == "other"
    assert record["identical"] is False
    assert record["committed"] == "pass"
    assert record["new"] == "fail"
    assert "abs_diff" not in record
    assert "rel_diff" not in record


def test_differing_rejected_key_list_has_no_numeric_fields() -> None:
    committed = {"rejected_keys": ["a", "b"]}
    new = {"rejected_keys": ["a", "b", "c"]}
    report = compare_results.compare_objects(committed, new)
    record = _record(report, "/rejected_keys/2")
    assert record["kind"] == "other"
    assert record["identical"] is False
    assert record["committed"] is None
    assert record["new"] == "c"
    assert record["committed_present"] is False
    assert record["new_present"] is True


def test_boolean_leaf_is_not_a_number() -> None:
    report = compare_results.compare_objects({"smoke": False}, {"smoke": True})
    record = _record(report, "/smoke")
    assert record["kind"] == "other"
    assert record["identical"] is False
    assert "abs_diff" not in record


def test_integer_and_float_with_the_same_value_are_identical() -> None:
    report = compare_results.compare_objects({"size": 400}, {"size": 400.0})
    record = _record(report, "/size")
    assert record["kind"] == "number"
    assert record["identical"] is True
    assert record["abs_diff"] == 0
    assert record["rel_diff"] == 0.0


def test_true_against_one_is_not_identical() -> None:
    """TQ.2 F5: a boolean is not a number, so Python's True == 1 must not count as identical."""
    report = compare_results.compare_objects({"smoke": True}, {"smoke": 1})
    assert report["identical"] is False
    assert report["n_leaves_differing"] == 1
    record = _record(report, "/smoke")
    assert record["identical"] is False
    assert record["committed"] is True
    assert record["new"] == 1


def test_false_against_zero_is_not_identical() -> None:
    """TQ.2 F5: False == 0 in Python, and the two leaves are still a boolean against a number."""
    report = compare_results.compare_objects({"smoke": False}, {"smoke": 0})
    assert report["identical"] is False
    record = _record(report, "/smoke")
    assert record["identical"] is False
    assert record["committed"] is False
    assert record["new"] == 0


@pytest.mark.parametrize(("committed", "new"), [(1, 1.0), (1.0, 1)])
def test_integer_and_float_leaves_of_equal_value_are_identical(committed: float, new: int) -> None:
    """1 and 1.0 match: both are JSON numbers (RFC 8259 §6), with one value and one difference.

    This is the module's choice for ``1`` against ``1.0`` (TQ.2 F5). The type-aware comparison that
    separates a boolean from a number must not separate an integer from a float, because JSON has
    one number type and the literal's fraction is not part of it: both leaves have the module's
    number type, so they stay identical and their record keeps the two numeric differences.
    """
    assert compare_results._json_type(committed) == compare_results.NUMBER_TYPE
    assert compare_results._json_type(new) == compare_results.NUMBER_TYPE
    report = compare_results.compare_objects({"passes": committed}, {"passes": new})
    assert report["identical"] is True
    assert report["non_numeric_identical"] is True
    record = _record(report, "/passes")
    assert record["kind"] == "number"
    assert record["identical"] is True
    assert record["abs_diff"] == 0
    assert record["rel_diff"] == 0.0


def test_key_present_in_only_one_file() -> None:
    committed = {"pairs": 8, "committed_only": 3.0}
    new = {"pairs": 8, "new_only": 4.0}
    report = compare_results.compare_objects(committed, new)
    assert report["identical"] is False
    assert report["n_leaves_differing"] == 2
    gone = _record(report, "/committed_only")
    assert gone["committed_present"] is True
    assert gone["new_present"] is False
    assert gone["identical"] is False
    assert gone["committed"] == 3.0
    assert gone["new"] is None
    assert gone["abs_diff"] is None
    assert gone["rel_diff"] is None
    added = _record(report, "/new_only")
    assert added["committed_present"] is False
    assert added["new_present"] is True
    assert added["committed"] is None
    assert added["new"] == 4.0
    assert added["abs_diff"] is None
    assert added["rel_diff"] is None


def test_container_present_in_only_one_file_is_one_leaf() -> None:
    """A leaf the other document lacks is reported at its own path, not as its whole subtree."""
    committed = {"grid": {"layout": [[0, 1], [2, 3]]}}
    new = {"grid": {}}
    report = compare_results.compare_objects(committed, new)
    assert [record["path"] for record in report["leaves"]] == ["/grid/layout"]
    record = _record(report, "/grid/layout")
    assert record["kind"] == "other"
    assert record["identical"] is False


def test_mapping_against_scalar_is_one_leaf() -> None:
    report = compare_results.compare_objects({"h2": {"lstar": None}}, {"h2": 0.5})
    assert [record["path"] for record in report["leaves"]] == ["/h2"]
    record = _record(report, "/h2")
    assert record["kind"] == "other"
    assert record["identical"] is False


def test_null_leaf_against_null_leaf_is_identical() -> None:
    report = compare_results.compare_objects({"lstar": None}, {"lstar": None})
    record = _record(report, "/lstar")
    assert record["kind"] == "other"
    assert record["identical"] is True


def test_sequence_shorter_than_the_committed_one() -> None:
    report = compare_results.compare_objects({"series": [1.0, 2.0]}, {"series": [1.0]})
    assert [record["path"] for record in report["leaves"]] == ["/series/0", "/series/1"]
    assert _record(report, "/series/1")["new_present"] is False
    assert report["identical"] is False


def test_paths_are_json_pointers_escaping_tilde_and_slash() -> None:
    report = compare_results.compare_objects({"a/b": {"c~d": 1.0}}, {"a/b": {"c~d": 2.0}})
    assert [record["path"] for record in report["leaves"]] == ["/a~1b/c~0d"]


def test_records_are_sorted_by_path() -> None:
    committed = {"b": 1, "a": {"d": 1, "c": 1}, "list": [1, 2]}
    report = compare_results.compare_objects(committed, committed)
    assert [record["path"] for record in report["leaves"]] == [
        "/a/c",
        "/a/d",
        "/b",
        "/list/0",
        "/list/1",
    ]


def test_leaf_records_are_json_serializable() -> None:
    report = compare_results.compare_objects(COMMITTED, COMMITTED)
    assert json.loads(json.dumps(report)) == report


def test_cli_prints_the_report_and_exits_zero(tmp_path: Path) -> None:
    committed_path = tmp_path / "committed.json"
    new_path = tmp_path / "new.json"
    committed_path.write_text(json.dumps(COMMITTED), encoding="utf-8")
    new_path.write_text(json.dumps({"pairs": 9}), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(TOOL), str(committed_path), str(new_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["identical"] is False
    assert _record(report, "/pairs")["abs_diff"] == 1


def test_main_takes_argv_and_prints_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    committed_path = tmp_path / "committed.json"
    new_path = tmp_path / "new.json"
    committed_path.write_text(json.dumps(COMMITTED), encoding="utf-8")
    new_path.write_text(json.dumps({"pairs": 9}), encoding="utf-8")
    assert compare_results.main([str(committed_path), str(new_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["identical"] is False
    assert _record(report, "/pairs")["rel_diff"] == 0.125


def test_cli_exits_zero_on_identical_files(tmp_path: Path) -> None:
    committed_path = tmp_path / "committed.json"
    new_path = tmp_path / "new.json"
    text = json.dumps(COMMITTED)
    committed_path.write_text(text, encoding="utf-8")
    new_path.write_text(text, encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(TOOL), str(committed_path), str(new_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["identical"] is True


def test_cli_reports_an_unreadable_file_on_stderr(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    completed = subprocess.run(
        [sys.executable, str(TOOL), str(missing), str(missing)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert completed.stdout == ""
    assert str(missing) in completed.stderr


def test_cli_requires_two_paths() -> None:
    completed = subprocess.run(
        [sys.executable, str(TOOL), "only-one.json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stdout == ""


@pytest.mark.parametrize("empty", [{}, []])
def test_empty_documents_are_identical(empty: object) -> None:
    report = compare_results.compare_objects(empty, empty)
    assert report["identical"] is True
    assert report["leaves"] == []


def test_the_report_does_not_touch_its_inputs() -> None:
    committed = {"verdict": {"h1": "pass"}}
    new = {"verdict": {"h1": "fail"}}
    compare_results.compare_objects(committed, new)
    assert committed == {"verdict": {"h1": "pass"}}
    assert new == {"verdict": {"h1": "fail"}}
