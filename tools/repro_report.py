#!/usr/bin/env python3
"""Regenerate the EXP-REPRO report: REPRO.json and REPRO.md (TQ.2 F9).

Usage: python tools/repro_report.py --outputs DIR --out DIR

``--outputs DIR`` holds one directory per experiment, ``DIR/<NNN>/``, with the files an
``analyze.py --out-dir`` run writes for that experiment. The committed side is
``experiments/<NNN>-*/`` in this checkout. The tool writes ``REPRO.json`` and ``REPRO.md`` to
``--out DIR``, in the layout of the committed files in ``docs/handoff/repro/``.

What the report says, per experiment and per output file:

- ``identical``: the output file equals the committed file of the same name byte for byte. That is
  what EXP-REPRO did with ``cmp``, and it is why the figures are checked without a tolerance.
- for a ``results.json`` that is not identical, ``leaves`` is the report of
  ``tools/compare_results.py``'s ``compare_objects`` (imported, not copied) on the committed and
  the new document, and ``non_numeric_identical`` repeats that report's verdict on the
  non-numeric leaves.
- ``all_identical``: every file of every experiment is identical.

The compared file set of an experiment is the union of the names in its output directory and the
committed names matching ``results.json`` or ``fig_*.png``: those are the files an
``analyze.py --out-dir`` run writes, so the committed ``README.md``, ``analyze.py`` and
``jobs.py`` are not output files. A name that only one side has is reported, and is not identical.
Every subdirectory of ``--outputs`` must be named ``<NNN>``, and must have exactly one committed
``experiments/<NNN>-*/`` directory.

Ties for the largest difference (the rule TQ.2 F9 asks for). Several differing leaves can share
the largest ``abs_diff`` or ``rel_diff``. The rule is: the first of the tied leaves in the
report's own leaf order, which ``compare_objects`` emits as sorted path order (mapping keys sorted
as strings, sequence indices ascending). In each of the three committed ties below, that leaf is
also the one with the smallest RFC 6901 JSON Pointer among the tied ones. A leaf whose difference
is null (present on one side only) is never a maximum, and neither is a NaN difference, which
compares false. The rule reproduces all three committed choices:

- 002 ``max_abs_diff``: ``/effect_size_table/u2_independent/all.spectral_slope``, the first of two
  (the other is ``/effect_summary/u2_independent/all.spectral_slope/cohen_d``);
- 003 ``max_rel_diff``: ``/h3/test/effect_summary/all.spectral_slope/rel_diff``, the first of two
  (the other is ``/h3/test/largest_abs_rel_diff/value``);
- 006 ``max_abs_diff``:
  ``/jitter_footprint/comparisons/800/effect_summary/r6.structure_std/cohen_d``, the first of
  three (the others are ``/jitter_footprint/comparisons/800/largest_abs_cohen_d/value`` and
  ``/jitter_footprint/comparisons/800/largest_abs_cohen_d_texture/value``).

REPRO.md's largest-difference table has one row per experiment: an experiment whose
``results.json`` is identical, or which has none, has 0 differing number leaves and empty maximum
cells.
"""

import argparse
import importlib.util
import json
import math
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import cast

# The checkout this tool lives in: the committed side is read from <root>/experiments.
REPO_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = REPO_ROOT / "experiments"
# tools/compare_results.py, next to this file. Its compare_objects builds the leaf report.
COMPARE_RESULTS_PATH = Path(__file__).resolve().parent / "compare_results.py"

# An experiment's number: the committed directory is experiments/<NNN>-<slug>/, and --outputs holds
# one <NNN>/ per experiment.
EXPERIMENT_NUMBER = re.compile(r"^\d{3}$")
# The files an `analyze.py --out-dir` run writes: one results.json, and the figures.
RESULTS_NAME = "results.json"
FIGURE_GLOB = "fig_*.png"
OUTPUT_PATTERNS = (RESULTS_NAME, FIGURE_GLOB)

# The report's top-level verdict, first key of REPRO.json and the second table of REPRO.md.
ALL_IDENTICAL = "all_identical"

# Names of the two files written to --out.
REPORT_JSON = "REPRO.json"
REPORT_MARKDOWN = "REPRO.md"

# Indent of REPRO.json: the committed file's layout, one field per line so a diff is readable.
JSON_INDENT = 2
# The report is written with LF on every platform, because the committed files are compared byte
# for byte (`cmp`).
NEWLINE = "\n"

