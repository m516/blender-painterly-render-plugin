#!/usr/bin/env python3
"""Compare two parsed results.json documents leaf by leaf (EXP-REPRO).

Usage: python tools/compare_results.py COMMITTED.json NEW.json

The report is a JSON object on stdout:

    {"identical": bool, "non_numeric_identical": bool, "n_leaves": int,
     "n_leaves_differing": int, "leaves": [record, ...]}

One record per leaf of the pair:

- ``path``: the leaf's location as an RFC 6901 JSON Pointer, with ``~`` escaped as ``~0`` and ``/``
  as ``~1``. The document root is ``""``.
- ``kind``: ``"number"`` when every side that has the leaf holds a JSON number, else ``"other"``
  (verdicts, rejected-key lists, strings, booleans, nulls, and containers the two documents
  disagree about).
- ``identical``: the parsed values are exactly equal, both documents have the leaf, and both sides
  have the same JSON type.
- ``committed_present`` / ``new_present``: whether that document has the leaf.
- ``committed`` / ``new``: the parsed values; ``null`` where that document has no leaf.
- ``abs_diff`` and ``rel_diff``: number leaves only, and absent from an ``"other"`` record.
  ``abs_diff`` is ``abs(new - committed)``. ``rel_diff`` is ``abs_diff / abs(committed)``: the
  denominator is the magnitude of the committed value, so it is never negative. When the committed
  value is 0 the relative difference has no finite value, and then ``rel_diff`` is ``0.0`` if
  ``new`` is also 0 (the values are equal) and ``null`` otherwise. A leaf that only one document
  has has both differences ``null``.

``identical`` is true only when every leaf is identical. ``non_numeric_identical`` is true only when
every non-numeric (``"other"``) leaf is identical: the second half of EXP-REPRO reports it per
experiment beside the ``cmp`` verdict.

Conventions:

- A leaf is identical only when both documents hold it, the two JSON values have the same type, and
  the values are equal. The types are JSON's six (RFC 8259 §3): object, array, number, string,
  boolean and null, and they are all distinct: ``true`` against ``1`` and ``false`` against ``0``
  are differences, not matches, and a type change in a results file is visible to EXP-REPRO even
  where the value would compare equal in Python.
- ``1`` and ``1.0`` are identical, and the reason is that both are JSON numbers: JSON (RFC 8259
  §6) gives a number one type and its grammar does not record whether the literal carried a
  fraction, so ``json`` parses ``1`` as an ``int`` and ``1.0`` as a ``float`` without that being a
  type change in the document. Both sides then have the same type and the same value, so the leaf
  is identical and reports ``abs_diff`` 0 and ``rel_diff`` 0.0. A boolean, a string and null are
  each distinct from a number and from each other, so none of them matches ``1`` or ``0``.
- Numbers are compared with ``==`` on the parsed values, and a ``NaN`` (which ``json`` accepts) is
  not identical to itself. Exactly equal values report ``abs_diff`` 0 and ``rel_diff`` 0.0,
  including equal infinities, whose difference would be NaN. A ``NaN`` leaf against a different
  value reports a ``NaN`` difference, since that is the arithmetic difference; ``json.dumps``
  writes it as the non-standard literal ``NaN``.
- A leaf that only one document has is one record at its own path; its subtree is not walked.
- Two containers of the same kind (two mappings, or two sequences) are walked together; a mapping
  against a scalar, or a sequence against a mapping, is one leaf.
- Records come out in sorted path order: mapping keys sorted as strings, sequence indices ascending.
- Exit status is 0 whenever the report was printed - a difference is data, not an error - 1 when a
  file cannot be read or parsed, and 2 on a usage error (argparse's own status). Read the
  ``identical`` field for the verdict.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

# A leaf whose every present side is a JSON number.
NUMBER_KIND = "number"
# A leaf that holds anything else, or that the two documents disagree about.
OTHER_KIND = "other"

# The JSON types a leaf can hold, as json parses them. They are all distinct, so a leaf is identical
# only when both sides have the same one: Python's own == would call True == 1 and False == 0, which
# is why the comparison cannot be a bare ==. An int and a float are both JSON numbers (RFC 8259 §6:
# a number is one type, and the literal's fraction is not part of it), so they share NUMBER_TYPE.
BOOLEAN_TYPE = "boolean"
STRING_TYPE = "string"
NULL_TYPE = "null"
NUMBER_TYPE = "number"
# The two container types. They reach a leaf only where the two documents disagree about the
# container (a mapping against a scalar, a sequence against a mapping), which is one leaf of kind
# "other" by the module docstring; they are distinct from the scalar types and from each other.
OBJECT_TYPE = "object"
ARRAY_TYPE = "array"

# Leaf paths are RFC 6901 JSON Pointers (RFC 6901 §3, §5): "" is the root, "/" separates reference
# tokens, and a token escapes "~" as "~0" and "/" as "~1" so a key can hold either character.
POINTER_ROOT = ""
POINTER_SEPARATOR = "/"
POINTER_TILDE = "~"
POINTER_ESCAPE_TILDE = "~0"
POINTER_ESCAPE_SLASH = "~1"

# Indent of the printed report: readable, and still one line per field for a diff.
REPORT_INDENT = 2

# main()'s exit statuses (the module docstring states when each one is returned). EXIT_USAGE is the
# status argparse itself exits with on a usage error.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2


def load_results(path: str | Path) -> object:
    """Parse the JSON document of a results.json file and return it.

    Units and conventions are the file's own; the document is returned as plain dicts, lists,
    numbers, strings, booleans and nulls.
    """
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def compare_objects(committed: object, new: object) -> dict[str, object]:
    """Walk two parsed results.json documents and return the leaf-by-leaf report.

    The report's shape and the difference conventions are in the module docstring. ``identical`` is
    true only when every leaf is identical, which includes the two leaf sets being equal: a leaf
    that only one document has is never identical. ``non_numeric_identical`` is the same verdict
    restricted to the ``"other"`` leaves.
    """
    leaves: list[dict[str, object]] = []
    _walk(committed, new, POINTER_ROOT, leaves)
    differing = sum(1 for leaf in leaves if not leaf["identical"])
    other_differing = sum(
        1 for leaf in leaves if leaf["kind"] == OTHER_KIND and not leaf["identical"]
    )
    return {
        "identical": differing == 0,
        "non_numeric_identical": other_differing == 0,
        "n_leaves": len(leaves),
        "n_leaves_differing": differing,
        "leaves": leaves,
    }


def build_parser() -> argparse.ArgumentParser:
    """The CLI parser: COMMITTED.json, then NEW.json."""
    parser = argparse.ArgumentParser(
        prog="compare_results.py",
        description="Compare two results.json files leaf by leaf and print the report as JSON.",
    )
    parser.add_argument("committed", type=Path, help="the committed results.json")
    parser.add_argument("new", type=Path, help="the new results.json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return its exit status; argv defaults to sys.argv[1:].

    The report goes to stdout as JSON. A difference is data, not an error: the status is EXIT_OK
    whenever the report was printed, and the verdict is the report's ``identical`` field.
    """
    args = build_parser().parse_args(argv)
    try:
        committed = load_results(args.committed)
        new = load_results(args.new)
    except (OSError, json.JSONDecodeError) as error:
        print(f"compare_results.py: {error}", file=sys.stderr)
        return EXIT_ERROR
    print(json.dumps(compare_objects(committed, new), indent=REPORT_INDENT))
    return EXIT_OK


