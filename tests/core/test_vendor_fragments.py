"""The fragment grammar of tools/vendor_sync.py, and the [[fragment]] entries of VENDORED.toml.

Every test but the last runs the tool's Python API on canned sources, so it needs no network and
no .cache/vendor checkout. The last one checks that the committed VENDORED.toml survives the
tool's own writer, which is what every later `sync`, `add` and `remove` writes back.
"""

import hashlib
import importlib.util
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
# Both hashes are of "#define WHOLE 1\n", the content of the checkout's scene/whole.h.
TEST_MANIFEST = r"""[upstream.cycles]
repo = "https://github.com/blender/blender.git"
tag = "v5.2.2"
commit = "d13f752e3b9c4f8c261cda552b1021f8bcc0382c"
root = "intern/cycles"

[[file]]
upstream = "cycles"
upstream_path = "scene/whole.h"
dest = "scene/whole.h"
upstream_sha256 = "aa420eefe02d5613df36cba6caf1a95e924d852201e3db66f6ce070b58b3460f"
sha256 = "aa420eefe02d5613df36cba6caf1a95e924d852201e3db66f6ce070b58b3460f"
patched = false
"""

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
    """A checkout with CASES, NODES and whole.h, and a manifest that vendors whole.h only."""
    checkout = tmp_path / "co"
    for relative, text in (
        ("intern/cycles/kernel/svm/toy.h", CASES),
        ("intern/cycles/scene/toy_nodes.cpp", NODES),
        ("intern/cycles/scene/whole.h", "#define WHOLE 1\n"),
    ):
        path = checkout / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    manifest = tmp_path / "tp" / "VENDORED.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(TEST_MANIFEST.encode("utf-8"))
    return manifest, {"cycles": checkout}


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
    assert vs.render_manifest(vs.load_manifest(manifest)) == manifest.read_text(encoding="utf-8")

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
    assert vs.render_manifest(vs.load_manifest(manifest)) == manifest.read_text(encoding="utf-8")
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

    # 6. A changed line in the checkout fails sync and the --upstream check, and writes no byte.
    toy_nodes = checkouts["cycles"] / "intern" / "cycles" / "scene" / "toy_nodes.cpp"
    assert toy_nodes.read_text(encoding="utf-8").split("\n")[31].strip() == (
        "compiler.add_node(this, NODE_MATH, SVMNodeMath{.math_type = toy_helper(1)});"
    )
    toy_nodes.write_text(
        toy_nodes.read_text(encoding="utf-8").replace("toy_helper(1)", "toy_helper(2)", 1),
        encoding="utf-8",
    )
    with pytest.raises(vs.FragmentError) as raised:
        vs.sync_fragments(manifest, checkouts)
    assert name in str(raised.value)
    assert path.read_bytes() == original
    problems = vs.check_fragments(manifest, checkouts)
    assert any(name in problem for problem in problems)
    toy_nodes.write_text(
        toy_nodes.read_text(encoding="utf-8").replace("toy_helper(2)", "toy_helper(1)", 1),
        encoding="utf-8",
    )

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
    assert vs.render_manifest(vs.load_manifest(manifest)) == manifest.read_text(encoding="utf-8")
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


def test_committed_manifest_survives_the_writer() -> None:
    """The committed VENDORED.toml is what every later sync, add and remove writes back."""
    path = REPO_ROOT / "third_party" / "cycles" / "VENDORED.toml"
    assert vs.render_manifest(vs.load_manifest(path)) == path.read_text(encoding="utf-8")
