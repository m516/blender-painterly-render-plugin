"""The fragment grammar of tools/vendor_sync.py, and the [[fragment]] entries of VENDORED.toml.

The grammar tests run the tool's Python API on canned sources. The tests that read a fragment
build their own one-commit upstream checkout under tmp_path (as tests/core/test_vendored.py does),
so none of them needs the network or a .cache/vendor checkout. The last one checks that the
committed VENDORED.toml survives the tool's own writer, which is what every later `sync`, `add` and
`remove` writes back.
"""

import hashlib
import importlib.util
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_TOOL = REPO_ROOT / "tools" / "vendor_sync.py"


def _load_vendor_tool() -> ModuleType:
    """tools/vendor_sync.py, loaded by path as test_symbol_audit_parsers.py loads its tool."""
    spec = importlib.util.spec_from_file_location("vendor_sync_fragments", VENDOR_TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


vs = _load_vendor_tool()

# The temporary VENDORED.toml of test 8: one vendored file, and no fragment until 8.1 adds one.
# Both hashes are of "#define WHOLE 1\n", the content of the checkout's scene/whole.h. `commit` is
# filled in by _tree, which commits the fixture checkout and pins that commit.
TEST_MANIFEST = r"""[upstream.cycles]
repo = "https://github.com/blender/blender.git"
tag = "v5.2.2"
commit = "{commit}"
root = "intern/cycles"

[[file]]
upstream = "cycles"
upstream_path = "scene/whole.h"
dest = "scene/whole.h"
upstream_sha256 = "aa420eefe02d5613df36cba6caf1a95e924d852201e3db66f6ce070b58b3460f"
sha256 = "aa420eefe02d5613df36cba6caf1a95e924d852201e3db66f6ce070b58b3460f"
patched = false
"""

# The fixture's own git commands, exactly as tests/core/test_vendored.py runs them: no GIT_*
# variable of the caller, no user or system git configuration (so no commit signing and no
# core.autocrlf), and a fixed identity and date, so every run makes the same commit.
FIXTURE_GIT_ENV = {
    **{key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Painterly tests",
    "GIT_AUTHOR_EMAIL": "tests@painterly.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_NAME": "Painterly tests",
    "GIT_COMMITTER_EMAIL": "tests@painterly.invalid",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
}


def _fixture_git(repo: Path, *args: str) -> str:
    """Run git in the fixture repository repo; return its stdout without surrounding whitespace."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        env=FIXTURE_GIT_ENV,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(checkout: Path, message: str) -> str:
    """Commit everything under checkout and return the new commit's id."""
    _fixture_git(checkout, "add", "--all")
    _fixture_git(checkout, "commit", "--quiet", "--message", message)
    return _fixture_git(checkout, "rev-parse", "HEAD")


def _init_checkout(checkout: Path) -> str:
    """Make checkout a one-commit git repository of what is already in it; return its commit."""
    _fixture_git(checkout, "init", "--quiet")
    return _commit(checkout, "fixture upstream")


CASES = r"""CCL_NAMESPACE_BEGIN

ccl_device void toy_eval(ccl_private float *stack, int offset)
{
  while (true) {
    switch (toy_node_type(offset++)) {
      SVM_CASE(NODE_END)
      return;
      SVM_CASE(NODE_SHADER_JUMP)
      {
        if (type == SHADER_TYPE_SURFACE) {
          offset = 1;
        }
        break;
      }
      SVM_CASE(NODE_ATTR)
      IF_KERNEL_NODES_FEATURE(VOLUME)
      {
#ifdef __VOLUME__
        toy_attr_volume(stack);
#endif
      }
      else {
        toy_attr_surface(stack);
      }
      break;
      SVM_CASE(NODE_AOV_START)
      if (!toy_check()) {
        return;
      }
      break;
      SVM_CASE(NODE_MIX)
      toy_mix(stack);

      SVM_CASE(NODE_INVERT)
      toy_invert(stack);
      break;
#if defined(__HAIR__)
      SVM_CASE(NODE_HAIR_INFO)
      toy_hair(stack);
      break;
#endif
#ifdef __SHADER_RAYTRACE__
      SVM_CASE(NODE_BEVEL)
      toy_bevel(stack);
      break;
      SVM_CASE(NODE_RAYCAST)
      toy_raycast(stack);
      break;
#endif
      SVM_CASE(NODE_CLAMP)
      toy_clamp(stack);
      break;

      default:
        return;
    }
  }
}

CCL_NAMESPACE_END
"""

NODES = r"""CCL_NAMESPACE_BEGIN

#define TOY_MAPPING_DEFINE(Node) \
  SOCKET_FLOAT(a, "A", 0.0f); \
  SOCKET_FLOAT(b, "B", 1.0f);

NODE_DEFINE(ToyNode)
{
  NodeType *type = NodeType::add("toy", create, NodeType::SHADER);
  SOCKET_STRING(name, "Name {", ustring("}"));
  /* } in a comment */
  SOCKET_INT(c, "C", '{'); // { in a line comment
  return type;
}

ToyNode::ToyNode() : ShaderNode(get_node_type()) {}

ToyNode::ToyNode(const ToyNode &other) = default;

bool ToyNode::registered = NodeType::register_on_init([] {
  ToyNode::get_node_type();
  return true;
});

static int toy_helper(int a)
{
  return a + 1;
}

void ToyNode::compile(SVMCompiler &compiler)
{
  compiler.add_node(this, NODE_MATH, SVMNodeMath{.math_type = toy_helper(1)});
}

void ToyNode::compile(SVMCompiler &compiler,
                      ShaderInput *input,
                      ShaderOutput *output)
{
  compiler.stack_link(input, output);
}

void ToyNode::compile(OSLCompiler & /*compiler*/) {}

template<typename T>
void ToyNode::emit(const T &value)
{
  write(value);
}

void ToyNode::attributes(Shader *shader)
{
#ifdef WITH_TOY
  if (shader) {
    add();
  }
#endif
}

#if 0
void ToyNode::disabled()
{
}
#endif

CCL_NAMESPACE_END
"""

FALLS = r"""switch (t) {
  SVM_CASE(NODE_X)
  if (c) {
    return;
  }
  SVM_CASE(NODE_Y)
  break;
  default:
    return;
}
"""


def _lines(text: str, first: int, last: int) -> str:
    """Lines first..last of text, each followed by a newline."""
    return "".join(f"{line}\n" for line in text.split("\n")[first - 1 : last])


def test_svm_case() -> None:
    """A case's extent ends before the next case, `default:` or a directive at its depth."""
    assert vs.extract_fragment(CASES, "svm_case", "NODE_END") == vs.Fragment(
        _lines(CASES, 7, 8), 7, 8
    )
    assert vs.extract_fragment(CASES, "svm_case", "NODE_SHADER_JUMP") == vs.Fragment(
        _lines(CASES, 9, 15), 9, 15
    )
    assert vs.extract_fragment(CASES, "svm_case", "NODE_ATTR") == vs.Fragment(
        _lines(CASES, 16, 26), 16, 26
    )
    assert vs.extract_fragment(CASES, "svm_case", "NODE_AOV_START") == vs.Fragment(
        _lines(CASES, 27, 31), 27, 31
    )
    assert vs.extract_fragment(CASES, "svm_case", "NODE_INVERT") == vs.Fragment(
        _lines(CASES, 35, 37), 35, 37
    )
    # A wrapped case keeps the #if and #endif that are the whole of its conditional.
    assert vs.extract_fragment(CASES, "svm_case", "NODE_HAIR_INFO") == vs.Fragment(
        _lines(CASES, 38, 42), 38, 42
    )
    # The blank line before `default:` is dropped from the extent.
    assert vs.extract_fragment(CASES, "svm_case", "NODE_CLAMP") == vs.Fragment(
        _lines(CASES, 51, 53), 51, 53
    )
    for anchor in ("NODE_MIX", "NODE_BEVEL", "NODE_RAYCAST", "NODE_NONE"):
        with pytest.raises(vs.FragmentError):
            vs.extract_fragment(CASES, "svm_case", anchor)
    # NODE_X ends in "}" but is not the NODE_SHADER_JUMP form, and it falls through when c is false.
    with pytest.raises(vs.FragmentError):
        vs.extract_fragment(FALLS, "svm_case", "NODE_X")
    assert vs.extract_fragment(FALLS, "svm_case", "NODE_Y") == vs.Fragment(
        _lines(FALLS, 6, 7), 6, 7
    )


def test_define_node_define_and_definitions() -> None:
    """Macros, NODE_DEFINE blocks and definitions, ignoring braces in literals and comments."""
    assert vs.extract_fragment(NODES, "define", "TOY_MAPPING_DEFINE") == vs.Fragment(
        _lines(NODES, 3, 5), 3, 5
    )
    assert vs.extract_fragment(NODES, "node_define", "ToyNode") == vs.Fragment(
        _lines(NODES, 7, 14), 7, 14
    )
    assert vs.extract_fragment(NODES, "member", "ToyNode::registered") == vs.Fragment(
        _lines(NODES, 20, 23), 20, 23
    )
    assert vs.extract_fragment(NODES, "function", "toy_helper") == vs.Fragment(
        _lines(NODES, 25, 28), 25, 28
    )
    # A definition's `template` line is part of its extent.
    assert vs.extract_fragment(NODES, "member", "ToyNode::emit") == vs.Fragment(
        _lines(NODES, 44, 48), 44, 48
    )
    assert vs.extract_fragment(NODES, "member", "ToyNode::attributes") == vs.Fragment(
        _lines(NODES, 50, 57), 50, 57
    )


def test_member_and_function_selection() -> None:
    """`params` selects one overload: an exact parameter text first, then a unique prefix."""
    with pytest.raises(vs.FragmentError):
        vs.extract_fragment(NODES, "member", "ToyNode::ToyNode")
    assert vs.extract_fragment(NODES, "member", "ToyNode::ToyNode", params="") == vs.Fragment(
        _lines(NODES, 16, 16), 16, 16
    )
    assert vs.extract_fragment(
        NODES, "member", "ToyNode::ToyNode", params="const ToyNode"
    ) == vs.Fragment(_lines(NODES, 18, 18), 18, 18)
    # Two prefix matches, so `SVMCompiler` alone is ambiguous; the exact text wins.
    with pytest.raises(vs.FragmentError):
        vs.extract_fragment(NODES, "member", "ToyNode::compile")
    with pytest.raises(vs.FragmentError):
        vs.extract_fragment(NODES, "member", "ToyNode::compile", params="SVMCompiler")
    assert vs.extract_fragment(
        NODES, "member", "ToyNode::compile", params="SVMCompiler &compiler"
    ) == vs.Fragment(_lines(NODES, 30, 33), 30, 33)
    assert vs.extract_fragment(
        NODES, "member", "ToyNode::compile", params="SVMCompiler &compiler, ShaderInput"
    ) == vs.Fragment(_lines(NODES, 35, 40), 35, 40)
    assert vs.extract_fragment(
        NODES, "member", "ToyNode::compile", params="OSLCompiler"
    ) == vs.Fragment(_lines(NODES, 42, 42), 42, 42)
    # Inside #if 0, a name that no line declares, and a declarator of the wrong kind.
    for kind, anchor in (
        ("member", "ToyNode::disabled"),
        ("member", "ToyNode::toy_helper"),
        ("function", "ToyNode"),
    ):
        with pytest.raises(vs.FragmentError):
            vs.extract_fragment(NODES, kind, anchor)


def test_span() -> None:
    """A span runs from the line equal to begin through the first later line equal to end."""
    begin = "ccl_device void toy_eval(ccl_private float *stack, int offset)"
    assert vs.extract_fragment(CASES, "span", begin=begin, end="{") == vs.Fragment(
        _lines(CASES, 3, 4), 3, 4
    )
    for start, stop in (
        ("      default: {", "{"),
        ("      break;", "{"),
        ("      default:", "CCL_NAMESPACE_BEGIN"),
        ("      SVM_CASE(NODE_HAIR_INFO)", "      break;"),
    ):
        with pytest.raises(vs.FragmentError):
            vs.extract_fragment(CASES, "span", begin=start, end=stop)


def test_lexing() -> None:
    """One left-to-right scan, so a quote in a comment and a comment mark in a literal agree."""
    with pytest.raises(vs.FragmentError):
        vs.extract_fragment(CASES.replace("\n", "\r\n", 1), "svm_case", "NODE_END")
    with pytest.raises(vs.FragmentError):
        vs.extract_fragment('int f()\n{\n  return "abc;\n}\n', "function", "f")
    s1 = "int f()\n{\n  return 1; // it's {\n}\n"
    assert vs.extract_fragment(s1, "function", "f") == vs.Fragment(s1, 1, 4)
    s2 = 'int g()\n{\n  return h("//", \'"\'); /* } */\n}\n'
    assert vs.extract_fragment(s2, "function", "g") == vs.Fragment(s2, 1, 4)


def test_list_anchors() -> None:
    """Every anchor that resolves, with its parameter text, sorted by line, kind and anchor."""
    assert vs.list_anchors(CASES) == [
        vs.Anchor("function", "toy_eval", "ccl_private float *stack, int offset", 3, 59),
        vs.Anchor("svm_case", "NODE_END", "", 7, 8),
        vs.Anchor("svm_case", "NODE_SHADER_JUMP", "", 9, 15),
        vs.Anchor("svm_case", "NODE_ATTR", "", 16, 26),
        vs.Anchor("svm_case", "NODE_AOV_START", "", 27, 31),
        vs.Anchor("svm_case", "NODE_INVERT", "", 35, 37),
        vs.Anchor("svm_case", "NODE_HAIR_INFO", "", 38, 42),
        vs.Anchor("svm_case", "NODE_CLAMP", "", 51, 53),
    ]
    assert vs.list_anchors(NODES) == [
        vs.Anchor("define", "TOY_MAPPING_DEFINE", "", 3, 5),
        vs.Anchor("node_define", "ToyNode", "", 7, 14),
        vs.Anchor("member", "ToyNode::ToyNode", "", 16, 16),
        vs.Anchor("member", "ToyNode::ToyNode", "const ToyNode &other", 18, 18),
        vs.Anchor("member", "ToyNode::registered", "", 20, 23),
        vs.Anchor("function", "toy_helper", "int a", 25, 28),
        vs.Anchor("member", "ToyNode::compile", "SVMCompiler &compiler", 30, 33),
        vs.Anchor(
            "member",
            "ToyNode::compile",
            "SVMCompiler &compiler, ShaderInput *input, ShaderOutput *output",
            35,
            40,
        ),
        vs.Anchor("member", "ToyNode::compile", "OSLCompiler &", 42, 42),
        vs.Anchor("member", "ToyNode::emit", "const T &value", 44, 48),
        vs.Anchor("member", "ToyNode::attributes", "Shader *shader", 50, 57),
    ]


def test_fragment_name() -> None:
    """The name of a fragment, and the 190-character bound on its file's path."""
    assert (
        vs.fragment_name("kernel/svm/svm.h", "svm_case", "NODE_END")
        == "kernel/svm/svm_h/svm_case/NODE_END"
    )
    assert (
        vs.fragment_name("kernel/svm/svm.h", "span", fragment_id="svm_eval_nodes_head")
        == "kernel/svm/svm_h/span/svm_eval_nodes_head"
    )
    assert (
        vs.fragment_name("scene/shader_nodes.cpp", "node_define", "MathNode")
        == "scene/shader_nodes_cpp/node_define/MathNode"
    )
    assert (
        vs.fragment_name(
            "scene/shader_nodes.cpp", "member", "MathNode::compile", params="SVMCompiler"
        )
        == "scene/shader_nodes_cpp/member/MathNode.compile-SVMCompiler"
    )
    assert (
        vs.fragment_name(
            "scene/shader_nodes.cpp", "member", "BsdfNode::compile", params="SVMCompiler &"
        )
        == "scene/shader_nodes_cpp/member/BsdfNode.compile-SVMCompiler"
    )
    assert (
        vs.fragment_name(
            "scene/shader_nodes.cpp",
            "member",
            "BsdfNode::compile",
            params="SVMCompiler &compiler, const T &data",
        )
        == "scene/shader_nodes_cpp/member/BsdfNode.compile-SVMCompiler_compiler_const_T_data"
    )
    assert (
        vs.fragment_name(
            "scene/shader_nodes.cpp",
            "member",
            "ScatterVolumeNode::ScatterVolumeNode",
            params="",
        )
        == "scene/shader_nodes_cpp/member/ScatterVolumeNode.ScatterVolumeNode-void"
    )
    assert (
        vs.fragment_name("scene/shader_nodes.cpp", "define", "TEXTURE_MAPPING_DEFINE")
        == "scene/shader_nodes_cpp/define/TEXTURE_MAPPING_DEFINE"
    )
    assert (
        vs.fragment_name("scene/shader_nodes.cpp", "function", "shader_bump_to_node_bump_offset")
        == "scene/shader_nodes_cpp/function/shader_bump_to_node_bump_offset"
    )
    assert (
        vs.fragment_name(
            "scene/svm.cpp", "member", "SVMCompiler::stack_size", params="SocketType::Type type"
        )
        == "scene/svm_cpp/member/SVMCompiler.stack_size-SocketType_Type_type"
    )
    assert (
        vs.fragment_name("scene/svm.cpp", "member", "SVMCompiler::Summary::full_report")
        == "scene/svm_cpp/member/SVMCompiler.Summary.full_report"
    )
    assert (
        vs.fragment_name("scene/svm.cpp", "member", "SVMShaderManager::~SVMShaderManager")
        == "scene/svm_cpp/member/SVMShaderManager.~SVMShaderManager"
    )
    assert vs.FRAGMENT_PATH_MAX == 190
    # 29 characters of directory, 28 of "scene/toy_nodes_cpp/function/", 7 of ".inc", and the name.
    name = vs.fragment_name("scene/toy_nodes.cpp", "function", "f", params="a" * 126)
    assert name == "scene/toy_nodes_cpp/function/f-" + "a" * 126
    assert len(f"third_party/cycles/fragments/{name}.inc") == 190
    with pytest.raises(vs.FragmentError, match="190"):
        vs.fragment_name("scene/toy_nodes.cpp", "function", "f", params="a" * 127)


def _tree(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    """A one-commit checkout with CASES, NODES and whole.h, and a manifest that vendors whole.h.

    The checkout is a git repository whose one commit is the manifest's pin, because the tool
    reads a fragment from the pinned commit's blob, never from the working tree.
    """
    checkout = tmp_path / "co"
    for relative, text in (
        ("intern/cycles/kernel/svm/toy.h", CASES),
        ("intern/cycles/scene/toy_nodes.cpp", NODES),
        ("intern/cycles/scene/whole.h", "#define WHOLE 1\n"),
    ):
        path = checkout / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    commit = _init_checkout(checkout)
    manifest = tmp_path / "tp" / "VENDORED.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(TEST_MANIFEST.format(commit=commit).encode("utf-8"))
    return manifest, {"cycles": checkout}


def _pinned(tmp_path: Path, commit: str | None = None) -> tuple[Path, dict[str, Path], str]:
    """A manifest pinning the fixture checkout, the checkouts, and the pinned commit.

    The pin is the checkout's HEAD unless commit names another one, so a test can point the
    manifest at an earlier commit while the checkout's working tree and HEAD have moved on.
    """
    checkout = tmp_path / "co"
    pinned = commit if commit is not None else _fixture_git(checkout, "rev-parse", "HEAD")
    manifest = tmp_path / "tp" / "VENDORED.toml"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_bytes(TEST_MANIFEST.format(commit=pinned).encode("utf-8"))
    return manifest, {"cycles": checkout}, pinned


def _fragment_files(manifest: Path) -> set[str]:
    """The repository-relative names of the .inc files under the manifest's fragments/."""
    directory = manifest.parent / "fragments"
    if not directory.is_dir():
        return set()
    return {
        path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()
    }


def test_manifest_round_trip(tmp_path: Path) -> None:
    """add-fragment, the rules, check, sync and remove-fragment on a temporary manifest."""
    manifest, checkouts = _tree(tmp_path)
    name = "scene/toy_nodes_cpp/member/ToyNode.compile-SVMCompiler_compiler"

    # 1. add_fragments writes the entry and its file, and the writer reproduces the file.
    added = vs.add_fragments(
        manifest,
        checkouts,
        "cycles",
        "scene/toy_nodes.cpp",
        "member",
        ["ToyNode::compile"],
        params="SVMCompiler &compiler",
    )
    assert added == [name]
    assert (manifest.parent / "fragments" / f"{name}.inc").read_bytes() == _lines(
        NODES, 30, 33
    ).encode("utf-8")
    with manifest.open("rb") as handle:
        data = tomllib.load(handle)
    assert data["fragment"] == [
        {
            "name": name,
            "upstream": "cycles",
            "upstream_path": "scene/toy_nodes.cpp",
            "kind": "member",
            "anchor": "ToyNode::compile",
            "params": "SVMCompiler &compiler",
            "upstream_lines": [30, 33],
            "sha256": "00e2df1ced6b49578e9c11a1c776543756a4355a24e47102dca72190bfdeeba8",
        }
    ]
    assert data["file"] == [
        {
            "upstream": "cycles",
            "upstream_path": "scene/whole.h",
            "dest": "scene/whole.h",
            "upstream_sha256": hashlib.sha256(b"#define WHOLE 1\n").hexdigest(),
            "sha256": hashlib.sha256(b"#define WHOLE 1\n").hexdigest(),
            "patched": False,
        }
    ]
    assert vs.render_manifest(vs.load_manifest(manifest)) == manifest.read_bytes().decode("utf-8")

    # 2. A failed extraction and an over-long path each leave the manifest and the files alone.
    before = manifest.read_bytes()
    files = _fragment_files(manifest)
    with pytest.raises(vs.FragmentError):
        vs.add_fragments(
            manifest, checkouts, "cycles", "kernel/svm/toy.h", "svm_case", ["NODE_END", "NODE_MIX"]
        )
    with pytest.raises(vs.FragmentError, match="190"):
        vs.add_fragments(
            manifest,
            checkouts,
            "cycles",
            "kernel/svm/toy.h",
            "span",
            fragment_id="x" * 136,
            begin="ccl_device void toy_eval(ccl_private float *stack, int offset)",
            end="{",
        )
    assert manifest.read_bytes() == before
    assert _fragment_files(manifest) == files

    # 3. A duplicate name, an overlapping range and a file that is also vendored whole.
    with pytest.raises(vs.FragmentError):
        vs.add_fragments(
            manifest,
            checkouts,
            "cycles",
            "scene/toy_nodes.cpp",
            "member",
            ["ToyNode::compile"],
            params="SVMCompiler &compiler",
        )
    vs.add_fragments(
        manifest, checkouts, "cycles", "scene/toy_nodes.cpp", "node_define", ["ToyNode"]
    )
    with pytest.raises(vs.FragmentError):
        vs.add_fragments(
            manifest,
            checkouts,
            "cycles",
            "scene/toy_nodes.cpp",
            "span",
            fragment_id="overlap",
            begin="NODE_DEFINE(ToyNode)",
            end="{",
        )
    with pytest.raises(vs.FragmentError):
        vs.add_fragments(manifest, checkouts, "cycles", "scene/whole.h", "define", ["WHOLE"])
    with manifest.open("rb") as handle:
        data = tomllib.load(handle)
    assert [table["name"] for table in data["fragment"]] == [
        name,
        "scene/toy_nodes_cpp/node_define/ToyNode",
    ]
    assert vs.render_manifest(vs.load_manifest(manifest)) == manifest.read_bytes().decode("utf-8")
    # The same rule from the [[file]] side, which is the check that `add` relies on.
    loaded = vs.load_manifest(manifest)
    entry = vs.Entry("cycles", "scene/toy_nodes.cpp", "scene/toy_nodes.cpp")
    with pytest.raises(vs.FragmentError):
        vs.check_structure(
            vs.Manifest(loaded.upstreams, [*loaded.entries, entry], loaded.fragments)
        )

    # 4. Both checks are clean.
    assert vs.check_fragments(manifest) == []
    assert vs.check_fragments(manifest, checkouts) == []

    # 5. One extra byte, and one extra file, each give exactly one message.
    path = manifest.parent / "fragments" / f"{name}.inc"
    original = path.read_bytes()
    path.write_bytes(original + b"\n")
    problems = vs.check_fragments(manifest)
    assert len(problems) == 1
    assert name in problems[0]
    path.write_bytes(original)
    stray = manifest.parent / "fragments" / "stray.inc"
    stray.write_bytes(b"x\n")
    problems = vs.check_fragments(manifest)
    assert len(problems) == 1
    assert "fragments/stray.inc" in problems[0]
    stray.unlink()

    # 6. A changed line in the pinned commit fails sync and the --upstream check, and writes no
    # byte. The line is committed and the manifest's pin moves to that commit: an uncommitted edit
    # is not in the pinned commit, so it changes nothing (test_a_working_tree_edit_is_unseen).
    toy_nodes = checkouts["cycles"] / "intern" / "cycles" / "scene" / "toy_nodes.cpp"
    assert toy_nodes.read_bytes().split(b"\n")[31].strip() == (
        b"compiler.add_node(this, NODE_MATH, SVMNodeMath{.math_type = toy_helper(1)});"
    )
    toy_nodes.write_bytes(toy_nodes.read_bytes().replace(b"toy_helper(1)", b"toy_helper(2)", 1))
    commit = _commit(checkouts["cycles"], "changed line")
    pinned_before = vs.load_manifest(manifest).upstreams["cycles"].commit
    manifest.write_bytes(
        manifest.read_bytes().replace(
            f'commit = "{pinned_before}"'.encode(),
            f'commit = "{commit}"'.encode(),
        )
    )
    assert vs.load_manifest(manifest).upstreams["cycles"].commit == commit
    with pytest.raises(vs.FragmentError) as raised:
        vs.sync_fragments(manifest, checkouts)
    assert name in str(raised.value)
    assert path.read_bytes() == original
    problems = vs.check_fragments(manifest, checkouts)
    assert any(name in problem for problem in problems)
    # Step 7 reads no checkout, so the pin stays at the changed commit and the working tree keeps
    # the changed line; no further extraction happens in this test.

    # 7. remove_fragments deletes the entry and its file, and refuses an unknown name.
    vs.remove_fragments(manifest, [name])
    assert not path.exists()
    with manifest.open("rb") as handle:
        data = tomllib.load(handle)
    assert [table["name"] for table in data["fragment"]] == [
        "scene/toy_nodes_cpp/node_define/ToyNode"
    ]
    assert data["file"][0]["dest"] == "scene/whole.h"
    before = manifest.read_bytes()
    with pytest.raises(vs.FragmentError):
        vs.remove_fragments(manifest, ["scene/toy_nodes_cpp/member/Nope"])
    assert manifest.read_bytes() == before


def test_member_without_params(tmp_path: Path) -> None:
    """A member or function entry without `params` is valid; a present `params` must be a string.

    T6.2 makes `params` optional: "a valid anchor (with `params` a string, if present) or a valid
    id". Card T6.4's step 4 adds members and functions without --params, and its fragment names
    carry no -<params> suffix for them. ToyNode::attributes has one definition, so no `params` is
    needed to select it.
    """
    manifest, checkouts = _tree(tmp_path)
    name = "scene/toy_nodes_cpp/member/ToyNode.attributes"
    assert vs.add_fragments(
        manifest, checkouts, "cycles", "scene/toy_nodes.cpp", "member", ["ToyNode::attributes"]
    ) == [name]
    # The name has no -<params> suffix. Had step 4 passed --params, the empty parameter text would
    # have given "ToyNode.attributes-void" instead (fragment_name's suffix rule).
    assert (
        vs.fragment_name("scene/toy_nodes.cpp", "member", "ToyNode::attributes", params="")
        == f"{name}-void"
    )

    # The entry has no `params` key, and its other fields are the member's.
    text = _lines(NODES, 50, 57).encode("utf-8")
    with manifest.open("rb") as handle:
        data = tomllib.load(handle)
    assert data["fragment"] == [
        {
            "name": name,
            "upstream": "cycles",
            "upstream_path": "scene/toy_nodes.cpp",
            "kind": "member",
            "anchor": "ToyNode::attributes",
            "upstream_lines": [50, 57],
            "sha256": hashlib.sha256(text).hexdigest(),
        }
    ]
    # load_manifest runs the rules, so they accept the entry; the writer reproduces the file.
    assert vs.render_manifest(vs.load_manifest(manifest)) == manifest.read_bytes().decode("utf-8")
    assert (manifest.parent / "fragments" / f"{name}.inc").read_bytes() == text
    assert vs.check_fragments(manifest, checkouts) == []

    # A `params` that is present must still be a string, with the same message as before.
    bad = manifest.parent / "VENDORED.bad.toml"
    bad.write_bytes(
        manifest.read_bytes().replace(
            b'anchor = "ToyNode::attributes"\n',
            b'anchor = "ToyNode::attributes"\nparams = 1\n',
        )
    )
    with pytest.raises(vs.FragmentError, match="the key 'params' must be a string"):
        vs.load_manifest(bad)


def _fixture_checkout(tmp_path: Path) -> tuple[Path, str]:
    """A one-commit checkout of the fixture upstream's two source files, and its commit."""
    checkout = tmp_path / "co"
    for relative, text in (
        ("intern/cycles/kernel/svm/toy.h", CASES),
        ("intern/cycles/scene/toy_nodes.cpp", NODES),
    ):
        path = checkout / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    return checkout, _init_checkout(checkout)


def test_a_working_tree_edit_is_unseen(tmp_path: Path) -> None:
    """An uncommitted edit, a deleted file and an untracked file change no fragment byte.

    The fragment's bytes come from the pinned commit's blob, so a checkout that is edited, has a
    file deleted, or holds a file only in its working tree still gives the committed bytes: the
    working tree is not the source (T3.27's rule, now for fragments too). A path that the commit
    does not have is refused, because a fragment is a verbatim extract of upstream's own code.
    """
    manifest, checkouts = _tree(tmp_path)
    checkout = checkouts["cycles"]
    toy_nodes = checkout / "intern" / "cycles" / "scene" / "toy_nodes.cpp"
    name = "scene/toy_nodes_cpp/member/ToyNode.compile-SVMCompiler_compiler"
    assert vs.add_fragments(
        manifest,
        checkouts,
        "cycles",
        "scene/toy_nodes.cpp",
        "member",
        ["ToyNode::compile"],
        params="SVMCompiler &compiler",
    ) == [name]
    path = manifest.parent / "fragments" / f"{name}.inc"
    original = path.read_bytes()

    # An uncommitted edit: neither check sees it, and sync rewrites the same bytes.
    toy_nodes.write_bytes(toy_nodes.read_bytes().replace(b"toy_helper(1)", b"toy_helper(2)", 1))
    assert vs.check_fragments(manifest, checkouts) == []
    vs.sync_fragments(manifest, checkouts)
    assert path.read_bytes() == original

    # The file deleted from the working tree: still nothing to report, still the same bytes.
    toy_nodes.unlink()
    assert vs.check_fragments(manifest, checkouts) == []
    vs.sync_fragments(manifest, checkouts)
    assert path.read_bytes() == original

    # A file that exists only in the working tree is not in upstream: it is refused.
    untracked = checkout / "intern" / "cycles" / "scene" / "untracked.cpp"
    untracked.write_bytes(NODES.encode("utf-8"))
    commit = vs.load_manifest(manifest).upstreams["cycles"].commit
    with pytest.raises(vs.FragmentError) as raised:
        vs.add_fragments(
            manifest, checkouts, "cycles", "scene/untracked.cpp", "function", ["toy_helper"]
        )
    assert str(raised.value) == (
        f"cycles:scene/untracked.cpp at {commit}: scene/untracked.cpp is not a file in upstream"
        f" cycles at {commit}"
    )

    # core.autocrlf=true puts CRLF in the working tree; the blob and the fragment stay LF.
    _fixture_git(checkout, "config", "core.autocrlf", "true")
    untracked.unlink()
    _fixture_git(checkout, "checkout", "--", "intern/cycles/scene/toy_nodes.cpp")
    assert toy_nodes.read_bytes() == NODES.encode("utf-8").replace(b"\n", b"\r\n")
    assert vs.check_fragments(manifest, checkouts) == []
    vs.sync_fragments(manifest, checkouts)
    assert path.read_bytes() == original


def test_the_committed_line_fails_sync_and_check(tmp_path: Path) -> None:
    """Step 6's outcomes, reached by committing the changed line and pinning that commit.

    A committed change is in the pinned commit, so the extraction gives the new text: sync refuses
    to write it, and the --upstream check names the fragment. Both outcomes are step 6's.
    """
    manifest, checkouts = _tree(tmp_path)
    name = "scene/toy_nodes_cpp/member/ToyNode.compile-SVMCompiler_compiler"
    vs.add_fragments(
        manifest,
        checkouts,
        "cycles",
        "scene/toy_nodes.cpp",
        "member",
        ["ToyNode::compile"],
        params="SVMCompiler &compiler",
    )
    path = manifest.parent / "fragments" / f"{name}.inc"
    original = path.read_bytes()
    toy_nodes = checkouts["cycles"] / "intern" / "cycles" / "scene" / "toy_nodes.cpp"
    toy_nodes.write_bytes(toy_nodes.read_bytes().replace(b"toy_helper(1)", b"toy_helper(2)", 1))
    commit = _commit(checkouts["cycles"], "changed line")
    pinned = vs.load_manifest(manifest).upstreams["cycles"]
    changed = manifest.parent / "VENDORED.changed.toml"
    changed.write_bytes(
        manifest.read_bytes().replace(
            f'commit = "{pinned.commit}"'.encode(),
            f'commit = "{commit}"'.encode(),
        )
    )
    assert vs.load_manifest(changed).upstreams["cycles"].commit == commit
    with pytest.raises(vs.FragmentError) as raised:
        vs.sync_fragments(changed, checkouts)
    assert name in str(raised.value)
    assert path.read_bytes() == original
    problems = vs.check_fragments(changed, checkouts)
    assert any(name in problem for problem in problems)


@pytest.mark.parametrize("command", ["add", "sync", "check"])
def test_a_checkout_off_its_pin_is_refused(tmp_path: Path, command: str) -> None:
    """A checkout whose HEAD is a later commit is refused, and nothing is written."""
    checkout, pinned = _fixture_checkout(tmp_path)
    manifest, checkouts, _ = _pinned(tmp_path, pinned)
    name = "scene/toy_nodes_cpp/member/ToyNode.attributes"
    vs.add_fragments(
        manifest, checkouts, "cycles", "scene/toy_nodes.cpp", "member", ["ToyNode::attributes"]
    )
    manifest_before = manifest.read_bytes()
    fragment = manifest.parent / "fragments" / f"{name}.inc"
    fragment_before = fragment.read_bytes()
    # A later commit: the checkout's HEAD adds a file that the pin does not have.
    later = checkout / "intern" / "cycles" / "util" / "c.h"
    later.parent.mkdir(parents=True)
    later.write_bytes(b"#define C 1\n")
    head = _commit(checkout, "off the pin")
    assert head != pinned
    expected = f"{checkout} is at {head}, not the pinned {pinned}; delete it and rerun fetch"
    if command == "add":
        with pytest.raises(vs.FragmentError) as raised:
            vs.add_fragments(
                manifest, checkouts, "cycles", "scene/toy_nodes.cpp", "member", ["ToyNode::compile"]
            )
        assert str(raised.value) == expected
    elif command == "sync":
        with pytest.raises(vs.FragmentError) as raised:
            vs.sync_fragments(manifest, checkouts)
        assert str(raised.value) == expected
    else:
        # check_fragments collects problems instead of raising, and the pin's text is one.
        assert vs.check_fragments(manifest, checkouts) == [f"{name}: {expected}"]
    assert manifest.read_bytes() == manifest_before
    assert fragment.read_bytes() == fragment_before
    new_fragment = manifest.parent / "fragments" / "scene/toy_nodes_cpp/member/ToyNode.compile.inc"
    assert not new_fragment.exists()


@pytest.mark.parametrize("kind", ["svm_case", "node_define", "define"])
def test_params_is_only_for_member_and_function(tmp_path: Path, kind: str) -> None:
    """`params` on an svm_case, node_define or define entry is an unexpected key (A2).

    The same entry without `params` is valid, so the refusal is about that key alone.
    """
    anchors = {
        "svm_case": ("kernel/svm/toy.h", "NODE_END"),
        "node_define": ("scene/toy_nodes.cpp", "ToyNode"),
        "define": ("scene/toy_nodes.cpp", "TOY_MAPPING_DEFINE"),
    }
    upstream_path, anchor = anchors[kind]
    manifest, checkouts = _tree(tmp_path)
    assert vs.add_fragments(manifest, checkouts, "cycles", upstream_path, kind, [anchor])
    good = manifest.read_bytes()
    assert vs.render_manifest(vs.load_manifest(manifest)) == good.decode("utf-8")
    bad = manifest.parent / "VENDORED.bad.toml"
    bad.write_bytes(good.replace(b'kind = "', b'params = "x"\nkind = "', 1))
    with pytest.raises(vs.FragmentError, match=r"unexpected \['params'\]"):
        vs.load_manifest(bad)
    loaded = vs.load_manifest(manifest)
    broken = vs.Manifest(loaded.upstreams, loaded.entries, [{**loaded.fragments[0], "params": "x"}])
    with pytest.raises(vs.FragmentError, match=r"unexpected \['params'\]"):
        vs.check_fragment_rules(broken)


def test_a_function_with_params_round_trips(tmp_path: Path) -> None:
    """A `function` entry may carry `params`, and its name has the -<params> suffix (A6)."""
    manifest, checkouts = _tree(tmp_path)
    suffixed = "scene/toy_nodes_cpp/function/toy_helper-int_a"
    assert vs.add_fragments(
        manifest,
        checkouts,
        "cycles",
        "scene/toy_nodes.cpp",
        "function",
        ["toy_helper"],
        params="int a",
    ) == [suffixed]
    assert vs.check_fragments(manifest, checkouts) == []
    text = _lines(NODES, 25, 28).encode("utf-8")
    assert (manifest.parent / "fragments" / f"{suffixed}.inc").read_bytes() == text
    with manifest.open("rb") as handle:
        data = tomllib.load(handle)
    assert data["fragment"] == [
        {
            "name": suffixed,
            "upstream": "cycles",
            "upstream_path": "scene/toy_nodes.cpp",
            "kind": "function",
            "anchor": "toy_helper",
            "params": "int a",
            "upstream_lines": [25, 28],
            "sha256": hashlib.sha256(text).hexdigest(),
        }
    ]
    # load_manifest runs the rules, and the writer reproduces the file it read.
    assert vs.render_manifest(vs.load_manifest(manifest)) == manifest.read_bytes().decode("utf-8")


# A value that the cases below delete the key of, to reach the "missing key" branch.
_DROP = "<drop this key>"

# One valid [[fragment]] entry per kind, in the fixture upstream, of the shapes that
# test_a_function_with_params_round_trips and test_manifest_round_trip write.
# test_each_fragment_rule_refuses_its_own_violation starts each case from one of these and changes
# exactly one thing, so each case reaches one branch of the rules and nothing else.
BASE_ENTRIES: dict[str, dict[str, object]] = {
    "function": {
        "name": "scene/toy_nodes_cpp/function/toy_helper-int_a",
        "upstream": "cycles",
        "upstream_path": "scene/toy_nodes.cpp",
        "kind": "function",
        "anchor": "toy_helper",
        "params": "int a",
        "upstream_lines": [25, 28],
        "sha256": "00e2df1ced6b49578e9c11a1c776543756a4355a24e47102dca72190bfdeeba8",
    },
    "member": {
        "name": "scene/toy_nodes_cpp/member/ToyNode.attributes",
        "upstream": "cycles",
        "upstream_path": "scene/toy_nodes.cpp",
        "kind": "member",
        "anchor": "ToyNode::attributes",
        "upstream_lines": [50, 57],
        "sha256": "00e2df1ced6b49578e9c11a1c776543756a4355a24e47102dca72190bfdeeba8",
    },
    "svm_case": {
        "name": "kernel/svm/toy_h/svm_case/NODE_END",
        "upstream": "cycles",
        "upstream_path": "kernel/svm/toy.h",
        "kind": "svm_case",
        "anchor": "NODE_END",
        "upstream_lines": [7, 8],
        "sha256": "00e2df1ced6b49578e9c11a1c776543756a4355a24e47102dca72190bfdeeba8",
    },
    "node_define": {
        "name": "scene/toy_nodes_cpp/node_define/ToyNode",
        "upstream": "cycles",
        "upstream_path": "scene/toy_nodes.cpp",
        "kind": "node_define",
        "anchor": "ToyNode",
        "upstream_lines": [7, 14],
        "sha256": "00e2df1ced6b49578e9c11a1c776543756a4355a24e47102dca72190bfdeeba8",
    },
    "define": {
        "name": "scene/toy_nodes_cpp/define/TOY_MAPPING_DEFINE",
        "upstream": "cycles",
        "upstream_path": "scene/toy_nodes.cpp",
        "kind": "define",
        "anchor": "TOY_MAPPING_DEFINE",
        "upstream_lines": [3, 5],
        "sha256": "00e2df1ced6b49578e9c11a1c776543756a4355a24e47102dca72190bfdeeba8",
    },
    "span": {
        "name": "scene/toy_nodes_cpp/span/toy_head",
        "upstream": "cycles",
        "upstream_path": "scene/toy_nodes.cpp",
        "kind": "span",
        "id": "toy_head",
        "begin": "NODE_DEFINE(ToyNode)",
        "end": "{",
        "upstream_lines": [7, 8],
        "sha256": "00e2df1ced6b49578e9c11a1c776543756a4355a24e47102dca72190bfdeeba8",
    },
}

# The second [[fragment]] table of the cases that need one: a valid function entry of the same
# file with another `params`, so its name and its lines differ from the base's.
SECOND_ENTRY: dict[str, object] = {
    **BASE_ENTRIES["function"],
    "name": "scene/toy_nodes_cpp/function/toy_helper-int_b",
    "params": "int b",
    "upstream_lines": [29, 30],
}

# A vendored-whole [[file]] entry for the base entry's file, for the "vendored whole and
# fragmented" branch. check_fragment_rules does not look at the hashes.
WHOLE_ENTRY = vs.Entry("cycles", "scene/toy_nodes.cpp", "scene/toy_nodes.cpp")

# test_each_fragment_rule_refuses_its_own_violation's cases: the branch's label, the base entry's
# kind, the one change (a _DROP value deletes that key), and a phrase of that branch's message.
RULE_VIOLATIONS: tuple[tuple[str, str, dict[str, object], str], ...] = (
    ("unknown kind", "function", {"kind": "macro"}, "unknown kind"),
    ("kind that is not a string", "function", {"kind": 1}, "unknown kind"),
    ("missing key for span", "span", {"end": _DROP}, "missing"),
    ("unexpected key for span", "span", {"anchor": "x"}, "unexpected"),
    ("missing key for a function", "function", {"anchor": _DROP}, "missing"),
    ("unexpected key for a function", "function", {"id": "x"}, "unexpected"),
    ("a character outside printable ASCII", "function", {"params": "int\ta"}, "printable ASCII"),
    ("an unknown upstream", "function", {"upstream": "nope"}, "is not in VENDORED.toml"),
    (
        "a non-canonical upstream_path",
        "function",
        {"upstream_path": "./scene/toy_nodes.cpp"},
        "canonical",
    ),
    ("an invalid span id", "span", {"id": "a b"}, "not a valid id"),
    ("an empty begin", "span", {"begin": ""}, "begin must not be empty"),
    ("an empty end", "span", {"end": ""}, "end must not be empty"),
    (
        "an invalid anchor for a function",
        "function",
        {"anchor": "toy helper"},
        "not a valid function",
    ),
    ("an invalid anchor for a member", "member", {"anchor": "toy_helper"}, "not a valid member"),
    (
        "upstream_lines is not a list of two integers",
        "function",
        {"upstream_lines": [25]},
        "two integers",
    ),
    ("upstream_lines holds a bool", "function", {"upstream_lines": [True, 28]}, "two integers"),
    (
        "upstream_lines breaks 1 <= first <= last",
        "function",
        {"upstream_lines": [28, 25]},
        "1 <= first <= last",
    ),
    (
        "a sha256 that is not 64 lowercase hex",
        "function",
        {"sha256": "AB" * 32},
        "SHA-256 hex digest",
    ),
    (
        "a name other than the one the fields give",
        "function",
        {"name": "scene/toy_nodes_cpp/function/other"},
        "the name its fields give",
    ),
)


def _fixture_pin(tmp_path: Path) -> tuple[Path, str]:
    """A VENDORED.toml with TEST_MANIFEST's pin and no fragments, and the fixture checkout's commit.

    The manifest is written beside a one-commit checkout of the two source files, so every base
    entry above describes a real fragment of the pinned commit.
    """
    checkout, commit = _fixture_checkout(tmp_path)
    manifest = tmp_path / "tp" / "VENDORED.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(TEST_MANIFEST.format(commit=commit).encode("utf-8"))
    return manifest, commit


def _rules_manifest(
    manifest: Path, fragments: list[object], entries: list[vs.Entry] | None = None
) -> vs.Manifest:
    """The manifest at path, with these [[fragment]] tables and [[file]] entries."""
    loaded = vs.load_manifest(manifest)
    return vs.Manifest(
        loaded.upstreams,
        loaded.entries if entries is None else entries,
        fragments,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize("kind", sorted(BASE_ENTRIES))
def test_every_base_entry_passes_the_rules(tmp_path: Path, kind: str) -> None:
    """Each base entry is valid, so a case that changes one thing tests that one thing."""
    manifest, _ = _fixture_pin(tmp_path)
    vs.check_fragment_rules(_rules_manifest(manifest, [dict(BASE_ENTRIES[kind])]))


@pytest.mark.parametrize(
    ("label", "base", "change", "message"),
    RULE_VIOLATIONS,
    ids=[label for label, _, _, _ in RULE_VIOLATIONS],
)
def test_each_fragment_rule_refuses_its_own_violation(
    tmp_path: Path, label: str, base: str, change: dict[str, object], message: str
) -> None:
    """One change to a valid entry reaches one branch of the rules, with that branch's message."""
    del label
    manifest, _ = _fixture_pin(tmp_path)
    entry = {
        key: value for key, value in {**BASE_ENTRIES[base], **change}.items() if value is not _DROP
    }
    with pytest.raises(vs.FragmentError, match=re.escape(message)):
        vs.check_fragment_rules(_rules_manifest(manifest, [entry]))


def test_a_non_table_fragment_entry_is_refused(tmp_path: Path) -> None:
    """A [[fragment]] entry that is not a table is refused, before any of its keys are read."""
    manifest, _ = _fixture_pin(tmp_path)
    with pytest.raises(vs.FragmentError, match=re.escape("must be a table")):
        vs.check_fragment_rules(_rules_manifest(manifest, ["not a table"]))


def test_a_name_used_twice_is_refused(tmp_path: Path) -> None:
    """Two entries with the same name are refused, whatever else differs between them."""
    manifest, _ = _fixture_pin(tmp_path)
    entry = dict(BASE_ENTRIES["function"])
    with pytest.raises(vs.FragmentError, match="the name is used twice"):
        vs.check_fragment_rules(_rules_manifest(manifest, [entry, dict(entry)]))


def test_a_file_vendored_whole_and_fragmented_is_refused(tmp_path: Path) -> None:
    """An upstream file that is both a [[file]] and a [[fragment]] source is refused."""
    manifest, _ = _fixture_pin(tmp_path)
    loaded = vs.load_manifest(manifest)
    with pytest.raises(vs.FragmentError, match="vendored whole and fragmented"):
        vs.check_fragment_rules(
            _rules_manifest(
                manifest,
                [dict(BASE_ENTRIES["function"])],
                [*loaded.entries, WHOLE_ENTRY],
            )
        )


@pytest.mark.parametrize("lines", [[26, 28], [28, 30]], ids=["overlapping", "sharing a line"])
def test_two_overlapping_ranges_are_refused(tmp_path: Path, lines: list[int]) -> None:
    """Two ranges of one upstream file that overlap, or share one line, are refused."""
    manifest, _ = _fixture_pin(tmp_path)
    second = {**SECOND_ENTRY, "upstream_lines": lines}
    with pytest.raises(vs.FragmentError, match="overlap"):
        vs.check_fragment_rules(_rules_manifest(manifest, [dict(BASE_ENTRIES["function"]), second]))


def test_abutting_and_separate_ranges_are_accepted(tmp_path: Path) -> None:
    """`[a, b]` next to `[b + 1, c]` is fine, and equal ranges in two different files are fine."""
    manifest, _ = _fixture_pin(tmp_path)
    first = dict(BASE_ENTRIES["function"])
    # SECOND_ENTRY is [29, 30]: the line after the base's last one.
    vs.check_fragment_rules(_rules_manifest(manifest, [first, dict(SECOND_ENTRY)]))
    other_file = {
        **first,
        "name": "kernel/svm/toy_h/function/toy_helper-int_a",
        "upstream_path": "kernel/svm/toy.h",
    }
    vs.check_fragment_rules(_rules_manifest(manifest, [first, other_file]))


def test_a_git_failure_is_not_reported_as_a_missing_path(tmp_path: Path) -> None:
    """A blob deleted from .git/objects is reported as git's failure, not as a path upstream lacks.

    TQ.3 F27: every git failure used to be reported as "<path> is not a file in upstream ...". A
    path the commit does not have is still that message; a broken object store is git's own.
    """
    manifest, checkouts = _tree(tmp_path)
    commit = vs.load_manifest(manifest).upstreams["cycles"].commit
    name = "scene/toy_nodes_cpp/function/toy_helper"
    assert vs.add_fragments(
        manifest, checkouts, "cycles", "scene/toy_nodes.cpp", "function", ["toy_helper"]
    ) == [name]
    # A path the commit does not have keeps the "not a file" message, with its path and commit.
    with pytest.raises(vs.FragmentError) as missing:
        vs.add_fragments(manifest, checkouts, "cycles", "scene/none.cpp", "function", ["f"])
    assert str(missing.value) == (
        f"cycles:scene/none.cpp at {commit}: scene/none.cpp is not a file in upstream cycles"
        f" at {commit}"
    )
    # Delete the blob of scene/toy_nodes.cpp from the checkout's object store: the commit still
    # names the path, but git cannot read it. The error is git's, not "not a file in upstream".
    checkout = checkouts["cycles"]
    oid = _fixture_git(checkout, "rev-parse", f"{commit}:intern/cycles/scene/toy_nodes.cpp")
    (checkout / ".git" / "objects" / oid[:2] / oid[2:]).unlink()
    with pytest.raises(vs.FragmentError) as broken:
        vs.add_fragments(
            manifest, checkouts, "cycles", "scene/toy_nodes.cpp", "function", ["toy_helper"]
        )
    message = str(broken.value)
    assert message.startswith(f"cycles:scene/toy_nodes.cpp at {commit}: ")
    assert "is not a file in upstream" not in message
    assert "git cat-file" in message and oid in message
    # check_fragments collects the same message rather than reporting a missing path.
    problems = vs.check_fragments(manifest, checkouts)
    assert problems == [f"{name}: {message}"]


def test_committed_manifest_survives_the_writer() -> None:
    """The committed VENDORED.toml is what every later sync, add and remove writes back."""
    path = REPO_ROOT / "third_party" / "cycles" / "VENDORED.toml"
    assert vs.render_manifest(vs.load_manifest(path)) == path.read_bytes().decode("utf-8")
