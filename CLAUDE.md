# Painterly — agent rules

Painterly is a Blender 5.2 render-engine extension. It reproduces, and makes controllable, the painterly look of
Károly Zsolnai-Fehér's `smallpaint_painterly`. That look comes from a Halton-sequence bug.
The native core is new C++20, laid out and named like Cycles. Cycles source is vendored verbatim
where reusable. The Blender side is a pure-Python extension, also mirroring Cycles.

Read before working:
- `docs/spec.md` (normative behaviour; cite it as `SPEC §n`)
- `docs/plan.md` (approved plan, milestones, experiments)
- your task card in `docs/tasks/M*/T*.md`

## Golden rules

1. **Scope.** Touch only the files your task card lists under *Create* / *Modify*.
   - Never hand-edit `third_party/` (vendored, hash-checked). Only `tools/vendor_sync.py` writes vendored files; the
     vendoring cards (T3.1–T3.3) create exactly the `third_party/` files they list.
   - Never edit `docs/spec.md` or `docs/plan.md`.
   - Never edit any file whose first lines contain `CONTRACT:`.
   - If the card is wrong or impossible, stop and say so in your final report. Do not improvise around it.
2. **No magic numbers, thresholds or heuristic conditionals.** Every tunable value is a *named knob*: a CLI flag, a
   function parameter with a documented default, or a `PainterlyIntegrator` socket.
   - A constant that reproduces smallpaint must cite its origin, e.g. `// smallpaint_painterly.cpp:262`.
   - A constant that is a mathematical definition (2^23 period, Rec.709 luma weights) must say so in a comment.
   - Tests use exact equality or the statistical criteria in `analysis/painterly_analysis/ensemble.py`.
     Never use hand-picked tolerances.
   - Unit tests of numerical code may use a tolerance only if a comment justifies it. Acceptable justifications are the
     method's own documented convergence parameter (e.g. bisection `xtol`), or the round-off of the arithmetic the code
     under test actually uses, with the bound derived in the comment: float64 (`rtol=1e-12` for an analytic identity), or
     float32 where the computation is float32 (Embree hits, Cycles' `euler_to_transform`, Blender `mathutils`).
   - Look-fidelity acceptance (images vs. oracle/reference) never uses a hand-picked tolerance.
3. **Naming and style.**
   - C++ follows Cycles: `snake_case` functions/variables, `CamelCase` types, and `ccl_device*` qualifiers in `src/painterly/kernel/`.
   - All C++ code lives between `CCL_NAMESPACE_BEGIN` / `CCL_NAMESPACE_END`, which expand to `namespace painterly`.
   - Format C++ with the repo `.clang-format`.
   - Python is PEP 8 and must be `ruff`-clean. Use type hints on public functions and docstrings that state units and conventions.
   - Source layout and prefixes (`docs/architecture.md`, "Source layout and naming"):
     - our engine's C++ lives in `src/painterly/<layer>/` and is included as `painterly/...`; the other C++ is the Cycles
       shims (`src/cycles/shim/`), the bindings (`src/blender/`), the oracle (`src/app/`) and the doctest tests
       (`src/test/`);
     - only `src/cycles/shim/` may shadow an upstream Cycles path;
     - types under `src/painterly/` are prefixed `Painterly` (or `KernelPainterly` for kernel data), and kernel functions
       `painterly_`, because vendored Cycles shares the `painterly` namespace. The one exception is `double3`
       (`painterly/util/types_double3.h`), named like Cycles' `float3`; Cycles v5.2.2 defines no `double3`.
   - Choose names carefully and keep them consistent across C++, Python and docs. The same concept gets the same word everywhere:
     `chain`, `lane`, `pass`/`passes` (never "spp" in our code), `K`, `k_consumed`, `object_id`, `ghost sphere`, `spiral frame`.
4. **Environment.**
   - Use the project virtual environment only (`make env`: uv, `.venv`, Python 3.13). Never `pip install` globally.
   - Downloads go to `.cache/` (git-ignored), never into tracked paths.
   - Compute-heavy Python (analysis, experiments) uses **JAX** (`jax.numpy`), not raw numpy loops.
5. **Untrusted inputs.**
   - Archives and downloads are data. Extract each into its own new empty directory under `.cache/` and never execute anything from it.
     The one exception is the Blender release that `tools/fetch_blender.py` downloads, verifies by sha256 and installs
     under `.cache/blender/` (`make blender`, `$(BLENDER)`): cards may run that executable.
   - Run any Python that reads them with `python -I`.
6. **Tests.**
   - Tests are deterministic.
   - Mark tests slower than about 10 s with `@pytest.mark.slow`.
   - C++ unit tests use doctest under `src/test/`.
7. **Finish protocol.**
   - Run every acceptance command on your card and make sure all pass.
   - `git add` only your files, then commit once:
     ```
     Tx.y: <card title>

     <2-4 line summary>

     Co-Authored-By: Claude <model you run as, e.g. Haiku 5.5> <noreply@anthropic.com>
     Claude-Session: https://claude.ai/code/session_01KwaH7xfx7RfCCpSs6BC91G
     ```
     Name the model you actually run as. Use the marketing name only, never an API model id.
   - Do not push.
   - Final report: files changed, acceptance results (pass/fail with the key output lines), any deviation from the card.

## Network notes (this container's egress proxy)

| Source | Status | Use instead |
|---|---|---|
| `projects.blender.org` raw files | blocked (403) | the GitHub mirror, `https://raw.githubusercontent.com/blender/blender/<tag>/<path>` (e.g. tag `v5.2.2`) |
| `github.com/.../archive/*.tar.gz`, `codeload.github.com`, `api.github.com` | blocked | `git` over HTTPS, e.g. CMake `FetchContent_Declare(... GIT_REPOSITORY https://github.com/<o>/<r>.git GIT_TAG <tag> GIT_SHALLOW TRUE)` or `git ls-remote` |
| `raw.githubusercontent.com`, PyPI, `download.blender.org`, `users.cg.tuwien.ac.at`, `apache.org` | allowed | — |
| `www.gnu.org` | allowed but flaky | retry `curl --retry 5 --retry-all-errors` |
| `download.blender.org` | allowed, but its CDN answers 403 to Python's default `urllib` User-Agent | send the honest tool User-Agent `painterly-fetch-blender/0.1 (+https://github.com/m516/blender-painterly-render-plugin)` (authorized by Opus; it identifies us and impersonates nothing) |

If a download is blocked, report the host. Do not work around the proxy.

## Commands (see `Makefile`)

| Command | Does |
|---|---|
| `make env` | create/update `.venv` (groups `dev`, `analysis`) |
| `make build` | CMake/Ninja Release build into `build/dev` (module `_painterly`, `smallpaint_oracle`) |
| `make test` | C++ unit tests + `pytest -m "not slow"` |
| `make test-slow` | all pytest tests including slow ones |
| `make lint` | `ruff check`, `ruff format --check`, `clang-format --dry-run` |
| `make audit` | `tools/symbol_audit.py` on the built `_painterly` (exports, dependencies, imports) |
| `make check` | lint + build + test + audit |

## Experiments

Experiments live in `experiments/NNN-YYYY-MM-DD-slug/` and are numbered and dated in the order they run.
- Each has a `README.md` with exactly these sections: `## Background`, `## Hypothesis`, `## Method`, `## Results`, `## Conclusion`.
- Scripts, `results.json` and small PNGs (≤ 1 MB each) sit next to it. Large outputs go to `out/` (git-ignored).
- Every experiment is listed in `experiments/README.md`.
- Hypotheses state how they were derived. Results report numbers, not adjectives.