# REPRO.md's fixed prose, in the committed file's layout. The title is generated from the
# experiment numbers, because it names them.
COLUMNS_PARAGRAPH = NEWLINE.join(
    (
        "Columns: `identical` = `cmp` exit status 0 against `experiments/<NNN>/<file>`;",
        "`leaf_report_identical`, `n_leaves`, `n_leaves_differing` "
        "and `non_numeric_identical` = the",
        "fields of `tools/compare_results.py`'s report on that `results.json` (present only where",
        "`identical` is false).",
    )
)
LARGEST_PARAGRAPH = NEWLINE.join(
    (
        "Largest difference among the differing leaves of each `results.json` "
        "(paths are the tool's",
        "RFC 6901 JSON Pointers; `abs_diff` and `rel_diff` are defined in "
        "`tools/compare_results.py`).",
    )
)
# The three tables' header rows and separators, as the committed file writes them.
FILE_TABLE_HEADER = (
    "| experiment | file | identical | leaf_report_identical | n_leaves | "
    "n_leaves_differing | non_numeric_identical |"
)
FILE_TABLE_SEPARATOR = "|" + "---|" * 7
COUNT_TABLE_SEPARATOR = "|" + "---|" * 2
LARGEST_TABLE_HEADER = (
    "| experiment | n_leaves_differing_number | max_abs_diff | max_abs_diff_path | "
    "max_rel_diff | max_rel_diff_path |"
)
LARGEST_TABLE_SEPARATOR = "|" + "---|" * 6

# The report's shape: {ALL_IDENTICAL: bool, "<NNN>": {<file name>: FileEntry}}.
FileEntry = dict[str, object]

# main()'s exit statuses: EXIT_USAGE is the status argparse itself exits with on a usage error.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2


class ReproReportError(Exception):
    """A report cannot be built from these inputs: a missing directory, or a nameless experiment."""


def _load_compare_results(path: Path = COMPARE_RESULTS_PATH) -> ModuleType:
    """Import tools/compare_results.py by path and return the module.

    The leaf report is that module's ``compare_objects``, imported rather than copied (TQ.2 F9).
    ``tools/`` is not a package, so the file is loaded by path, as its own tests load it.
    """
    spec = importlib.util.spec_from_file_location("compare_results", path)
    if spec is None or spec.loader is None:
        raise ReproReportError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


COMPARE_RESULTS = _load_compare_results()


def build_report(outputs_dir: Path, experiments_dir: Path) -> dict[str, object]:
    """Build the report dict for every experiment under outputs_dir.

    ``outputs_dir`` holds one ``<NNN>/`` directory per experiment, with that experiment's
    ``analyze.py --out-dir`` files; ``experiments_dir`` holds the committed
    ``<NNN>-<slug>/`` directories. The result is REPRO.json's content: ``all_identical`` first,
    then one entry per experiment in ascending number order, each with one entry per file name in
    ascending name order. See the module docstring for what each entry holds.
    """
    report: dict[str, object] = {}
    all_identical = True
    for number in _experiment_numbers(outputs_dir):
        committed_dir = _committed_dir(experiments_dir, number)
        output_dir = outputs_dir / number
        files: dict[str, FileEntry] = {}
        for name in _output_names(committed_dir, output_dir):
            identical = _files_identical(committed_dir / name, output_dir / name)
            entry: FileEntry = {"identical": identical}
            if name == RESULTS_NAME and not identical:
                leaves = _leaves_report(committed_dir / name, output_dir / name)
                if leaves is not None:
                    entry["leaves"] = leaves
                    entry["non_numeric_identical"] = leaves["non_numeric_identical"]
            files[name] = entry
            all_identical = all_identical and identical
        report[number] = files
    return {ALL_IDENTICAL: all_identical, **report}


def render_markdown(report: Mapping[str, object]) -> str:
    """Render REPRO.md from a report built by build_report, in the committed file's layout.

    The document is a title, the two prose paragraphs and the three tables, separated by one blank
    line, with a single LF after the last table row.
    """
    numbers = [key for key in report if key != ALL_IDENTICAL]
    blocks = (
        _title(numbers),
        COLUMNS_PARAGRAPH,
        _file_table(report, numbers),
        _count_table(report, numbers),
        LARGEST_PARAGRAPH,
        _largest_table(report, numbers),
    )
    return NEWLINE.join(block + NEWLINE for block in blocks)


