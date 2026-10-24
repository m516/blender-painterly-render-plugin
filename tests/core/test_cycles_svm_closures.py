"""Card T6.7: Cycles' closure SVM nodes, the BSDF lookup tables and the painterly closure collector.

Checks that the svm_eval_nodes() manifest lists the closure cases, that VENDORED.toml lists this
card's vendored files and fragments and none of the paths it must never vendor, that the fragment
unit "tables" is declared and was generated from the committed inputs, and that the collector is
painterly code, not a shim.
"""

import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDORED = REPO_ROOT / "third_party" / "cycles" / "VENDORED.toml"
SVM_MANIFEST = REPO_ROOT / "src" / "cycles" / "svm_nodes.toml"
UNIT_MANIFEST = REPO_ROOT / "src" / "cycles" / "fragment_units.toml"

# The three files of card T6.7, "Vendored files".
VENDORED_FILES = ["scene/shader.tables", "scene/tables.h", "util/list.h"]

# Shimmed or fragmented: never a [[file]] entry.
NEVER_VENDORED = [
    "scene/shader.cpp",
    "scene/shader.h",
    "scene/scene.h",
    "scene/tables.cpp",
    "scene/shader_nodes.cpp",
    "kernel/svm/svm.h",
]

CASES = [
    "NODE_CLOSURE_BSDF",
    "NODE_CLOSURE_BACKGROUND",
    "NODE_CLOSURE_WEIGHT",
    "NODE_MIX_CLOSURE",
]

# The 67 fragments of card T6.7, "Fragments", in upstream order.
FRAGMENTS = [
    "kernel/svm/svm_h/svm_case/NODE_CLOSURE_BSDF",
    "kernel/svm/svm_h/svm_case/NODE_CLOSURE_BACKGROUND",
    "kernel/svm/svm_h/svm_case/NODE_CLOSURE_WEIGHT",
    "kernel/svm/svm_h/svm_case/NODE_MIX_CLOSURE",
    "scene/shader_nodes_cpp/member/BsdfBaseNode.BsdfBaseNode",
    "scene/shader_nodes_cpp/member/BsdfBaseNode.has_bump",
    "scene/shader_nodes_cpp/member/BsdfNode.BsdfNode",
    "scene/shader_nodes_cpp/member/BsdfNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/BsdfNode.compile-SVMCompiler_compiler",
    "scene/shader_nodes_cpp/member/BsdfNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/node_define/GlossyBsdfNode",
    "scene/shader_nodes_cpp/member/GlossyBsdfNode.GlossyBsdfNode",
    "scene/shader_nodes_cpp/member/GlossyBsdfNode.is_isotropic",
    "scene/shader_nodes_cpp/member/GlossyBsdfNode.attributes",
    "scene/shader_nodes_cpp/member/GlossyBsdfNode.simplify_settings",
    "scene/shader_nodes_cpp/member/GlossyBsdfNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/GlossyBsdfNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/node_define/GlassBsdfNode",
    "scene/shader_nodes_cpp/member/GlassBsdfNode.GlassBsdfNode",
    "scene/shader_nodes_cpp/member/GlassBsdfNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/GlassBsdfNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/node_define/RefractionBsdfNode",
    "scene/shader_nodes_cpp/member/RefractionBsdfNode.RefractionBsdfNode",
    "scene/shader_nodes_cpp/member/RefractionBsdfNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/RefractionBsdfNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/node_define/DiffuseBsdfNode",
    "scene/shader_nodes_cpp/member/DiffuseBsdfNode.DiffuseBsdfNode",
    "scene/shader_nodes_cpp/member/DiffuseBsdfNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/DiffuseBsdfNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/node_define/PrincipledBsdfNode",
    "scene/shader_nodes_cpp/member/PrincipledBsdfNode.PrincipledBsdfNode",
    "scene/shader_nodes_cpp/member/PrincipledBsdfNode.simplify_settings",
    "scene/shader_nodes_cpp/member/PrincipledBsdfNode.has_surface_transparent",
    "scene/shader_nodes_cpp/member/PrincipledBsdfNode.is_thin_wall",
    "scene/shader_nodes_cpp/member/PrincipledBsdfNode.has_surface_emission",
    "scene/shader_nodes_cpp/member/PrincipledBsdfNode.subsurface_has_positive_weight",
    "scene/shader_nodes_cpp/member/PrincipledBsdfNode.has_surface_bssrdf",
    "scene/shader_nodes_cpp/member/PrincipledBsdfNode.has_nonzero_weight",
    "scene/shader_nodes_cpp/member/PrincipledBsdfNode.attributes",
    "scene/shader_nodes_cpp/member/PrincipledBsdfNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/PrincipledBsdfNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/member/PrincipledBsdfNode.has_bssrdf_bump",
    "scene/shader_nodes_cpp/node_define/TransparentBsdfNode",
    "scene/shader_nodes_cpp/member/TransparentBsdfNode.TransparentBsdfNode",
    "scene/shader_nodes_cpp/member/TransparentBsdfNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/TransparentBsdfNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/node_define/BackgroundNode",
    "scene/shader_nodes_cpp/member/BackgroundNode.BackgroundNode",
    "scene/shader_nodes_cpp/member/BackgroundNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/BackgroundNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/member/BackgroundNode.constant_fold",
    "scene/shader_nodes_cpp/node_define/AddClosureNode",
    "scene/shader_nodes_cpp/member/AddClosureNode.AddClosureNode",
    "scene/shader_nodes_cpp/member/AddClosureNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/AddClosureNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/member/AddClosureNode.constant_fold",
    "scene/shader_nodes_cpp/node_define/MixClosureNode",
    "scene/shader_nodes_cpp/member/MixClosureNode.MixClosureNode",
    "scene/shader_nodes_cpp/member/MixClosureNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/MixClosureNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/member/MixClosureNode.constant_fold",
    "scene/tables_cpp/member/LookupTables.LookupTables",
    "scene/tables_cpp/member/LookupTables.~LookupTables",
    "scene/tables_cpp/member/LookupTables.need_update",
    "scene/tables_cpp/function/round_up_to_multiple",
    "scene/tables_cpp/member/LookupTables.add_table",
    "scene/tables_cpp/member/LookupTables.remove_table",
]