def _is_number(value: object) -> bool:
    """True for a JSON number. Python's bool is an int subclass, and is not a number here."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _json_type(value: object) -> str:
    """The JSON type of a parsed leaf value: one of the module's *_TYPE names.

    A boolean is checked before the numbers because Python's bool is an int subclass. An int and a
    float are both NUMBER_TYPE: JSON has one number type. A container reaches here only where the
    two documents disagree about it, which the module docstring makes one "other" leaf.
    """
    if isinstance(value, bool):
        return BOOLEAN_TYPE
    if isinstance(value, (int, float)):
        return NUMBER_TYPE
    if isinstance(value, str):
        return STRING_TYPE
    if value is None:
        return NULL_TYPE
    if isinstance(value, dict):
        return OBJECT_TYPE
    if isinstance(value, list):
        return ARRAY_TYPE
    raise TypeError(f"not a JSON value: {value!r}")


def _same_value(committed: object, new: object) -> bool:
    """True when both leaves have the same JSON type and an equal value (the docstring's rule)."""
    return _json_type(committed) == _json_type(new) and committed == new


def _pointer_token(token: str) -> str:
    """Escape one RFC 6901 reference token: "~" first, then "/" (RFC 6901 §3)."""
    return token.replace(POINTER_TILDE, POINTER_ESCAPE_TILDE).replace(
        POINTER_SEPARATOR, POINTER_ESCAPE_SLASH
    )


def _child_pointer(path: str, token: str) -> str:
    """The JSON Pointer of a child of path reached by token."""
    return path + POINTER_SEPARATOR + _pointer_token(token)


def _differences(committed: object, new: object) -> tuple[object, float | None]:
    """The absolute and relative difference of two numbers, per the module docstring."""
    if committed == new:
        # Exactly equal values differ by 0. Returned rather than computed, because the difference
        # of two equal infinities is NaN, and a finite denominator's ratio would be 0.0 anyway.
        return 0, 0.0
    abs_diff = abs(new - committed)
    if committed == 0:
        # No finite relative difference against a zero denominator.
        return abs_diff, None
    return abs_diff, abs_diff / abs(committed)


def _leaf(
    path: str,
    committed: object,
    new: object,
    committed_present: bool,
    new_present: bool,
) -> dict[str, object]:
    """One report record for the leaf at path."""
    present = [
        value for value, exists in ((committed, committed_present), (new, new_present)) if exists
    ]
    record: dict[str, object] = {
        "path": path,
        "kind": NUMBER_KIND if all(_is_number(value) for value in present) else OTHER_KIND,
        "identical": committed_present == new_present
        and (not committed_present or _same_value(committed, new)),
        "committed_present": committed_present,
        "new_present": new_present,
        "committed": committed if committed_present else None,
        "new": new if new_present else None,
    }
    if record["kind"] == NUMBER_KIND:
        abs_diff: object = None
        rel_diff: float | None = None
        if committed_present and new_present:
            abs_diff, rel_diff = _differences(committed, new)
        record["abs_diff"] = abs_diff
        record["rel_diff"] = rel_diff
    return record


def _walk(committed: object, new: object, path: str, leaves: list[dict[str, object]]) -> None:
    """Append one record per leaf under path, following the module docstring's conventions."""
    if isinstance(committed, dict) and isinstance(new, dict):
        for key in sorted(set(committed) | set(new), key=str):
            child = _child_pointer(path, str(key))
            if key in committed and key in new:
                _walk(committed[key], new[key], child, leaves)
            else:
                leaves.append(
                    _leaf(
                        child,
                        committed.get(key),
                        new.get(key),
                        key in committed,
                        key in new,
                    )
                )
        return
    if isinstance(committed, list) and isinstance(new, list):
        for index in range(max(len(committed), len(new))):
            child = _child_pointer(path, str(index))
            if index < len(committed) and index < len(new):
                _walk(committed[index], new[index], child, leaves)
            else:
                leaves.append(
                    _leaf(
                        child,
                        committed[index] if index < len(committed) else None,
                        new[index] if index < len(new) else None,
                        index < len(committed),
                        index < len(new),
                    )
                )
        return
    leaves.append(_leaf(path, committed, new, True, True))


if __name__ == "__main__":
    sys.exit(main())