def write_report(report: Mapping[str, object], out_dir: Path) -> None:
    """Write REPRO.json and REPRO.md into out_dir, creating it (and its parents) if needed.

    Both files are UTF-8 with LF line endings, so they can be compared with the committed files
    byte for byte.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / REPORT_JSON).write_text(
        json.dumps(report, indent=JSON_INDENT) + NEWLINE, encoding="utf-8", newline=NEWLINE
    )
    (out_dir / REPORT_MARKDOWN).write_text(
        render_markdown(report), encoding="utf-8", newline=NEWLINE
    )


def build_parser() -> argparse.ArgumentParser:
    """The CLI parser: --outputs (the per-experiment output tree), then --out (the report's dir)."""
    parser = argparse.ArgumentParser(
        prog="repro_report.py",
        description="Build REPRO.json and REPRO.md from a per-experiment output tree.",
    )
    parser.add_argument(
        "--outputs",
        type=Path,
        required=True,
        help="directory with one <NNN>/ subdirectory per experiment",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="directory to write REPRO.json and REPRO.md to",
    )
    return parser


def main(argv: Sequence[str] | None = None, experiments_dir: Path = EXPERIMENTS_DIR) -> int:
    """Run the CLI and return its exit status; argv defaults to sys.argv[1:].

    ``experiments_dir`` is the committed side and defaults to this checkout's experiments/. A
    difference is data, not an error: the status is EXIT_OK whenever both files were written. The
    status is EXIT_ERROR when a directory is missing, a results.json cannot be read, or a file
    cannot be written, with a message on stderr.
    """
    args = build_parser().parse_args(argv)
    try:
        report = build_report(args.outputs, experiments_dir)
        write_report(report, args.out)
    except (ReproReportError, OSError, json.JSONDecodeError) as error:
        print(f"repro_report.py: {error}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK


def _experiment_numbers(outputs_dir: Path) -> list[str]:
    """The experiment numbers under outputs_dir, ascending; every subdirectory must be one."""
    if not outputs_dir.is_dir():
        raise ReproReportError(f"not a directory: {outputs_dir}")
    numbers: list[str] = []
    for path in sorted(outputs_dir.iterdir()):
        if not path.is_dir():
            raise ReproReportError(f"not a directory of an experiment: {path}")
        if not EXPERIMENT_NUMBER.fullmatch(path.name):
            raise ReproReportError(f"not an experiment number: {path}")
        numbers.append(path.name)
    if not numbers:
        raise ReproReportError(f"no experiment directories in {outputs_dir}")
    return numbers


def _committed_dir(experiments_dir: Path, number: str) -> Path:
    """The one committed directory experiments/<NNN>-<slug>/ for an experiment number."""
    matches = sorted(path for path in experiments_dir.glob(f"{number}-*") if path.is_dir())
    if len(matches) != 1:
        raise ReproReportError(
            f"expected one committed directory {experiments_dir}/{number}-*, found {len(matches)}"
        )
    return matches[0]


def _output_names(committed_dir: Path, output_dir: Path) -> list[str]:
    """The names of the files to compare, ascending: the output files on either side.

    That is every name in the output directory, plus the committed names an ``analyze.py
    --out-dir`` run writes (``results.json`` and ``fig_*.png``). The committed directory's own
    sources (README.md, analyze.py, jobs.py) are not output files and are not compared.
    """
    names = {path.name for path in output_dir.iterdir() if path.is_file()}
    for pattern in OUTPUT_PATTERNS:
        names.update(path.name for path in committed_dir.glob(pattern) if path.is_file())
    return sorted(names)


def _files_identical(committed: Path, output: Path) -> bool:
    """True when both files exist and hold the same bytes (EXP-REPRO's `cmp`)."""
    if not committed.is_file() or not output.is_file():
        return False
    return committed.read_bytes() == output.read_bytes()


def _leaves_report(committed: Path, output: Path) -> dict[str, object] | None:
    """compare_objects on the two results.json documents, or None when one side has no file.

    A file that exists but cannot be parsed raises, and main() reports it: a report cannot be
    built from a document that is not JSON.
    """
    if not committed.is_file() or not output.is_file():
        return None
    return COMPARE_RESULTS.compare_objects(
        COMPARE_RESULTS.load_results(committed), COMPARE_RESULTS.load_results(output)
    )


def _experiment_files(
    report: Mapping[str, object], number: str
) -> Mapping[str, Mapping[str, object]]:
    """The file entries of one experiment in a report built by build_report."""
    return cast(Mapping[str, Mapping[str, object]], report[number])


def _title(numbers: Sequence[str]) -> str:
    """REPRO.md's title line, which names the experiments it covers."""
    return f"# EXP-REPRO: reproduction of experiments {_and_list(numbers)}"


def _and_list(items: Sequence[str]) -> str:
    """The items as an English list: "a, b and c"; one item is itself, and none is empty."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def _row(cells: Sequence[str]) -> str:
    """One Markdown table row. An empty cell keeps its padding, as the committed file writes it."""
    return "| " + " | ".join(cells) + " |"


def _boolean(value: object) -> str:
    """A JSON verdict as the committed tables write it: ``true`` or ``false``."""
    return "true" if value else "false"


def _number(value: object) -> str:
    """A JSON number as the committed tables write it: the shortest round-trip literal."""
    return repr(value)


def _file_table(report: Mapping[str, object], numbers: Sequence[str]) -> str:
    """The first table: one row per file, with the leaf report's fields where it has one."""
    rows = [FILE_TABLE_HEADER, FILE_TABLE_SEPARATOR]
    for number in numbers:
        for name, entry in _experiment_files(report, number).items():
            leaves = entry.get("leaves")
            cells = [number, name, _boolean(entry["identical"])]
            if isinstance(leaves, Mapping):
                cells += [
                    _boolean(leaves["identical"]),
                    _number(leaves["n_leaves"]),
                    _number(leaves["n_leaves_differing"]),
                    _boolean(leaves["non_numeric_identical"]),
                ]
            else:
                cells += ["", "", "", ""]
            rows.append(_row(cells))
    return NEWLINE.join(rows)


def _count_table(report: Mapping[str, object], numbers: Sequence[str]) -> str:
    """The verdict table: all_identical and the file counts."""
    files = [entry for number in numbers for entry in _experiment_files(report, number).values()]
    identical = sum(1 for entry in files if entry["identical"])
    rows = [
        _row([ALL_IDENTICAL, _boolean(report[ALL_IDENTICAL])]),
        COUNT_TABLE_SEPARATOR,
        _row(["files", _number(len(files))]),
        _row(["files_identical", _number(identical)]),
        _row(["files_not_identical", _number(len(files) - identical)]),
    ]
    return NEWLINE.join(rows)


def _largest_table(report: Mapping[str, object], numbers: Sequence[str]) -> str:
    """The largest-difference table: one row per experiment, maxima by the module's tie rule."""
    rows = [LARGEST_TABLE_HEADER, LARGEST_TABLE_SEPARATOR]
    for number in numbers:
        entry = _experiment_files(report, number).get(RESULTS_NAME)
        leaves = entry.get("leaves") if entry is not None else None
        records = [] if not isinstance(leaves, Mapping) else _differing_numbers(leaves["leaves"])
        largest_abs = _largest(records, "abs_diff")
        largest_rel = _largest(records, "rel_diff")
        cells = [number, _number(len(records))]
        for largest in (largest_abs, largest_rel):
            if largest is None:
                cells += ["", ""]
            else:
                value, path = largest
                cells += [_number(value), path]
        rows.append(_row(cells))
    return NEWLINE.join(rows)


def _differing_numbers(leaves: object) -> list[Mapping[str, object]]:
    """The report's number leaves that are not identical, in the report's own order."""
    records = cast(Sequence[Mapping[str, object]], leaves)
    return [
        record
        for record in records
        if record["kind"] == COMPARE_RESULTS.NUMBER_KIND and not record["identical"]
    ]


def _is_finite_number(value: object) -> bool:
    """True for a JSON number that can be a maximum: not null, and not NaN.

    A leaf present on one side only has a null difference, and a NaN difference compares false
    against everything, so neither can be the largest.
    """
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return not math.isnan(value)


def _largest(records: Sequence[Mapping[str, object]], field: str) -> tuple[object, str] | None:
    """The largest non-null value of field among records, with its path, or None.

    Ties go to the first record in the report's order (the module docstring's rule): the scan
    replaces the best value only on a strict increase, so an equal value keeps the earlier leaf. A
    NaN difference is never the maximum, because NaN compares false.
    """
    largest: tuple[object, str] | None = None
    for record in records:
        value = record[field]
        if not _is_finite_number(value):
            continue
        if largest is None or value > largest[0]:
            largest = (value, cast(str, record["path"]))
    return largest


if __name__ == "__main__":
    sys.exit(main())
