"""tools/repro_report.py: rebuild EXP-REPRO's REPRO.json and REPRO.md (TQ.2 F9).

Every experiment here is synthetic and lives under tmp_path: a committed side
``tmp_path/experiments/<NNN>-<slug>/`` and an output side ``tmp_path/outputs/<NNN>/``, the two
directories the tool compares. Nothing is measured and no tolerance is involved: a figure is
compared byte for byte, and a results.json leaf by the exact equality of
``tools/compare_results.py``.
"""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

TOOL = Path(__file__).resolve().parents[2] / "tools" / "repro_report.py"

# The experiment every test builds: one committed directory on the committed side, one output
# directory on the other.
NUMBER = "001"
COMMITTED_DIR = "001-2026-01-01-synthetic"
EXPERIMENT_HEADING = "# EXP-REPRO: reproduction of experiments 001"


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("repro_report", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


repro_report = _load_tool()


def _write(path: Path, data: bytes) -> None:
    """Write data to path, creating its parent directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _sides(root: Path) -> tuple[Path, Path]:
    """The committed and the output directory of the synthetic experiment, both created."""
    committed = root / "experiments" / COMMITTED_DIR
    outputs = root / "outputs" / NUMBER
    committed.mkdir(parents=True)
    outputs.mkdir(parents=True)
    return committed, outputs


def _write_json(path: Path, document: object) -> None:
    """Write a results.json document."""
    _write(path, json.dumps(document).encode("utf-8"))


def _run(root: Path) -> Path:
    """Run the tool on root's synthetic tree and return the directory it wrote."""
    out = root / "out"
    status = repro_report.main(
        ["--outputs", str(root / "outputs"), "--out", str(out)],
        experiments_dir=root / "experiments",
    )
    assert status == repro_report.EXIT_OK
    return out


def _report(root: Path) -> dict[str, object]:
    """The parsed REPRO.json the tool wrote."""
    return json.loads((root / "out" / repro_report.REPORT_JSON).read_text(encoding="utf-8"))


def _markdown(root: Path) -> str:
    """REPRO.md as the tool wrote it."""
    return (root / "out" / repro_report.REPORT_MARKDOWN).read_text(encoding="utf-8")


def test_an_identical_figure_is_identical_and_all_identical_is_true(tmp_path: Path) -> None:
    """The whole report of one byte-identical figure: identical, and all_identical true.

    Mutation that fails this test: make ``_files_identical`` return False (the ``cmp`` verdict
    negated), which flips the entry and all_identical to false.
    """
    committed, outputs = _sides(tmp_path)
    _write(committed / "fig_grid.png", b"\x89PNG committed figure")
    _write(outputs / "fig_grid.png", b"\x89PNG committed figure")
    _run(tmp_path)
    assert _report(tmp_path) == {
        "all_identical": True,
        NUMBER: {"fig_grid.png": {"identical": True}},
    }
    markdown = _markdown(tmp_path)
    assert "| 001 | fig_grid.png | true |  |  |  |  |" in markdown
    assert "| all_identical | true |" in markdown
    assert "| files_not_identical | 0 |" in markdown


def test_a_differing_figure_is_not_identical_and_all_identical_is_false(tmp_path: Path) -> None:
    """Two figures of equal length and different bytes are not identical (a byte-wise compare).

    Mutation that fails this test: compare ``stat().st_size`` instead of the bytes, which calls
    these two equal-length figures identical.
    """
    committed, outputs = _sides(tmp_path)
    _write(committed / "fig_grid.png", b"\x89PNG-AAAA")
    _write(outputs / "fig_grid.png", b"\x89PNG-BBBB")
    _run(tmp_path)
    assert _report(tmp_path) == {
        "all_identical": False,
        NUMBER: {"fig_grid.png": {"identical": False}},
    }
    markdown = _markdown(tmp_path)
    assert "| 001 | fig_grid.png | false |  |  |  |  |" in markdown
    assert "| all_identical | false |" in markdown
    assert "| files_not_identical | 1 |" in markdown


def test_results_json_with_one_numeric_difference_carries_the_leaf_report(tmp_path: Path) -> None:
    """A differing results.json stores compare_objects' report, not a summary of it.

    Mutation that fails this test: store the leaf count or a hand-rolled top-level comparison
    instead of ``compare_objects``' whole report (the entry then no longer equals the imported
    report, and n_leaves_differing is 0).
    """
    committed, outputs = _sides(tmp_path)
    committed_document = {"mean": 2.0, "verdict": "pass"}
    new_document = {"mean": 1.5, "verdict": "pass"}
    _write_json(committed / "results.json", committed_document)
    _write_json(outputs / "results.json", new_document)
    _run(tmp_path)
    entry = _report(tmp_path)[NUMBER]["results.json"]
    assert entry["identical"] is False
    assert entry["leaves"] == repro_report.COMPARE_RESULTS.compare_objects(
        committed_document, new_document
    )
    assert entry["leaves"]["n_leaves_differing"] == 1
    assert entry["non_numeric_identical"] is True
    assert "| 001 | results.json | false | false | 2 | 1 | true |" in _markdown(tmp_path)


def test_tied_leaves_are_decided_by_the_first_leaf_in_the_report_order(tmp_path: Path) -> None:
    """Two leaves tie on both differences; the named rule picks the first in the report's order.

    Mutation that fails this test: the tie rule reversed (``>=`` instead of ``>`` in
    ``_largest``), which names /b/mean instead of /a/mean.
    """
    committed, outputs = _sides(tmp_path)
    committed_document = {"a": {"mean": 1.0}, "b": {"mean": -1.0}}
    # Both leaves differ by 0.5, and by 0.5 relative to their own committed magnitude.
    new_document = {"a": {"mean": 1.5}, "b": {"mean": -1.5}}
    _write_json(committed / "results.json", committed_document)
    _write_json(outputs / "results.json", new_document)
    _run(tmp_path)
    leaves = _report(tmp_path)[NUMBER]["results.json"]["leaves"]["leaves"]
    tied = [record["path"] for record in leaves if record["abs_diff"] == 0.5]
    assert tied == ["/a/mean", "/b/mean"]
    markdown = _markdown(tmp_path)
    assert "| 001 | 2 | 0.5 | /a/mean | 0.5 | /a/mean |" in markdown
    assert "/b/mean" not in markdown


def test_a_leaf_present_on_one_side_only_is_never_a_largest_difference(tmp_path: Path) -> None:
    """A one-sided leaf has a null difference, so it is counted but is never a maximum.

    Mutation that fails this test: drop the null guard in ``_largest`` (the record's null
    ``abs_diff`` then reaches ``None > 0.5`` and the run raises TypeError).
    """
    committed, outputs = _sides(tmp_path)
    _write_json(committed / "results.json", {"gone": 2.0, "mean": 1.0})
    _write_json(outputs / "results.json", {"mean": 1.5})
    _run(tmp_path)
    leaves = _report(tmp_path)[NUMBER]["results.json"]["leaves"]["leaves"]
    gone = [record for record in leaves if record["path"] == "/gone"]
    assert gone[0]["kind"] == "number"
    assert gone[0]["abs_diff"] is None
    assert "| 001 | 2 | 0.5 | /mean | 0.5 | /mean |" in _markdown(tmp_path)


def test_a_file_only_one_side_has_is_not_identical(tmp_path: Path) -> None:
    """A committed figure the output tree lacks is reported, and is not identical.

    Mutation that fails this test: skip a name when one side lacks it (``continue`` where
    ``_files_identical`` returns False for a missing file), which drops the row and leaves
    all_identical true.
    """
    committed, outputs = _sides(tmp_path)
    _write(committed / "fig_grid.png", b"\x89PNG committed figure")
    _write(committed / "results.json", b"{}")
    _write(outputs / "results.json", b"{}")
    _run(tmp_path)
    report = _report(tmp_path)
    assert report["all_identical"] is False
    assert report[NUMBER]["fig_grid.png"] == {"identical": False}
    assert "| 001 | fig_grid.png | false |  |  |  |  |" in _markdown(tmp_path)


def test_the_committed_sources_are_not_output_files(tmp_path: Path) -> None:
    """README.md, analyze.py and jobs.py are the experiment's sources, not analyze.py outputs.

    Mutation that fails this test: take the committed names from ``glob("*")`` instead of
    ``results.json`` and ``fig_*.png``, which reports the three source files as not identical.
    """
    committed, outputs = _sides(tmp_path)
    for name in ("README.md", "analyze.py", "jobs.py"):
        _write(committed / name, b"committed source\n")
    _write(committed / "results.json", b"{}")
    _write(outputs / "results.json", b"{}")
    _run(tmp_path)
    assert _report(tmp_path) == {
        "all_identical": True,
        NUMBER: {"results.json": {"identical": True}},
    }
    assert "README.md" not in _markdown(tmp_path)


def test_the_markdown_has_the_committed_layout(tmp_path: Path) -> None:
    """REPRO.md is the title, the two paragraphs and the three tables, in the committed layout.

    Mutation that fails this test: drop the blank line between two blocks (the paragraphs and
    tables then run together), or write the count table's cells without the committed padding.
    """
    committed, outputs = _sides(tmp_path)
    _write(committed / "fig_grid.png", b"\x89PNG committed figure")
    _write(outputs / "fig_grid.png", b"\x89PNG committed figure")
    _write_json(committed / "results.json", {"mean": 2.0, "verdict": "pass"})
    _write_json(outputs / "results.json", {"mean": 1.5, "verdict": "pass"})
    _run(tmp_path)
    expected = (
        EXPERIMENT_HEADING + "\n"
        "\n"
        "Columns: `identical` = `cmp` exit status 0 against `experiments/<NNN>/<file>`;\n"
        "`leaf_report_identical`, `n_leaves`, `n_leaves_differing` "
        "and `non_numeric_identical` = the\n"
        "fields of `tools/compare_results.py`'s report on that `results.json` (present only where\n"
        "`identical` is false).\n"
        "\n"
        "| experiment | file | identical | leaf_report_identical | n_leaves | "
        "n_leaves_differing | non_numeric_identical |\n"
        "|---|---|---|---|---|---|---|\n"
        "| 001 | fig_grid.png | true |  |  |  |  |\n"
        "| 001 | results.json | false | false | 2 | 1 | true |\n"
        "\n"
        "| all_identical | false |\n"
        "|---|---|\n"
        "| files | 2 |\n"
        "| files_identical | 1 |\n"
        "| files_not_identical | 1 |\n"
        "\n"
        "Largest difference among the differing leaves of each `results.json` "
        "(paths are the tool's\n"
        "RFC 6901 JSON Pointers; `abs_diff` and `rel_diff` are defined in "
        "`tools/compare_results.py`).\n"
        "\n"
        "| experiment | n_leaves_differing_number | max_abs_diff | max_abs_diff_path | "
        "max_rel_diff | max_rel_diff_path |\n"
        "|---|---|---|---|---|---|\n"
        "| 001 | 1 | 0.5 | /mean | 0.25 | /mean |\n"
    )
    assert _markdown(tmp_path) == expected
