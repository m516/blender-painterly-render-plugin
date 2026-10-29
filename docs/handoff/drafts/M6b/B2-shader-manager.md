# B2 — The shader manager in `PainterlyScene::device_update`
Milestone: M6b · Depends on: B1 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B2" (lines 114-135) and its section 1 decisions 3 and 4
(lines 30-51), per that brief's section 4 (lines 303-324). Code facts are `docs/handoff/drafts/M6b/FACTS.md` §3, re-read
at this clone's HEAD in the files cited below. Every number this card states is derived by the script in step 1, whose
output the card quotes.

## Goal

`PainterlyScene` owns Cycles' host scene and runs Cycles' SVM shader manager on it, so a node material becomes a compiled
SVM program with a jump-table entry and a `KernelShader`, and its `KernelPainterlyMaterial` carries the Cycles shader id
instead of an offset:

- `PainterlyScene` holds `std::unique_ptr<Scene> cycles_` (the shim `Scene`, `src/cycles/shim/scene/scene.h:45-63`) with
  `shader_manager` a `PainterlyShaderManager`, its `shaders` and its `dscene` (BRIEF.md:38-42).
- `PainterlyScene::add_shader(std::unique_ptr<ShaderGraph>) -> int` returns a shader index, and
  `add_node_material(int shader) -> int` returns a material index; `add_node_material` calls `Shader::reference()`,
  because Cycles compiles only a referenced shader (`SVMCompiler.compile_type.inc:69`; BRIEF.md:47-48).
- `KernelPainterlyMaterial::svm_offset` becomes `int cycles_shader`, the Cycles shader id (`sd->shader`), or -1 for a
  constant material (BRIEF.md:30-34). It is not an offset: the SVM starts at word
  `id * (1 + sizeof(SVMNodeShaderJump) / sizeof(uint))` of `svm_nodes`
  (`fragments/kernel/svm/svm_h/span/svm_eval_nodes_head.inc:13`; `src/painterly/scene/svm/shader_manager.h:181`, `:202`).
- `PainterlyScene::device_update` stays `const` and, in T6.7's order, runs `device_update_pre`, `device_update_post` and
  `device_update_lookup_tables` (BRIEF.md:43-44), which compiles every referenced shader, fills the jump table,
  `KernelShader::flags` and the lookup tables, sets each node material's `cycles_shader` to its shader id, and binds
  `svm_nodes`, `shaders`, `lookup_table` and `KernelData` into `cycles_globals()` (BRIEF.md:117-119).
- TQ.4 F5 (`docs/audits/TQ.4.md:47`): `PainterlyShaderManager` gets one public entry point that runs the three steps in
  order; the painterly steps become protected; a null graph and a shader whose `id` is not its index are errors, not
  asserts; and binding happens after the last `add_table`, because `LookupTables::add_table` resizes `lookup_table`
  (`fragments/scene/tables_cpp/member/LookupTables.add_table.inc:25`).
- TQ.4 F4 (`docs/audits/TQ.4.md:46`): `device_update_common` also writes the `KernelData` members that the vendored SVM
  reads and that Cycles without OCIO sets: `film.is_rec709`, the `rec709_to_*` rows, `xyz_to_*` and
  `max_closures = MAX_CLOSURE` (BRIEF.md:123-126).
- The strong guarantee of `src/painterly/scene/device_scene.cpp:94-97` survives: the shader manager writes only into the
  host scene's scratch `Scene::dscene`, and the device scene takes that scratch's arrays by pointer at the existing
  commit point (`:289-303`) (BRIEF.md:49-51).

A scene of constant materials is unchanged: every material keeps `cycles_shader == -1`, no shader is compiled, and the
three Cycles arrays stay empty. T3.16's bit-identical parity test is the check.

## Read first

- `CLAUDE.md` rules 1, 2 and 3; `AGENTS.md` "Expected values are evidence"; `docs/architecture.md:57-70` ("Dependency
  direction": `PainterlyScene::device_update()` is the only bridge, and `painterly/kernel/` never includes
  `painterly/scene/`).
- `docs/handoff/drafts/M6b/BRIEF.md` lines 30-51 (decisions 3 and 4), 114-135 (this card's mandate) and 303-324 (how the
  cards are drafted).
- The CONTRACT header `src/painterly/kernel/types.h` (read it, never edit it: `:4` is `CONTRACT: Opus-owned`):
  `KernelPainterlyLobe` `:90-94`, `KernelPainterlyMaterial` `:101-106`, `KernelPainterlyData` `:158-162`.
- `src/painterly/scene/scene.h` (`:34-112`: the lists, `add_material` `:52`, `set_background` `:89`, `device_update`
  `:103`, the private members `:106-112`) and `src/painterly/scene/scene.cpp` (`clear` `:21-33`, `add_material`
  `:35-44`).
- `src/painterly/scene/material.h:17-47` (`PainterlyMaterial` and its `validate()`), and `src/painterly/scene/device_scene.h`
  (`:23-67`) with `src/painterly/scene/device_scene.cpp` (`bind_globals` `:68-85`, `globals()` `:87-90`, `device_update`
  `:92-304`, the strong guarantee `:94-97`, the material flattening `:112-123` with `svm_offset = -1` at `:120`, the
  commit `:289-303`).
- `src/painterly/scene/svm/shader_manager.h` in full: `background_shader` `:48`, `device_update_pre` `:52-120`,
  `device_update_post` `:124-127`, `device_free` `:131-136`, `bind_kernel_globals` `:143-152`, `device_update_specific`
  `:156-250` (`device_free` first `:166`, `jump_node_size` `:181`, the jump table `:191-209`, the node copy `:211-219`),
  `device_update_shader` `:236-250` (the `assert(shader->graph)` at `:238`), `device_update_common` `:252-354`
  (`dscene->shaders.clear()` `:257`, the early return `:259-261`, `KernelShader::flags` `:264-323`, the caustics flags
  `:346-347`, `rgb_to_y` `:353`).
- The shim `src/cycles/shim/scene/scene.h` (`DeviceScene` `:31-38`, `Scene` `:45-63`) and `src/cycles/shim/scene/shader.h`
  (`Shader` `:66-161` with `id` `:120` and `reference()` `:150`; `ShaderManager` `:169-228` with
  `device_update_lookup_tables` `:192` and `rgb_to_y` `:205`), and `src/cycles/shim/scene/shader.cpp` (the constructor's
  colour matrix `:60-76`, `device_update_lookup_tables` `:188-206`, `device_free_lookup_tables` `:210-218`).
- The vendored pieces the code ports: `fragments/scene/svm_cpp/member/SVMCompiler.compile.inc:1-63` (the jump node first,
  then the four programs), `SVMCompiler.compile_type.inc:69` (compile only a referenced shader) and `:132-136` (the
  per-type `NODE_END`), `fragments/scene/tables_cpp/member/LookupTables.add_table.inc:9,15-32`,
  `fragments/kernel/svm/svm_h/span/svm_eval_nodes_head.inc:13`, `kernel/svm/node_types.h:24-31` (`SVMNodeShaderJump`),
  `kernel/closure/alloc.h:19-21` (`num_closure_left == 0` drops every closure), `kernel/util/colorspace.h:13-32`
  (`xyz_to_rgb`, `rec709_to_rgb`), `kernel/data_template.h:64-157` (`KernelFilm`, `is_rec709` at `:76`),
  `kernel/types.h:1334-1348` (`KernelTables`), `:1366-1372` (`KernelData::max_closures`), `:829-833` (`MAX_CLOSURE`).
- Upstream Cycles v5.2.2, from the pinned checkout, for the two functions this card ports:
  `intern/cycles/scene/shader.cpp:520-598` (`device_update_pre`), `:600-610` (`device_update_post`), `:612-748`
  (`device_update_common`, the film block at `:737-748`), `:995-1023` (`init_xyz_transforms`, the `lin_rec709_scene`
  branch at `:1001-1007`), `intern/cycles/scene/svm.cpp:57-146` (`device_update_specific`), and
  `intern/cycles/scene/shader.h:180-282` (`ShaderManager`).
