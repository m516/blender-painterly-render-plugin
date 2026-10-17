# EXP-REPRO-HOST: this machine's outputs of the 001-006 analyses

R17: `docs/handoff/repro/host/<NNN>/results.json` is this machine's output of the analysis of
experiment `<NNN>` (`<NNN>` in 001, 002, 003, 004, 006). Every exact check (`==`, `cmp`) that a
card, PLAN or item makes against a committed 001-006 `results.json` compares with this file
instead. Checks against committed figures are unchanged. A mismatch is a finding; a check against
one of these files is never turned into a tolerance.

No figure is copied here: the figures stay in `experiments/<NNN>-*/`.

Date of the run: 2026-10-16 (America/Chicago, UTC−05:00; 2026-10-17 UTC).

Experiments' oracle (R7): `MAIN/.cache/oracle-build/src/app/smallpaint_oracle`, sha256
`804a2dc2722167aab472aacc2c0cce4bba53f28f155d63b7a0f2c827a0395954`. `MAIN` is
`/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin`.

## Commands

Run from the clone root, for `<NNN>` in 001 002 003 004 006:

```
PYTHONPATH="$PWD/analysis" PAINTERLY_BUILD_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/oracle-build PAINTERLY_CACHE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache /run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python experiments/<NNN>-*/analyze.py --out-dir .cache/repro-host/<NNN>
```

All five exits were 0; no analysis reported a missing render. Each output figure was compared with
the committed figure of the same name:

```
for n in 001 002 003 004 006; do
  exp=$(ls -d experiments/$n-*)
  for f in .cache/repro-host/$n/fig_*.png; do
    cmp "$f" "$exp/$(basename "$f")"
  done
done
```

Each output `results.json` was copied byte for byte to `docs/handoff/repro/host/<NNN>/results.json`
(`cp`), and each copy was checked with `cmp`.

## Outcome checks

### 1. Figures

24 of 24 output figures are byte-identical to the committed figures (`cmp` exit status 0):

| experiment | figures | identical |
|---|---|---|
| 001 | 4 | 4 |
| 002 | 11 | 11 |
| 003 | 1 | 1 |
| 004 | 1 | 1 |
| 006 | 7 | 7 |
| all | 24 | 24 |

### 2. `results.json` records

For each `<NNN>`, `compare_objects` from `tools/compare_results.py`, applied to the committed
`experiments/<NNN>-*/results.json` and to `docs/handoff/repro/host/<NNN>/results.json`, equals
(`==` on the parsed JSON) the report stored in `docs/handoff/repro/REPRO.json` under
`["<NNN>"]["results.json"]["leaves"]`:

| experiment | equal | identical | n_leaves | n_leaves_differing | non_numeric_identical |
|---|---|---|---|---|---|
| 001 | true | false | 1798 | 48 | true |
| 002 | true | false | 4805 | 80 | true |
| 003 | true | false | 1278 | 7 | true |
| 004 | true | false | 2902 | 60 | true |
| 006 | true | false | 8730 | 2539 | true |

`equal` is `compare_objects(...) == REPRO.json["<NNN>"]["results.json"]["leaves"]`; the other four
columns are fields of that report. `identical` false and `non_numeric_identical` true match
`docs/handoff/repro/REPRO.md`.

sha256 of the records copied here:

| experiment | `docs/handoff/repro/host/<NNN>/results.json` |
|---|---|
| 001 | c1d9e6f4745defa11af0fdaf75e70200b70a94f516fe454ee089dedf9e35c7b3 |
| 002 | 8339c088f931b5739a8cc88e1912f258abcfb728558d3c8c3ac293486f7e3b3e |
| 003 | f98414270ae7a11b54ccb27c9258d855ce98f3c9f2396dfd104ee03e29a9b20f |
| 004 | fe46ef80c8b997fa68ef807d107c1bc86f6cd492d2c6b033179cad2b5cf5834a |
| 006 | 41494b386b2022430c6a60bdf03bb67521d973ad57f11b9a9eccd8731a6bfad9 |

### 3. `make lint`

```
CMAKE_BUILD_PARALLEL_LEVEL=4 make lint VENV=<MAIN>/.venv BUILD_DIR=build/q BLENDER=<MAIN>/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=<MAIN>/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=<MAIN>/.cache/src/doctest"
```

Exit status 0. Output: `All checks passed!` (ruff check), `134 files already formatted`
(ruff format --check), clang-format `--dry-run --Werror` exit 0.
