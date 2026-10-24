"""Card T6.6: Cycles' texture and texture-coordinate SVM nodes and the texture node classes.

Checks that the svm_eval_nodes() manifest lists the new cases, that VENDORED.toml lists this card's
vendored files and fragments and none of the paths it must never vendor, and that the build used the
committed inputs of the generated fragment unit "transform".
"""

import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDORED = REPO_ROOT / "third_party" / "cycles" / "VENDORED.toml"
SVM_MANIFEST = REPO_ROOT / "src" / "cycles" / "svm_nodes.toml"
UNIT_MANIFEST = REPO_ROOT / "src" / "cycles" / "fragment_units.toml"

# The 32 headers of card T6.6, "Vendored files".
VENDORED_FILES = [
    "kernel/bvh/util.h",
    "kernel/camera/camera.h",
    "kernel/camera/projection.h",
    "kernel/geom/attribute.h",
    "kernel/geom/curve.h",
    "kernel/geom/motion_curve.h",
    "kernel/geom/motion_point.h",
    "kernel/geom/motion_triangle.h",
    "kernel/geom/object.h",
    "kernel/geom/point.h",
    "kernel/geom/primitive.h",
    "kernel/geom/triangle.h",
    "kernel/geom/volume.h",
    "kernel/integrator/state.h",
    "kernel/sample/lcg.h",
    "kernel/sample/mapping.h",
    "kernel/svm/attribute.h",
    "kernel/svm/brick.h",
    "kernel/svm/checker.h",
    "kernel/svm/fractal_noise.h",
    "kernel/svm/geometry.h",
    "kernel/svm/gradient.h",
    "kernel/svm/magic.h",
    "kernel/svm/noise.h",
    "kernel/svm/noisetex.h",
    "kernel/svm/tex_coord.h",
    "kernel/svm/voronoi.h",
    "kernel/svm/wave.h",
    "kernel/svm/white_noise.h",
    "kernel/util/differential.h",
    "kernel/util/image_3d.h",
    "kernel/util/lookup_table.h",
]

# Never a [[file]] entry: reached only through inactive conditionals (WITH_OSL,
# __PATH_GUIDING__, or left unvendored by card T6.5 (kernel/util/nanovdb.h, WITH_NANOVDB)),
# fragmented (kernel/svm/svm.h, scene/shader_nodes.cpp, util/transform.cpp), or kept out by
# card T3.2 (util/boundbox.h).
NEVER_VENDORED = [
    "kernel/osl/camera.h",
    "kernel/osl/closures_template.h",
    "kernel/osl/types.h",
    "util/guiding.h",
    "kernel/util/nanovdb.h",
    "kernel/svm/svm.h",
    "scene/shader_nodes.cpp",
    "util/transform.cpp",
    "util/boundbox.h",
]

CASES = [
    "NODE_GEOMETRY",
    "NODE_GEOMETRY_DERIVATIVE",
    "NODE_TEX_COORD",
    "NODE_TEX_COORD_DERIVATIVE",
    "NODE_ATTR",
    "NODE_ATTR_DERIVATIVE",
    "NODE_TEX_NOISE",
    "NODE_TEX_GRADIENT",
    "NODE_TEX_VORONOI",
    "NODE_TEX_WAVE",
    "NODE_TEX_MAGIC",
    "NODE_TEX_CHECKER",
    "NODE_TEX_BRICK",
    "NODE_TEX_WHITE_NOISE",
]

INCLUDES = [
    "kernel/svm/attribute.h",
    "kernel/svm/brick.h",
    "kernel/svm/checker.h",
    "kernel/svm/geometry.h",
    "kernel/svm/gradient.h",
    "kernel/svm/magic.h",
    "kernel/svm/noisetex.h",
    "kernel/svm/tex_coord.h",
    "kernel/svm/voronoi.h",
    "kernel/svm/wave.h",
    "kernel/svm/white_noise.h",
]