- `src/test/cycles_svm_test_support.h` (`painterly_svm_test_shader_data` `:317-331`, `painterly_svm_test_run`
  `:341-353`), `src/test/cycles_svm_test_scene.h` (`surface()` `:104-118`, `background()` `:121-130`),
  `src/test/test_cycles_svm_closures.cpp` (`make_scene` `:47-53`, `compile` `:90-96`, `evaluate` `:119-138`, the lookup
  table case `:281-356`), `src/test/test_cycles_svm_compiler.cpp` (`prepare_unfolded` `:114-124`, `default_shader_flags`
  `:195`), `src/test/test_scene.cpp` (`:438-478` the flattened arrays, `:898-960` the strong guarantee),
  `src/test/CMakeLists.txt` (`:65` `add_test`, `:69-77` the layout probe, `:96-99` T6.8's block).
- `docs/audits/TQ.4.md` findings F4 `:46` and F5 `:47` with their `Evidence` columns; F1 `:43` (asserts are compiled out
  of every build) and F7 `:49` (the copied test helpers), which the steps below lean on.
- The two parity tests this card must keep green unchanged: `tests/core/test_oracle_parity.py` and
  `tests/core/test_triangle_path.py`; and `tests/core/test_api_contract.py`, which must pass because B6 owns the Python
  names.
- `docs/handoff/drafts/M6a/T6.5-svm-compiler.md:144-147` (M6b moves `PainterlyShaderManager` into a library) and
  `T6.7-svm-closures.md:144-149` (the order of the three steps).

## Create

- `src/test/test_cycles_shader_manager.cpp`

## Modify

- `src/painterly/scene/scene.h`: `#include <memory>`; forward declarations of `ShaderGraph` and of the shim `Scene`;
  `PainterlyScene()` and `~PainterlyScene()` declared instead of `= default` (`:44`); the member
  `std::unique_ptr<Scene> cycles_`; `add_shader` and `add_node_material`; the class comment.
- `src/painterly/scene/scene.cpp`: define the constructor (it creates `cycles_` and its `PainterlyShaderManager`) and the
  destructor; `clear()` also empties `cycles_->shaders`; `add_shader` and `add_node_material`.
- `src/painterly/scene/material.h`: `PainterlyMaterial::shader` (`-1` for a constant material) and `validate()`'s rule
  for a node material.
- `src/painterly/scene/device_scene.h`: `#include <memory>`; forward-declare the shim `DeviceScene`; the member
  `std::unique_ptr<DeviceScene> cycles_dscene_`; the accessor `const DeviceScene &cycles_device_scene() const`; the class
  comment.
- `src/painterly/scene/device_scene.cpp`: the constructor allocates `cycles_dscene_`; the material loop writes
  `cycles_shader`; the shader-manager call; the commit steals the three Cycles arrays and the `KernelData` and binds
  `KernelGlobalsCPU`.
- `src/painterly/scene/svm/shader_manager.h`: TQ.4 F5's one public entry point and protected steps, the two error checks,
  and TQ.4 F4's `KernelData` writes in `device_update_common`; drop `final` from the class so a doctest can expose a
  protected step (TQ.3's rule that a guard needs a test).
- `src/cycles/shim/scene/shader.h`: the protected members `xyz_to_r`, `xyz_to_g`, `xyz_to_b`, `rec709_to_r`,
  `rec709_to_g`, `rec709_to_b` (TQ.4 F4's inputs), next to `rgb_to_y` (`:205`).
- `src/cycles/shim/scene/shader.cpp`: the constructor computes them from the matrix at `:60-71`, as upstream's
  `init_xyz_transforms` does (`:1001-1007`, `:1014-1019`).
- `src/test/cycles_svm_test_support.h`: `painterly_svm_test_globals()` and the `KernelGlobalsCPU &` parameter of
  `painterly_svm_test_shader_data` (BRIEF.md:125-126).
- `src/test/cycles_svm_test_scene.h`: `surface()` and `background()` take the `KernelGlobalsCPU &` they pass on.
- `src/test/test_cycles_svm_closures.cpp`, `src/test/test_cycles_svm_compiler.cpp`,
  `src/test/test_cycles_svm_images.cpp`, `src/test/test_cycles_svm_textures.cpp`,
  `src/test/test_cycles_svm_stack_nodes.cpp`: every `KernelGlobalsCPU globals;` becomes
  `KernelGlobalsCPU globals = painterly_svm_test_globals();`, and every helper call passes it.
- `src/test/smallpaint_scene_fixture.h`, `src/test/test_path.cpp`, `src/test/test_scene.cpp`: the renamed field's
  readers.
- `src/test/CMakeLists.txt`: `test_cycles_shader_manager.cpp` in `painterly_tests`.

## Do not touch

- `src/painterly/kernel/types.h` (CONTRACT, `:4`): `cycles_shader` is Opus's and arrives before dispatch (see
  `## Interface`). This card only updates the field's readers (step 2).
- `src/painterly/kernel/globals.h` (CONTRACT, B1's), `src/blender/_painterly.pyi` (CONTRACT, B6's and B10's) and
  `src/blender/python.cpp`: B6 binds `add_shader` and `add_node_material`, so this card adds no Python name and
  `tests/core/test_api_contract.py` must pass unchanged.
- `third_party/cycles/**` (vendored; `tools/vendor_sync.py` only), `src/cycles/svm_nodes.toml`,
  `src/cycles/fragment_units.toml`, `src/cycles/CMakeLists.txt`, `src/painterly/scene/CMakeLists.txt`,
  `src/painterly/kernel/CMakeLists.txt`: B1 lands every build change this card needs (`ccl=painterly` PRIVATE on
  `painterly_scene` and `painterly_tests`, `cycles_scene` on `painterly_scene`, `cycles_svm` on `painterly_kernel`).
- `src/cycles/shim/kernel/**` and the vendored `kernel/` headers: this card ports Cycles' setup, it vendors nothing.
- `src/test/cycles_kernel_layout_probe.h`, `src/test/cycles_kernel_layout_probe.cpp`,
  `src/test/test_cycles_kernel_layout.cpp` (T6.1's, with B1's comparison) and `src/test/test_cycles_globals.cpp` (B1's
  doctests, which must pass unchanged: a constant-material scene leaves the three Cycles arrays empty).
- `tests/core/test_oracle_parity.py`, `tests/core/test_triangle_path.py`, `tests/core/test_api_contract.py`: they must
  pass unchanged, so not one line of any may move.
- `docs/spec.md`, `docs/architecture.md`, `Makefile`, `pyproject.toml`, `.github/workflows/**`.

## Interface

CONTRACT (Opus writes this before dispatch): `src/painterly/kernel/types.h:101-106` replaces `int svm_offset;` with
BRIEF.md:30-34's declaration and comment, exactly:

    int cycles_shader; /* The Cycles shader id, `sd->shader`, or -1 for constant lobes, today's path. It is not an
                          offset: the SVM starts at word `id * (1 + sizeof(SVMNodeShaderJump) / sizeof(uint))` of
                          `svm_nodes` (svm_eval_nodes_head.inc:13; shader_manager.h:181, :202). */

Its neighbours keep their comments, including `num_lobes`'s `/* >= 1 */`, which then states the constant material's
rule; `## Open for Opus` item 1 asks whether Opus wants that comment widened for a node material, whose `num_lobes` is 0.

Not CONTRACT, and what later cards may rely on (B4, B6 and B8 read them; nothing else):

    /* A shader graph, compiled at the next device_update (BRIEF.md section 2, "B2"). Returns the shader index, which is
     * also Cycles' shader id (sd->shader). The scene takes ownership of the graph. */
    int add_shader(std::unique_ptr<ShaderGraph> graph);

    /* A material whose lobes and emission come from shader `shader` per hit (BRIEF.md section 1, decision 3). Calls
     * Shader::reference(), because Cycles compiles only a referenced shader. Returns the material index. */
    int add_node_material(int shader);

    /* The Cycles host scene this object owns: its shader manager, its shaders and its dscene. Valid while this object
     * lives. */
    const DeviceScene &cycles_device_scene() const;          // src/painterly/scene/device_scene.h

    /* TQ.4 F5: the one entry point. Runs device_update_pre, device_update_post and device_update_lookup_tables in that
     * order and throws std::runtime_error for a shader without a graph or with an id that is not its index. The caller
     * binds afterwards (PainterlyShaderManager::bind_kernel_globals), never this function: add_table resizes
     * lookup_table. */
    void device_update(DeviceScene *dscene, Scene *scene, Progress &progress);   // PainterlyShaderManager

and, in `src/painterly/scene/material.h`,

    /* The shader graph of a node material (an index into PainterlyScene::add_shader's list), or -1 for a constant
     * material whose lobes are the ones in `lobes`. */
    int shader = -1;

## Steps

1. Preconditions, and the derivation of every number below. Each must hold; otherwise stop, commit nothing and report
   what you saw.
   - B1 has landed: `grep -c 'KernelGlobalsCPU \*cycles' src/painterly/kernel/globals.h` prints `1`, and
     `grep -c 'cycles_globals' src/painterly/scene/device_scene.h` prints at least `1`. Without B1 there is no
     `cycles_globals()` to bind, and the targets this card's new include closure reaches have no `__MAX_CLOSURE__`.
   - The CONTRACT of `## Interface` is present: `grep -c 'int cycles_shader;' src/painterly/kernel/types.h` prints `1`
     and `grep -c 'svm_offset' src/painterly/kernel/types.h` prints `0`. If not, the contract has not arrived: stop and
     report (CLAUDE.md rule 1; the field is Opus's).
   - The tree is the one this card was written against: `grep -c 'void device_update_common(Device \* /\*device\*/'
     src/painterly/scene/svm/shader_manager.h` prints `1`, and `grep -c 'assert(shader->graph)'
     src/painterly/scene/svm/shader_manager.h` prints `1`.
   - No production source compiles the shader manager yet: `grep -c 'shader_manager.h'
     src/painterly/scene/device_scene.cpp` prints `0`.
   - Every number this card quotes. Write the block below to `.cache/b2-derive.py` (git-ignored: `:5` of `.gitignore`)
     and run it from the repository root:

     ```
     .venv/bin/python -I .cache/b2-derive.py
     ```

     ```python
     """Every number card B2 states, derived from this checkout. Run from the repository root:
         .venv/bin/python -I .cache/b2-derive.py
     """
     import pathlib
     import re

     root = pathlib.Path(".")


     def read(path):
         return (root / path).read_text(encoding="utf-8")


     def hits(path, needle, skip=()):
         """1-based line numbers of `path` whose text contains `needle`, minus comment lines."""
         return [i for i, line in enumerate(read(path).splitlines(), 1)
                 if needle in line and not line.lstrip().startswith(("*", "//"))
                 and not any(k in line for k in skip)]


     # 1. The lookup-table offsets. LookupTables::add_table places every table at the next free
     # multiple of TABLE_CHUNK_SIZE (fragments/scene/tables_cpp/member/LookupTables.add_table.inc:9,
     # 15-32), in the order ShaderManager::device_update_lookup_tables adds them
     # (src/cycles/shim/scene/shader.cpp:192-205).
     chunk = int(re.search(r"TABLE_CHUNK_SIZE = (\d+)",
                           read("third_party/cycles/scene/tables.h")).group(1))
     thin = int(re.search(r"#define THIN_FILM_TABLE_SIZE (\d+)",
                          read("third_party/cycles/kernel/types.h")).group(1))
     tables = read("third_party/cycles/scene/shader.tables")
     size = {n: int(c) for n, c in re.findall(r"static const float (table_\w+)\[(\d+)\]", tables)}
     size["thin_film_table"] = 6 * thin  # shim shader.cpp:141, resize(6 * THIN_FILM_TABLE_SIZE)
     order = ["table_ggx_E", "table_ggx_Eavg", "table_ggx_glass_E", "table_ggx_glass_Eavg",
              "table_ggx_glass_inv_E", "table_ggx_glass_inv_Eavg", "table_sheen_ltc",
              "table_ggx_gen_schlick_ior_s", "table_ggx_gen_schlick_s", "thin_film_table"]
     offset, offsets = 0, []
     for name in order:
         offsets.append(offset)
         offset += -(-size[name] // chunk) * chunk
     print("1 table sizes, in upload order:", [size[n] for n in order])
     print("1 offsets:", offsets, "| lookup_table width:", offset)

     # 2. jump_node_size = 1 + sizeof(SVMNodeShaderJump) / sizeof(int) (shader_manager.h:181);
     # SVMNodeShaderJump is three ints (kernel/svm/node_types.h:24-31).
     print("2 jump_node_size:", 1 + 3)

     # 3. doctest case counts. doctest v2.4.11 wildcmp() (doctest.h:4113-4124) compares a literal
     # prefix and stops at '*', so 'a:b*' selects only names that begin with 'a:b'.
     cases = []
     for path in sorted((root / "src/test").glob("*.cpp")):
         rel = str(path.relative_to(root))
         cases += [(rel, n) for n in re.findall(r'TEST_CASE\(\s*"([^"]*)"', read(rel))]
     new = ["cycles shader manager: " + s for s in (
         "a node material gets its shader id and its jump entry",
         "the lookup tables are uploaded where KernelTables points",
         "two node materials share one jump table",
         "a throwing device update leaves the previous device scene bit for bit unchanged",
         "a scene of constant materials compiles no shader",
         "a null graph or a wrong shader id is an error, not an assert",
         "the one entry point runs pre, post and the table upload in order",
         "KernelData carries the film and closure members the SVM reads",
         "the closure budget comes from kernel_data.max_closures")]


     def wildcmp(s, w):
         i = 0
         while i < len(s) and i < len(w) and w[i] != "*":
             if w[i] != s[i] and w[i] != "?":
                 return False
             i += 1
         return i == len(s) if i == len(w) else w[i] == "*"


     print("3 TEST_CASEs in src/test:", len(cases), "| this card's:", len(new))
     for pat in ("cycles shader manager:*", "cycles svm*", "painterly scene:*",
                 "cycles kernel layout*", "cycles kernel globals*"):
         print("3 %-24s -> %d" % (pat, sum(1 for _, n in cases if wildcmp(n, pat))
                                   + sum(1 for n in new if wildcmp(n, pat))))
     print("3 'painterly scene:' names the filter skips:",
           [(f, n) for f, n in cases
            if n.startswith("painterly scene") and not wildcmp(n, "painterly scene:*")])
     print("3 'painterly scene:' per file:",
           {f: sum(1 for g, n in cases if g == f and n.startswith("painterly scene:"))
            for f in sorted({f for f, n in cases if n.startswith("painterly scene:")})})

     # 4. The field rename (BRIEF.md:30-34): every reader of the old name.
     field = []
     for path in sorted(list((root / "src").rglob("*.h")) + list((root / "src").rglob("*.cpp"))):
         rel = str(path.relative_to(root))
         field += [(rel, i) for i in hits(rel, "svm_offset")]
     print("4 svm_offset:", len(field), "lines in", len({p for p, _ in field}), "files")
     print("4 per file:", {p: sorted(i for q, i in field if q == p) for p in sorted({p for p, _ in field})})

     # 5. The three manager steps and their call sites, which the entry point replaces.
     test_sources = [str(p.relative_to(root)) for p in sorted((root / "src/test").iterdir())
                     if p.suffix in (".h", ".cpp")]
     steps = []
     for needle in ("device_update_pre(", "device_update_post(", "device_update_lookup_tables("):
         for path in test_sources:
             steps += [(path, i) for i in hits(path, needle, skip=("void ",))]
     print("5 manager step call sites:", len(steps),
           {p: sorted(i for q, i in steps if q == p) for p in sorted({p for p, _ in steps})})

     # 6. painterly_svm_test_shader_data (BRIEF.md:125-126) and the files that call it.
     helper = []
     for path in test_sources:
         helper += [(path, i) for i in hits(path, "painterly_svm_test_shader_data(",
                                            skip=("inline ShaderData",))]
     print("6 helper call sites:", len(helper), "in", len({p for p, _ in helper}), "files",
           {p: sum(1 for q, _ in helper if q == p) for p in sorted({p for p, _ in helper})})
     sources = sorted({p for p, _ in helper if p.endswith(".cpp")})
     decl = []
     for path in sources:
         decl += [(path, i) for i in hits(path, "KernelGlobalsCPU globals;")]
     print("6 'KernelGlobalsCPU globals;' in those sources:", len(decl), "in", len(sources), "files",
           {p: sum(1 for q, _ in decl if q == p) for p in sources})
     scene_calls = []
     for path in test_sources:
         scene_calls += [(path, i) for i in hits(path, "scene.surface(")
                         + hits(path, "scene.background()")]
     print("6 PainterlySvmTestScene hit calls:", len(scene_calls),
           {p: sorted(i for q, i in scene_calls if q == p) for p in sorted({p for p, _ in scene_calls})})

     # 7. The Python files the acceptance counts.
     for name in ("test_oracle_parity.py", "test_triangle_path.py", "test_api_contract.py"):
         text = read("tests/core/" + name)
         print("7", name, "def test_:", len(re.findall(r"^def (test_\w+)", text, re.M)),
               "| @pytest.mark.slow:", len(re.findall(r"@pytest\.mark\.slow\s*\ndef ", text)),
               "| parametrize:", len(re.findall(r"@pytest\.mark\.parametrize", text)))
     design = len([l for l in re.search(r"DESIGN: tuple\[.*?= \((.*?)\n\)",
                                        read("tests/core/test_oracle_parity.py"), re.S)
                   .group(1).splitlines() if l.strip()])
     configs = len([l for l in re.search(r"CORE_CONFIGS: tuple\[.*?= \((.*?)\n\)",
                                         read("tests/core/test_oracle_parity.py"), re.S)
                    .group(1).splitlines() if l.strip()])
     print("7 DESIGN", design, "x CORE_CONFIGS", configs, "=", design * configs, "parametrized items")
     shim = sorted(p for p in (root / "src/cycles/shim").rglob("*") if p.is_file())
     shim_headers = [p for p in shim if p.suffix == ".h"]
     print("7 shim files", len(shim), "| shim headers", len(shim_headers),
           "| test_shims.py items", 3 + 2 * len(shim) + len(shim_headers),
           "| span items", 1 + len(re.findall(r'^\s+"[0-9a-f]{64}",$',
                                              read("tests/core/test_shim_upstream_copies.py"), re.M)))

     # 8. This card's own path lists, which acceptance 9 expects in git status. The card is the draft
     # until Opus approves it, then docs/tasks/M6b's.
     card = next(str(p) for p in ("docs/handoff/drafts/M6b/B2-shader-manager.md",
                                  "docs/tasks/M6b/B2-shader-manager.md") if (root / p).exists())
     text = read(card)
     create = re.search(r"## Create\n(.*?)\n## Modify", text, re.S).group(1)
     modify = re.search(r"## Modify\n(.*?)\n## Do not touch", text, re.S).group(1)


     def paths(section):
         """Every repository path a section names in backticks, deduplicated, in order of first
         mention: a token with at least one '/' and a source suffix, so a bare file name in a
         bullet's prose is not one."""
         out = []
         for s in re.findall(r"`([^`]+)`", section):
             if re.fullmatch(r"[\w.-]+(?:/[\w.-]+)+\.(?:h|cpp|py|pyi|txt|md)", s) and s not in out:
                 out.append(s)
         return out


     c = paths(create)
     m = [p for p in paths(modify) if p not in c]
     print("8 Create paths:", len(c), c)
     print("8 Modify paths:", len(m), m)
     print("8 'git status --porcelain' entries:", len(c) + len(m))
     ```

     Its output, which is where every offset, count and path count in this card comes from:

     ```
     1 table sizes, in upload order: [1024, 32, 4096, 256, 4096, 256, 3072, 4096, 4096, 3072]
     1 offsets: [0, 1024, 1280, 5376, 5632, 9728, 9984, 13056, 17152, 21248] | lookup_table width: 24320
     2 jump_node_size: 4
     3 TEST_CASEs in src/test: 154 | this card's: 9
     3 cycles shader manager:*  -> 9
     3 cycles svm*              -> 45
     3 painterly scene:*        -> 14
     3 cycles kernel layout*    -> 2
     3 cycles kernel globals*   -> 0
     3 'painterly scene:' names the filter skips: [('src/test/test_path_trace.cpp', 'painterly scene intersect: an analytic hit that beats a triangle resets the record')]
     3 'painterly scene:' per file: {'src/test/test_scene.cpp': 11, 'src/test/test_triangle_diagnostics.cpp': 3}
     4 svm_offset: 8 lines in 5 files
     4 per file: {'src/painterly/kernel/types.h': [105], 'src/painterly/scene/device_scene.cpp': [120], 'src/test/smallpaint_scene_fixture.h': [150, 167], 'src/test/test_path.cpp': [194, 200], 'src/test/test_scene.cpp': [468, 470]}
     5 manager step call sites: 12 {'src/test/test_cycles_svm_closures.cpp': [93, 94, 95, 402, 403], 'src/test/test_cycles_svm_compiler.cpp': [313, 341, 354, 404, 507, 522, 523]}
     6 helper call sites: 22 in 6 files {'src/test/cycles_svm_test_scene.h': 2, 'src/test/cycles_svm_test_support.h': 1, 'src/test/test_cycles_svm_closures.cpp': 3, 'src/test/test_cycles_svm_compiler.cpp': 1, 'src/test/test_cycles_svm_images.cpp': 7, 'src/test/test_cycles_svm_textures.cpp': 8}
     6 'KernelGlobalsCPU globals;' in those sources: 22 in 4 files {'src/test/test_cycles_svm_closures.cpp': 2, 'src/test/test_cycles_svm_compiler.cpp': 1, 'src/test/test_cycles_svm_images.cpp': 7, 'src/test/test_cycles_svm_textures.cpp': 12}
     6 PainterlySvmTestScene hit calls: 4 {'src/test/test_cycles_svm_textures.cpp': [368, 388, 409, 431]}
     7 test_oracle_parity.py def test_: 5 | @pytest.mark.slow: 1 | parametrize: 2
     7 test_triangle_path.py def test_: 3 | @pytest.mark.slow: 1 | parametrize: 0
     7 test_api_contract.py def test_: 31 | @pytest.mark.slow: 0 | parametrize: 0
     7 DESIGN 12 x CORE_CONFIGS 4 = 48 parametrized items
     7 shim files 19 | shim headers 12 | test_shims.py items 53 | span items 11
     8 Create paths: 1 ['src/test/test_cycles_shader_manager.cpp']
     8 Modify paths: 19 ['src/painterly/scene/scene.h', 'src/painterly/scene/scene.cpp', 'src/painterly/scene/material.h', 'src/painterly/scene/device_scene.h', 'src/painterly/scene/device_scene.cpp', 'src/painterly/scene/svm/shader_manager.h', 'src/cycles/shim/scene/shader.h', 'src/cycles/shim/scene/shader.cpp', 'src/test/cycles_svm_test_support.h', 'src/test/cycles_svm_test_scene.h', 'src/test/test_cycles_svm_closures.cpp', 'src/test/test_cycles_svm_compiler.cpp', 'src/test/test_cycles_svm_images.cpp', 'src/test/test_cycles_svm_textures.cpp', 'src/test/test_cycles_svm_stack_nodes.cpp', 'src/test/smallpaint_scene_fixture.h', 'src/test/test_path.cpp', 'src/test/test_scene.cpp', 'src/test/CMakeLists.txt']
     8 'git status --porcelain' entries: 20
     ```
2. `src/painterly/kernel/types.h` is Opus's; do not edit it. Its rename leaves readers in 4 files (step 1's output,
   "4 per file"): `src/painterly/scene/device_scene.cpp:120`, `src/test/smallpaint_scene_fixture.h:150,167`,
   `src/test/test_path.cpp:194,200` and `src/test/test_scene.cpp:468,470`. Update each to `cycles_shader`, and each
   comment that names the field, to what it now means: `-1` is a constant material, `>= 0` a node material (step 5).
   The field's own definition (`src/painterly/kernel/types.h:105`) is the CONTRACT's line and is already renamed.
3. `src/painterly/scene/material.h`: add the `shader` member of `## Interface`, with `= -1`, and extend `validate()`:
   - a constant material (`shader < 0`) keeps every check it has today, including "at least one lobe" (`:27-29`);
   - a node material (`shader >= 0`) has no constant lobe, so its lobe list may be empty and the per-lobe checks run
     over the lobes it has. It also must not be both: `shader >= 0` with a non-empty lobe list is a programming error,
     so `validate()` throws `std::invalid_argument("PainterlyMaterial: a node material has no constant lobes")`.
   Keep the message style of the four existing throws (`:28`, `:34`, `:40`, `:43`).
4. `src/painterly/scene/scene.h`:
   - `#include <memory>`; `class Scene;` and `class ShaderGraph;` above `class PainterlyScene`;
   - replace `PainterlyScene() = default;` (`:44`) with `PainterlyScene();` and add `~PainterlyScene();`, both defined
     in `scene.cpp`, where the shim `Scene` is complete. A `std::unique_ptr<Scene>` member with an inline destructor
     would need the shim header here, and `painterly/scene/scene.h` reaches `src/blender/python.cpp:34`, which must not
     include a Cycles header;
   - the two methods of `## Interface`, after `add_material` (`:52`), with the comment that `add_shader`'s index is also
     the shader id;
   - the private member `std::unique_ptr<Scene> cycles_;` beside `next_object_id_` (`:108`), with the comment that this
     object owns Cycles' host scene (BRIEF.md section 1, decision 4) and that `device_update` writes only its `dscene`,
     because graph finalization and shader numbering are a cache Cycles fills at the first device update.
   `PainterlyScene` becomes move-only. Nothing copies it today (step 1's output lists no such site), and
   `nb::class_<PainterlyScene>(m, "Scene").def(nb::init<>())` (`src/blender/python.cpp:694-695`) constructs in place, so
   the module compiles unchanged.
5. `src/painterly/scene/scene.cpp`:
   ```cpp
   #include "painterly/scene/scene.h"

   #include <stdexcept>

   #include "painterly/scene/device_scene.h"
   #include "painterly/scene/svm/shader_manager.h"
   #include "scene/scene.h"
   #include "scene/shader.h"
   #include "scene/shader_graph.h"

   /* BRIEF.md section 1, decision 4: the Cycles host scene lives inside PainterlyScene, with painterly's shader
    * manager, and nothing else. */
   PainterlyScene::PainterlyScene() : cycles_(make_unique<Scene>())
   {
     cycles_->shader_manager = make_unique<PainterlyShaderManager>();
   }

   /* ~Scene calls shader_manager->device_free (shim scene.h:57-62), which removes the lookup tables before
    * ~LookupTables asserts that none is left (intern/cycles/scene/tables.cpp:24). */
   PainterlyScene::~PainterlyScene() = default;

   int PainterlyScene::add_shader(std::unique_ptr<ShaderGraph> graph)
   {
     unique_ptr<Shader> shader = make_unique<Shader>();
     shader->set_graph(std::move(graph));
     cycles_->shaders.push_back(std::move(shader));
     return int(cycles_->shaders.size()) - 1;
   }

   int PainterlyScene::add_node_material(const int shader)
   {
     if (shader < 0 || size_t(shader) >= cycles_->shaders.size()) {
       throw std::invalid_argument("PainterlyScene::add_node_material: shader index out of range");
     }
     /* Cycles compiles only a referenced shader (SVMCompiler.compile_type.inc:69; BRIEF.md:47-48). */
     cycles_->shaders[size_t(shader)]->reference();
     PainterlyMaterial material;
     material.shader = shader;
     materials.push_back(material);
     return int(materials.size()) - 1;
   }
   ```
   `add_shader` accepts a null graph on purpose: the manager's entry point reports it (step 6, TQ.4 F5), and a doctest
   needs a way to reach that state through the public API.
   `clear()` (`:21-33`) also empties `cycles_->shaders`, so a material index cannot outlive the shaders it names. Leave
   `cycles_->dscene` alone there: the next device update frees and rebuilds it (step 10).
6. `src/painterly/scene/svm/shader_manager.h`, TQ.4 F5 (`docs/audits/TQ.4.md:47`):
   - `class PainterlyShaderManager : public ShaderManager` — drop `final` (`:40`), so a doctest can expose a protected
     step and prove the `id != index` guard fires (TQ.3's rule that a guard needs a test). Nothing else about the class
     changes.
   - the public entry point of `## Interface`, above `device_update_pre`, and `device_update_pre` (`:52`) and
     `device_update_post` (`:124`) moved under the existing `protected:` (`:154`). The third step stays where it is:
     `device_update_lookup_tables` is `ShaderManager`'s member (`src/cycles/shim/scene/shader.h:192`), and re-shaping the
     shim's API is not this card's (`## Open for Opus` item 5). `device_free` stays public: `~Scene` calls it
     (`shim scene.h:60`).
   - the entry point, before the three steps:
     ```cpp
     /* TQ.4 F5: the one entry point. Each step is a precondition of the next (shader ids, then the jump table, then
      * the lookup tables), and add_table resizes lookup_table, so the caller binds after this returns, never inside. */
     void device_update(DeviceScene *dscene, Scene *scene, Progress &progress)
     {
       for (size_t i = 0; i < scene->shaders.size(); i++) {
         if (scene->shaders[i]->graph == nullptr) {
           throw std::runtime_error("PainterlyShaderManager: shader " + std::to_string(i) +
                                    " has no graph");
         }
       }
       device_update_pre(nullptr, dscene, scene, progress);
       device_update_post(nullptr, dscene, scene, progress);
       device_update_lookup_tables(dscene, scene);
     }
     ```
   - `device_update_post` starts with the second check, before it can index the jump table:
     ```cpp
     /* TQ.4 F5: device_update_pre assigns the ids this indexes the jump table with (shader_manager.h:202). */
     for (size_t i = 0; i < scene->shaders.size(); i++) {
       if (scene->shaders[i]->id != i) {
         throw std::runtime_error("PainterlyShaderManager: shader " + std::to_string(i) + " has id " +
                                  std::to_string(scene->shaders[i]->id) +
                                  "; device_update_pre numbers them");
       }
     }
     ```
     and the vanished `assert(shader->graph)` (`:238`) goes: the entry point has already reported that case, and F1
     (`docs/audits/TQ.4.md:43`) says the assert is compiled out of every build anyway.
   - `#include <stdexcept>` and `#include <string>`.
7. `src/cycles/shim/scene/shader.h` and `shader.cpp`, TQ.4 F4's inputs: the constructor already builds the matrix
   `xyz_to_rgb` (`shader.cpp:60-71`) and takes `rgb_to_y` from its inverse (`:72-73`). It also stores
   `xyz_to_r/g/b = make_float3(xyz_to_rgb.x/y/z)` and the identity `rec709_to_r/g/b`, with a comment naming upstream's
   `init_xyz_transforms` (`intern/cycles/scene/shader.cpp:995-1023`) and its `lin_rec709_scene` branch (`:1001-1007`),
   which is the branch a build without OCIO takes (the shim's own comment `:56-59`). Add the six `float3` members beside
   `rgb_to_y` (`shader.h:205`), protected like it.
   - `tests/core/test_shim_upstream_copies.py:44-57` pins `scene/shader.cpp`'s upstream lines 483-502 and 894-897 by
     sha256, so
     the constructor is free to change; those two spans must stay byte-identical (acceptance 7 checks them).
   - `white_xyz` stays zero: `grep -rn 'white_xyz' third_party/cycles/kernel/` finds only its declaration
     (`kernel/data_template.h:71`), so nothing reads it (`## Open for Opus` item 2).
8. `src/painterly/scene/svm/shader_manager.h`, TQ.4 F4 (`docs/audits/TQ.4.md:46`): in `device_update_common`, write the
   members the vendored SVM reads, before the `scene->shaders.empty()` early return (`:259-261`), because
   `bind_kernel_globals` copies the whole `KernelData` (`:151`) and a constant-material scene must still carry Cycles'
   closure budget:
   ```cpp
   /* TQ.4 F4: the members the vendored SVM reads that Cycles without OCIO sets (intern/cycles/scene/shader.cpp:737-748,
    * the lin_rec709_scene branch at :1001-1007). Written before the early return below: the caller binds this
    * KernelData by value (bind_kernel_globals), so it must carry the closure budget even when no shader is compiled.
    * collect.h:17-18 starts num_closure_left from max_closures, and closure_alloc returns null at 0
    * (kernel/closure/alloc.h:19-21). */
   KernelFilm *kfilm = &dscene->data.film;
   kfilm->xyz_to_r = make_float4(xyz_to_r);
   kfilm->xyz_to_g = make_float4(xyz_to_g);
   kfilm->xyz_to_b = make_float4(xyz_to_b);
   kfilm->rec709_to_r = make_float4(rec709_to_r);
   kfilm->rec709_to_g = make_float4(rec709_to_g);
   kfilm->rec709_to_b = make_float4(rec709_to_b);
   kfilm->is_rec709 = 1;
   dscene->data.max_closures = MAX_CLOSURE;
   ```
   `make_float4(const float3)` sets `w = 1.0f` (`util/types_float4.h:89-92`), which is upstream's value too. The
   existing `kfilm->rgb_to_y` write (`:353`) stays where it is, and the second `KernelFilm *kfilm` declaration that
   would result is dropped.
9. `src/painterly/scene/device_scene.h`:
   - `#include <memory>`, `class DeviceScene;` above `class PainterlyDeviceScene`, and the private member
     `std::unique_ptr<DeviceScene> cycles_dscene_;` next to B1's `cycles_`, with the comment that it owns the Cycles
     arrays `cycles_globals()` points into;
   - the public accessor `const DeviceScene &cycles_device_scene() const` of `## Interface`, beside `cycles_globals()`;
   - no `scene/*` include here: `src/blender/python.cpp` reaches this header through `painterly/session/session.h:36`,
     and the forward declaration is enough for a `unique_ptr` whose destructor is defined in `device_scene.cpp`
     (`~PainterlyDeviceScene`, `:47-50`).
10. `src/painterly/scene/device_scene.cpp`:
    - includes: `#include "painterly/scene/svm/shader_manager.h"` and `#include "scene/scene.h"`;
    - the constructor (B1's) also allocates: `cycles_dscene_ = make_unique<DeviceScene>();`
    - `const DeviceScene &PainterlyDeviceScene::cycles_device_scene() const` returns `*cycles_dscene_`;
    - the material loop (`:112-123`) writes `kernel_material.cycles_shader = material.shader;` instead of
      `svm_offset = -1`, with the comment that `-1` is a constant material and `>= 0` the Cycles shader id whose jump
      entry the SVM starts at (BRIEF.md:30-34);
    - after every check has passed and before the commit, the shader manager runs on the host scene's own
      `Scene::dscene`:
      ```cpp
      /* BRIEF.md section 1, decision 4: pre, post and the lookup tables, in T6.7's order, on the host scene's own
       * DeviceScene, which the manager clears first (device_update_post -> device_update_specific -> device_free,
       * shader_manager.h:166). A throw here leaves `ds` untouched, which is the strong guarantee. */
      Progress progress;
      static_cast<PainterlyShaderManager &>(*cycles_->shader_manager)
          .device_update(&cycles_->dscene, cycles_.get(), progress);
      ```
      `device_update` is `const`, and `operator*` on a const `unique_ptr` returns a non-const `Scene &`, so no `mutable`
      is needed;
    - the commit (`:289-303`) gains, before `ds.bind_globals()`:
      ```cpp
      /* The Cycles arrays, by pointer: steal_data() frees this device scene's old array and takes the scratch's, so
       * nothing here throws (util/array.h:113-125). The pointers the previous bind_globals() published dangle between
       * the two statements and are replaced immediately; the device scene is never updated during a render
       * (session.cpp:55, :166), so no reader sees the gap. */
      ds.cycles_dscene_->svm_nodes.steal_data(cycles_->dscene.svm_nodes);
      ds.cycles_dscene_->shaders.steal_data(cycles_->dscene.shaders);
      ds.cycles_dscene_->lookup_table.steal_data(cycles_->dscene.lookup_table);
      ds.cycles_dscene_->data = cycles_->dscene.data;
      PainterlyShaderManager::bind_kernel_globals(*ds.cycles_dscene_, ds.cycles_);
      ```
      `ds.cycles_` and `ds.cycles_dscene_` are private and `PainterlyScene` is a friend (`device_scene.h:51`), so this
      needs no setter;
    - the manager runs on every update, including one with no node material: that is what gives a constant-material
      scene Cycles' closure budget and film members (step 8) while leaving the three arrays empty.
11. `src/test/cycles_svm_test_support.h`: `painterly_svm_test_globals()` and the new parameter.
    ```cpp
    /* A KernelGlobalsCPU for the SVM tests. Cycles' closure budget is the one member a test must set: collect.h:17-18
     * starts num_closure_left from kernel_data.max_closures, and closure_alloc returns null at 0
     * (kernel/closure/alloc.h:19-21). Every other array stays empty. */
    inline KernelGlobalsCPU painterly_svm_test_globals()
    {
      KernelGlobalsCPU globals;
      globals.data.max_closures = MAX_CLOSURE;
      return globals;
    }
    ```
    and `painterly_svm_test_shader_data(const KernelGlobalsCPU &globals, const int shader,
    const int shader_flags = 0)` reads `globals.data.max_closures` into `sd.num_closure_left` instead of `MAX_CLOSURE`
    (`:327`). `painterly_svm_test_run` (`:341-353`) passes its own `globals`.
    `PainterlySvmTestScene::surface()` and `background()` (`cycles_svm_test_scene.h:104-130`) take
    `const KernelGlobalsCPU &globals` as their first parameter, for the same reason.
12. The 22 call sites of step 1's output, and the 22 `KernelGlobalsCPU globals;` declarations in the four `.cpp` files
    that hold them, which become `KernelGlobalsCPU globals = painterly_svm_test_globals();`. Each call passes the
    `globals` in scope. In `src/test/cycles_svm_test_scene.h` the two calls are the ones in `surface()` and
    `background()`, so they pass their new parameter on; the four `PainterlySvmTestScene` hit calls in
    `test_cycles_svm_textures.cpp` (step 1's output) pass their `globals`. This is mechanical, and step 1's two
    "helper call sites" and "'KernelGlobalsCPU globals;'" lines are the check that none is missed: after the change,
    grep prints `0` for `KernelGlobalsCPU globals;` in those four files and every helper call has two arguments.
13. `src/test/test_cycles_shader_manager.cpp`, the 9 doctests of `## Acceptance`:
    - the file header comment names BRIEF.md section 2 "B2" and TQ.4 F4 and F5;
    - the helpers `test_cycles_svm_closures.cpp:47-96` uses, copied as the four SVM test sources copy them, with
      `make_scene` replaced by a `PainterlyScene` and `create_node_by_name`/`set_enum`/`add_surface` unchanged.
      TQ.4 F7 (`docs/audits/TQ.4.md:49`) gives the de-duplication of these helpers to M6a-FIX-TQ4c, so this card copies
      and does not refactor; the copy must be the `REQUIRE`-guarded `create_node_by_name` (`test_cycles_svm_closures.cpp`
      `:61-66`);
    - `painterly_cycles_shader_node_types()` once, before the first `NodeType::find` (`cycles/shader_node_registry.h:24`;
      T6.4:861);
    - the 9 cases, in this order, with the names step 1's output counts:
      1. *a node material gets its shader id and its jump entry* — a `diffuse_bsdf` with Color (0.5, 0.25, 0.125),
         dyadic, linked to the output's Surface; `CHECK(ds.materials[0].cycles_shader == 0)` and
         `CHECK(ds.cycles_device_scene().svm_nodes.data[0] == NODE_SHADER_JUMP)`, which is
         `svm_nodes[cycles_shader * jump_node_size]` for the derived `jump_node_size` 4 (`shader_manager.h:181`,
         `:202-203`); and the lobe the collector reads at that shader id, through the `evaluate()` pattern, equals the
         authored colour exactly.
      2. *the lookup tables are uploaded where KernelTables points* — the ten offsets of step 1's output
         (`0, 1024, 1280, 5376, 5632, 9728, 9984, 13056, 17152, 21248`), `lookup_table.width == 24320`,
         `cycles_globals().lookup_table.data == ds.cycles_device_scene().lookup_table.data()`, and
         `cycles_globals().data.tables.thin_film_table == 21248`. The offsets are `LookupTables::add_table`'s
         (`add_table.inc:9,15-32`) applied to the ten table sizes of `scene/shader.tables` in
         `device_update_lookup_tables`'s order (`shim shader.cpp:192-205`); `test_cycles_svm_closures.cpp:294-304` pins
         the same ten values for the manager alone, which corroborates them.
      3. *two node materials share one jump table* — two shaders; `svm_nodes[0]` and `svm_nodes[4]` are both
         `NODE_SHADER_JUMP`, and the second entry's `offset_surface` is `8 + first_size - 4`, the arithmetic of
         `shader_manager.h:191-212` with the first shader's compiled size taken from the test's own `svm_nodes` size.
      4. *a throwing device update leaves the previous device scene bit for bit unchanged* — the existing throw points
         of `device_scene.cpp` (`:129`, `:155`, `:186`, `:246-247`, `:252`) reached through a mesh whose material index is
         out of range, with a node material in the scene so the manager has already compiled: every painterly array,
         `KernelPainterlyData` and the three Cycles arrays are compared with `memcmp` against copies, as
         `test_scene.cpp:898-960` does, and `cycles_globals().svm_nodes.data` still points into the device scene.
      5. *a scene of constant materials compiles no shader* — the host scene's `shaders` empty, every
         `ds.materials[i].cycles_shader == -1`, and `svm_nodes`, `shaders` and `lookup_table` all of width 0 with null
         pointers; then a second `device_update` leaves every painterly array byte-identical. The bit-identical
         comparison with the pre-B2 output is T3.16's, in `## Acceptance` 5.
      6. *a null graph or a wrong shader id is an error, not an assert* — `scene.add_shader(nullptr)` then
         `CHECK_THROWS_WITH_AS(scene.device_update(ds), "PainterlyShaderManager: shader 0 has no graph",
         std::runtime_error)`; and, through a subclass that re-exposes the protected `device_update_post` (step 6),
         `CHECK_THROWS_AS(manager.device_update_post(nullptr, &cycles.dscene, &cycles, progress), std::runtime_error)`
         before it can index the jump table.
      7. *the one entry point runs pre, post and the table upload in order* — after one call to the entry point,
         `shader->id == 0` (pre), `svm_nodes` non-empty and `KernelShader::flags ==
         SD_VOLUME_MIS | SD_USE_BUMP_MAP_CORRECTION` (post; `default_shader_flags`, `test_cycles_svm_compiler.cpp:195`),
         and `data.tables.ggx_E == 0` with `lookup_table.width == 24320` (the tables).
      8. *KernelData carries the film and closure members the SVM reads* — `is_rec709 == 1`, the three `rec709_to_*`
         rows the identity, `xyz_to_r` equal to the first row of the matrix `shim shader.cpp:60-71` builds (the test
         writes that row out, so it shares no code with the constructor), and `max_closures == MAX_CLOSURE`, on a scene
         whose only material is constant — the early-return path of step 8.
      9. *the closure budget comes from kernel_data.max_closures* — `painterly_svm_test_shader_data(globals, 0)` with
         `globals.data.max_closures = 0` gives `num_closure_left == 0`, and `closure_alloc` then returns null
         (`kernel/closure/alloc.h:19-21`), while the same call with `painterly_svm_test_globals()` gives `MAX_CLOSURE`:
         the helper's contract, and the reason the 22 call sites pass a globals.
14. `src/test/CMakeLists.txt`: `target_sources(painterly_tests PRIVATE test_cycles_shader_manager.cpp)` in a block of
    its own, with the comment that it needs `cycles_scene` and `cycles_svm` (which `:96-99`'s block already links) and
    `ccl=painterly` (B1's `target_compile_definitions(painterly_tests PRIVATE ccl=painterly)`).
15. `make format`, then every acceptance command.

## Acceptance

Run every command from the repository root; the queue translates them with BACKLOG.md's table (`make check` → `CHECK`,
`build/dev` → `build/q`, `.venv/bin/<tool>` → `MAIN/.venv/bin/<tool>`, `python -I` → `PYTHONPATH="$PWD/analysis" … -P -s`).

1. `make check` exits 0. Report the doctest test-case and assertion counts, the pytest pass count and the audit's
   `RESULT: PASS` line.
2. `build/dev/src/test/painterly_tests --test-case='cycles shader manager:*'` exits 0 and prints
   `test cases: 9 | 9 passed | 0 failed`: the 9 cases of step 13 and only those. doctest v2.4.11's `wildcmp` compares a
   literal prefix and stops at the first `*` (`doctest.h:4113-4124`), so this filter selects every name that *begins*
   with `cycles shader manager:`; step 1's output shows that no case at HEAD does, so 9 is this card's own count.
3. `build/dev/src/test/painterly_tests --test-case='painterly scene:*'` exits 0 and prints
   `test cases: 14 | 14 passed | 0 failed`: the scene's 14 cases at HEAD (11 in `test_scene.cpp`, 3 in
   `test_triangle_diagnostics.cpp`), unchanged by this card and now running against a `device_update` that calls the
   shader manager. This filter does **not** reach this card's new cases, which are named `cycles shader manager: …`;
   `test_path_trace.cpp:341`'s `painterly scene intersect: …` is the one `painterly scene` case the filter skips, because
   the literal-prefix loop compares `:` with ` ` and returns 0 before any `*` is reached (step 1's output, "names the
   filter skips"). Acceptance 2 is what covers the new cases.
4. `build/dev/src/test/painterly_tests --test-case='cycles svm*'` exits 0 and prints
   `test cases: 45 | 45 passed | 0 failed`: T6.3-T6.8's SVM cases after the helper's signature changed at 22 call sites.
   The 45 is the count at HEAD and does not move: this card adds no case whose name starts with `cycles svm`, and B1's
   two are named `cycles kernel globals: …` (`docs/handoff/drafts/M6b/B1-kernel-globals.md`, step 11), which that filter
   does not match either. The script's own `cycles kernel globals* -> 0` is the count in this checkout, where B1's cases
   do not exist yet; it is not the count after B1.
5. `.venv/bin/python -m pytest -q -m slow tests/core/test_oracle_parity.py tests/core/test_triangle_path.py` prints
   `2 passed, 53 deselected`: the two slow tests, unchanged. `test_oracle_parity.py` holds 3 unparametrized tests
   (`:125`, `:138`, `:162`), 12 `DESIGN` entries × 4 `CORE_CONFIGS` = 48 parametrized items and 1 slow test (`:366-367`),
   so 52 items; `test_triangle_path.py` holds `:156`, `:183` and the slow `:272-273`, so 3. 52 + 3 = 55 items, 2 of them
   `slow`, so the `-m slow` run selects 2 and reports `55 - 2 = 53` deselected (step 1's output). This is also the check
   for the brief's "a scene of constant materials produces byte-identical painterly arrays to today's": T3.16 compares
   the core's output with the oracle bit for bit, so any change in the constant path fails it.
6. `.venv/bin/python -m pytest -q tests/core/test_api_contract.py` prints `31 passed`: no Python name changed (B6 owns
   them). The count is the file's own 31 `def test_`; it has no parametrize (step 1's output).
7. `.venv/bin/python -m pytest -q tests/core/test_shims.py tests/core/test_shim_upstream_copies.py` prints `53 passed`
   for the first file and `11 passed` for the second: the shim markers and the ten pinned upstream spans
   (`tests/core/test_shim_upstream_copies.py:22-93`) still hold after step 7. `test_shims.py` has
   1 + 19 + 19 + 1 + 12 + 1 = 53 items (6 `def test_`, two of them parametrized over the 19 shim files and one over the
   12 shim headers); `test_shim_upstream_copies.py` has 10 span items plus `test_spans_are_distinct` (step 1's output).
8. `make audit` prints `RESULT: PASS`: no new exported symbol and no new dependency. The new members are C++ members of
   classes the module already binds, and `painterly_scene`'s new link is B1's.
9. `git status --porcelain` lists exactly the 1 Create path and the 19 Modify paths above (step 1's output, "git status
   --porcelain entries: 20").
10. The derivation script of step 1, re-run, prints the output quoted there: every number in this card comes from it.

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- delete the `cycles_shader = material.shader` line → acceptance 2 fails on the first case;
- bind before the entry point returns, i.e. call `bind_kernel_globals` inside `device_update_common` → acceptance 2 fails
  on the lookup-table case: `add_table`'s `resize` moves the array after the bind (TQ.4 F5's dangling pointer);
- move the `max_closures` write below the `shaders.empty()` return → acceptance 2 fails on the eighth and ninth cases,
  and B1's `cycles kernel globals` case fails on a constant-material scene;
- `kfilm->is_rec709 = 0` → acceptance 2 fails on the eighth case;
- copy the three Cycles arrays instead of `steal_data` at the commit, then throw after the copy → acceptance 2's fourth
  case fails: the device scene is no longer the earlier one;
- keep `assert(shader->graph)` and drop the entry point's null-graph check → the sixth case fails in a Release build (the
  assert is compiled out, TQ.4 F1) and aborts in a Debug build;
- leave `num_closure_left = MAX_CLOSURE` in the helper instead of reading `globals.data.max_closures` → the ninth case
  fails.

Report: the doctest and pytest counts, the audit line, the derivation script's output, and every mutation you ran with
its first failing check.

## Commit

`B2: the shader manager in PainterlyScene::device_update`

## Open for Opus

1. **`num_lobes >= 1` holds only for a constant material.** The CONTRACT comment (`types.h:103`) says `num_lobes` is at
   least 1, and this card's node material sets 0, because its lobes come from `painterly_svm_collect()` per hit
   (BRIEF.md:35) and a placeholder lobe would make a missing B4 render black through the constant path instead of
   failing. Options: (a) leave the comment as the constant material's rule and let `cycles_shader`'s own comment carry
   the node case (this card's reading, and the CONTRACT block of `## Interface`); (b) widen the comment to "1 for a
   constant material, 0 when `cycles_shader >= 0`", a one-line CONTRACT edit Opus would make before dispatch; (c) give a
   node material one zero-weight diffuse lobe, which keeps the comment true and needs no CONTRACT edit, at the cost of a
   lobe that means nothing. This card takes (a).
2. **`white_xyz` stays zero.** TQ.4 F4 names `is_rec709`, `rec709_to_*`, `xyz_to_*` and `max_closures`; upstream's
   `init_xyz_transforms` also sets `white_xyz` (`intern/cycles/scene/shader.cpp:1020`) and `device_update_common` writes
   it (`:743`). No vendored kernel code reads it (`kernel/data_template.h:71` is its only occurrence), so this card
   leaves it zero. Options: (a) as this card; (b) write it too, from the same inverse matrix, which costs one shim member
   and one line and keeps the shim a complete port of the colour-space block. If a later node (a white-balance or a
   chromaticity node) reads it, (b) becomes necessary.
3. **The error channel of F5's two checks.** The brief says the two cases are "an error, not an assert" and names no
   mechanism. Options: (a) `std::runtime_error`, which `PainterlyScene::device_update` lets escape and which the session
   already reports as a state's `error` string; (b) a `bool` return with a `std::string *error` out-parameter, which
   matches no other painterly API; (c) `std::invalid_argument`, the type `device_scene.cpp` throws for a malformed
   scene, though these two are not the caller's input's fault. This card takes (a), and its doctest matches the message,
   so the choice is pinned either way.
4. **`PainterlyShaderManager` loses `final`.** TQ.3's rule is that a guard needs a test, and the only way to reach the
   protected `device_update_post` is a subclass, so step 6 drops `final` (`shader_manager.h:43`). The alternative is to
   keep `final` and leave the `id != index` guard untested — the shape TQ.4 F7 and F16 filed against. If Opus prefers
   `final`, the sixth case keeps only its null-graph half, and the guard moves into `device_update_pre`'s numbering loop,
   where it cannot fire either.
5. **`device_update_lookup_tables` stays public.** F5 asks that "the three steps become protected", but the third is
   `ShaderManager`'s member in `src/cycles/shim/scene/shader.h:192`, and re-shaping the shim's API is not this card's
   mandate; the entry point calls it, and the `protected:` block holds the two painterly steps. Options: (a) as this
   card; (b) move the shim's member into a protected section, which changes `src/cycles/shim/**` for one line of API
   hygiene and makes `tests/core/test_shims.py` and the pinned-span test re-check it. (a) already gives one public entry
   point, which is what F5's fix asks for.
6. **The new doctest file copies four helpers.** TQ.4 F7 (`docs/audits/TQ.4.md:49`) files the divergence of
   `create_node_by_name`, `new_program`, `run_and_check` and `make_scene` across the SVM test sources and gives the
   de-duplication to M6a-FIX-TQ4c. This card's file copies them, like the four before it, rather than refactoring a
   header F7 owns. The alternative is to move them into `cycles_svm_test_support.h` in this card, which would edit the
   helper header F7's own fix touches.
7. **The strong guarantee covers `ds`, not the host scene's scratch.** A `device_update` that throws after the manager
   ran leaves `cycles_->dscene` holding a half-compiled program, while `ds` is exactly as it was; the next update clears
   it (`device_update_specific` → `device_free`, `shader_manager.h:166`). The brief's decision 4 asks only for `ds`'s
   guarantee (`device_scene.cpp:94-97`), and the scratch is a cache Cycles itself refills (BRIEF.md:40-42), so this card
   does not restore it. If Opus wants the scratch restored too, the manager must write into a local `DeviceScene` and the
   commit must steal from that instead, which is one more local in `device_update`.
