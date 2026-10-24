"""Card T6.8: Cycles' image texture SVM nodes and the in-memory image manager.

Checks that the svm_eval_nodes() manifest lists the image cases, that VENDORED.toml lists this
card's vendored files and fragments and none of the paths that cards T6.4 and T6.8 shim, and that
no vendored Cycles code calls an atomic operation, which the util/atomic.h shim does not provide.
"""

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CYCLES = REPO_ROOT / "third_party" / "cycles"
VENDORED = CYCLES / "VENDORED.toml"
SVM_MANIFEST = REPO_ROOT / "src" / "cycles" / "svm_nodes.toml"
SHIM = REPO_ROOT / "src" / "cycles" / "shim"

# The five files of card T6.8, "Vendored files", and util/types_image.h, which card T6.1 vendored.
VENDORED_FILES = [
    "kernel/device/cpu/image.h",
    "kernel/image.h",
    "kernel/svm/image.h",
    "kernel/util/image_2d.h",
    "util/half.h",
    "util/types_image.h",
]

# Shimmed by cards T6.4 and T6.8 (src/cycles/shim/<path>): never a [[file]] entry.
SHIMMED = ["scene/image.cpp", "scene/image.h", "util/atomic.h"]

CASES = [
    "NODE_TEX_IMAGE",
    "NODE_TEX_IMAGE_DERIVATIVE",
    "NODE_TEX_IMAGE_BOX",
    "NODE_TEX_IMAGE_BOX_DERIVATIVE",
    "NODE_TEX_ENVIRONMENT",
    "NODE_TEX_ENVIRONMENT_DERIVATIVE",
]

# A call of an atomic operation or a barrier of upstream's util/atomic.h (util/atomic.h:12-20), or
# of Blender's intern/atomic, onto which upstream maps them.
ATOMIC_USE = re.compile(r"\batomic_[a-z0-9_]+\s*\(|\bCCL_LOCAL_MEM_FENCE\b|\bccl_barrier\s*\(")


def _vendored() -> dict:
    with VENDORED.open("rb") as f:
        return tomllib.load(f)


def test_manifest_lists_image_cases() -> None:
    with SVM_MANIFEST.open("rb") as f:
        manifest = tomllib.load(f)
    assert set(CASES) <= set(manifest["cases"])
    assert "kernel/svm/image.h" in manifest["includes"]


def test_image_sources_vendored_and_shimmed() -> None:
    vendored = _vendored()
    dests = {entry["dest"] for entry in vendored["file"]}
    assert set(VENDORED_FILES) <= dests
    assert not dests & set(SHIMMED)
    for path in SHIMMED:
        assert (SHIM / path).is_file(), path
    names = {entry["name"] for entry in vendored["fragment"]}
    assert {"kernel/svm/svm_h/svm_case/" + case for case in CASES} <= names


def test_no_vendored_cycles_code_calls_an_atomic_operation() -> None:
    """The util/atomic.h shim defines no atomic operation (card T6.8, Decision 3)."""
    vendored = _vendored()
    paths = [CYCLES / entry["dest"] for entry in vendored["file"] if entry["upstream"] == "cycles"]
    paths += [CYCLES / "fragments" / (entry["name"] + ".inc") for entry in vendored["fragment"]]
    users = [
        str(path.relative_to(CYCLES))
        for path in paths
        if path.suffix in (".h", ".cpp", ".inc")
        and ATOMIC_USE.search(path.read_text(encoding="utf-8"))
    ]
    assert users == []