# The 55 fragments of card T6.6, "Fragments".
FRAGMENTS = [
    "kernel/svm/svm_h/svm_case/NODE_GEOMETRY",
    "kernel/svm/svm_h/svm_case/NODE_GEOMETRY_DERIVATIVE",
    "kernel/svm/svm_h/svm_case/NODE_TEX_COORD",
    "kernel/svm/svm_h/svm_case/NODE_TEX_COORD_DERIVATIVE",
    "kernel/svm/svm_h/svm_case/NODE_ATTR",
    "kernel/svm/svm_h/svm_case/NODE_ATTR_DERIVATIVE",
    "kernel/svm/svm_h/svm_case/NODE_TEX_NOISE",
    "kernel/svm/svm_h/svm_case/NODE_TEX_GRADIENT",
    "kernel/svm/svm_h/svm_case/NODE_TEX_VORONOI",
    "kernel/svm/svm_h/svm_case/NODE_TEX_WAVE",
    "kernel/svm/svm_h/svm_case/NODE_TEX_MAGIC",
    "kernel/svm/svm_h/svm_case/NODE_TEX_CHECKER",
    "kernel/svm/svm_h/svm_case/NODE_TEX_BRICK",
    "kernel/svm/svm_h/svm_case/NODE_TEX_WHITE_NOISE",
    "scene/shader_nodes_cpp/define/TEXTURE_MAPPING_DEFINE",
    "scene/shader_nodes_cpp/member/TextureMapping.TextureMapping",
    "scene/shader_nodes_cpp/member/TextureMapping.compute_transform",
    "scene/shader_nodes_cpp/member/TextureMapping.skip",
    "scene/shader_nodes_cpp/member/TextureMapping.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/TextureMapping.compile_begin",
    "scene/shader_nodes_cpp/member/TextureMapping.compile_end",
    "scene/shader_nodes_cpp/member/TextureMapping.compile-OSLCompiler",
    "scene/shader_nodes_cpp/node_define/GradientTextureNode",
    "scene/shader_nodes_cpp/member/GradientTextureNode.GradientTextureNode",
    "scene/shader_nodes_cpp/member/GradientTextureNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/GradientTextureNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/node_define/NoiseTextureNode",
    "scene/shader_nodes_cpp/member/NoiseTextureNode.NoiseTextureNode",
    "scene/shader_nodes_cpp/member/NoiseTextureNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/NoiseTextureNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/node_define/VoronoiTextureNode",
    "scene/shader_nodes_cpp/member/VoronoiTextureNode.VoronoiTextureNode",
    "scene/shader_nodes_cpp/member/VoronoiTextureNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/VoronoiTextureNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/node_define/WhiteNoiseTextureNode",
    "scene/shader_nodes_cpp/member/WhiteNoiseTextureNode.WhiteNoiseTextureNode",
    "scene/shader_nodes_cpp/member/WhiteNoiseTextureNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/WhiteNoiseTextureNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/node_define/WaveTextureNode",
    "scene/shader_nodes_cpp/member/WaveTextureNode.WaveTextureNode",
    "scene/shader_nodes_cpp/member/WaveTextureNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/WaveTextureNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/node_define/MagicTextureNode",
    "scene/shader_nodes_cpp/member/MagicTextureNode.MagicTextureNode",
    "scene/shader_nodes_cpp/member/MagicTextureNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/MagicTextureNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/node_define/CheckerTextureNode",
    "scene/shader_nodes_cpp/member/CheckerTextureNode.CheckerTextureNode",
    "scene/shader_nodes_cpp/member/CheckerTextureNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/CheckerTextureNode.compile-OSLCompiler",
    "scene/shader_nodes_cpp/node_define/BrickTextureNode",
    "scene/shader_nodes_cpp/member/BrickTextureNode.BrickTextureNode",
    "scene/shader_nodes_cpp/member/BrickTextureNode.compile-SVMCompiler",
    "scene/shader_nodes_cpp/member/BrickTextureNode.compile-OSLCompiler",
    "util/transform_cpp/function/transform_transposed_inverse",
]


def _vendored() -> dict:
    """VENDORED.toml as parsed by tomllib."""
    return tomllib.loads(VENDORED.read_text(encoding="utf-8"))


def test_manifest_lists_texture_nodes() -> None:
    """svm_nodes.toml lists the 14 cases and 11 evaluator headers (later cards may append)."""
    manifest = tomllib.loads(SVM_MANIFEST.read_text(encoding="utf-8"))
    assert set(CASES) <= set(manifest["cases"])
    assert set(INCLUDES) <= set(manifest["includes"])


def test_texture_sources_vendored() -> None:
    """The 32 headers and 55 fragments are listed; the never-vendored paths are not."""
    data = _vendored()
    dests = {entry["dest"] for entry in data["file"]}
    names = {entry["name"] for entry in data.get("fragment", [])}
    assert sorted(set(VENDORED_FILES) - dests) == []
    assert sorted(set(NEVER_VENDORED) & dests) == []
    assert sorted(set(FRAGMENTS) - names) == []


def test_transform_unit_declared() -> None:
    """fragment_units.toml declares the unit "transform" of card T6.6, "Interface"."""
    units = tomllib.loads(UNIT_MANIFEST.read_text(encoding="utf-8"))["unit"]
    assert units["transform"] == {
        "upstream_path": "util/transform.cpp",
        "includes": ["util/transform.h", "util/projection.h"],
        "node_registry": False,
    }


def test_transform_unit_is_current(build_dir: Path) -> None:
    """The build generated fragment_units/transform.cpp from the committed inputs."""
    unit = build_dir / "src" / "cycles" / "fragment_units" / "transform.cpp"
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
            "transform",
            "--check",
            str(unit),
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0