def _vendored() -> dict:
    """VENDORED.toml as parsed by tomllib."""
    return tomllib.loads(VENDORED.read_text(encoding="utf-8"))


def test_manifest_lists_closure_cases() -> None:
    """svm_nodes.toml lists the four cases; kernel/svm/closure.h (card T6.5) evaluates them."""
    manifest = tomllib.loads(SVM_MANIFEST.read_text(encoding="utf-8"))
    assert set(CASES) <= set(manifest["cases"])
    assert "kernel/svm/closure.h" in manifest["includes"]


def test_closure_sources_vendored() -> None:
    """The three files and 67 fragments are listed; the never-vendored paths are not."""
    data = _vendored()
    dests = {entry["dest"] for entry in data["file"]}
    names = {entry["name"] for entry in data.get("fragment", [])}
    assert sorted(set(VENDORED_FILES) - dests) == []
    assert sorted(set(NEVER_VENDORED) & dests) == []
    assert sorted(set(FRAGMENTS) - names) == []


def test_tables_unit_declared() -> None:
    """fragment_units.toml declares the unit "tables" and the shader_nodes include of card T6.7."""
    units = tomllib.loads(UNIT_MANIFEST.read_text(encoding="utf-8"))["unit"]
    assert units["tables"] == {
        "upstream_path": "scene/tables.cpp",
        "includes": ["scene/tables.h", "scene/scene.h", "<cassert>", "<cstring>"],
        "node_registry": False,
    }
    includes = units["shader_nodes"]["includes"]
    position = includes.index("kernel/closure/bsdf_microfacet.h")
    assert includes[position - 1 : position + 2] == [
        "util/transform.h",
        "kernel/closure/bsdf_microfacet.h",
        "kernel/svm/math_util.h",
    ]


def test_tables_unit_is_current(build_dir: Path) -> None:
    """The build generated fragment_units/tables.cpp from the committed inputs."""
    unit = build_dir / "src" / "cycles" / "fragment_units" / "tables.cpp"
    assert unit.is_file()
    result = subprocess.run(
        [
            sys.executable,
            "tools/gen_fragment_units.py",
            "--manifest",
            "src/cycles/fragment_units.toml",
            "--vendored",
            "third_party/cycles/VENDORED.toml",
            "--unit",
            "tables",
            "--check",
            str(unit),
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0


def test_collector_is_painterly_code() -> None:
    """The collector lives under src/painterly/kernel/svm/; no shim shadows scene/tables.h."""
    assert (REPO_ROOT / "src" / "painterly" / "kernel" / "svm" / "collect.h").is_file()
    assert not (REPO_ROOT / "src" / "cycles" / "shim" / "scene" / "tables.h").exists()
