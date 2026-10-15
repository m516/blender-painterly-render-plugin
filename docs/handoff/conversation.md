# Condensed history (2026-10-08 to 2026-10-15)

## The request
The owner uploaded `Smallpaint.zip` (smallpaint_painterly, a small path tracer whose painterly look comes from a Halton
sequence bug) and asked for a plan, executed by Haiku subagents, to turn it into an accelerated Blender extension with
Cycles as the code template. Preserving the look and making it accessible to artists is the goal. The planning answers
are in `decisions.md`. The approved plan became `docs/plan.md`, and the normative behaviour `docs/spec.md`.

## What happened, in order
1. **M0-M1.** Repository scaffolding, a compiled oracle of smallpaint (`src/app/smallpaint_oracle.cpp`, with documented
   changes in `src/app/CHANGES.md`), the analysis package (`analysis/painterly_analysis`, JAX), and experiments 001-006.
   - 001 showed that the oracle reproduces the reference.
   - 002 showed that every ingredient is necessary.
   - 003 made `chain=row` the default.
   - 004 was inconclusive on locking.
   - 006 fixed the jitter units at a fraction of the image side, 1/1400 (SPEC §7).
   The index `experiments/README.md` has a one-line result for each.
2. **M2.** Static `_painterly` module (nanobind, stable ABI, Embree 4.4.1 static and namespaced), symbol audit, wheels for
   three OS, and coexistence inside Blender 5.2.2 (005).
   - Windows needed three fixes before G1 closed:
     - T2.9: nanobind's exception-class exports;
     - T2.10: `<memory>` force-included for vendored Cycles' `guarded_allocator.h`, which upstream gets via
       `WITH_BLENDER_GUARDEDALLOC`;
     - T2.11: `NOMINMAX`, as Blender defines it for every Windows source.
3. **Layout v2.** Our C++ lives in `src/painterly/<layer>/` with `Painterly`/`painterly_` prefixes, and shims live only in
   `src/cycles/shim/`. The reason: vendored Cycles shares the `painterly` namespace, and the old names collided.
4. **M3 run 3a** (T3.1-T3.12, TQ.1) implemented vendoring, the kernel, the BVH, the path and the scheduler. The review
   panel confirmed 20 findings, which went into fix-up cards T3.19-T3.28 together with TQ.1's proposals.
5. **Native first light** (2026-10-10). 18 of 18 configurations are bit-identical to the oracle; see
   `firstlight/README.md`.
   - It revealed the zero-length bounce NaN: vdc(K) = 0 at K ≡ 0 mod 2^23 gives d = N + F·s = 0 on a surface with
     N = −F·(1,0,0), and the α-rescale is then 0·∞.
   - Fixed in SPEC §4 (D33); the code fix is card T3.19.
6. **Card drafting** for the M3 fix-ups, M6a and M7-M9, and pre-registrations for 007-009. On 2026-10-10 a weekly usage
   limit stopped all of them partway. On 2026-10-15 a retry ran read-only because the session was still in plan mode.

## Experiments 007-009 (in flight at handoff)
- **007 (noise locking, re-analysis of 006 renders; no new renders).** The second review found a blocker. The row chain's
  noise is exactly uncorrelated across rows (SPEC §2-§3: K0 per (row, pass); hashes per (row, col, pass)). Its 2-D
  isotropic keys can therefore never reach the "image-locked" cell: an independent simulation gave 0 of 15. The fix:
  1-D along-row keys (`noise_frac`, `nlag.x`), row-independent synthetic models, and a separate test of row independence.
- **008 (jitter dose-response).**
  - Six jitter levels at 400 px on the row chain: f ∈ {0, 1/5600, 1/2800, 1/1400, 1/700, 1/350}, blocks 42-45, 64 new
    renders.
  - Review points: sensitivity of the sds per doubling of f; using `report.paint`/`draw_line` from 007.
- **009 (scale limits).**
  - A 1600 px family, and an undersampling test at f = 1/400 on fresh blocks 46-67.
  - Review points: 99% intervals; disk (7.8 GB needed); idle-machine dispatch.
- **Rules settled for all three.** Directory date = the commit date that creates it, numbered in run order. 99% decision
  intervals. Never `make oracle`.

## Lessons that shaped the process
- Pre-register every experiment, and review the design adversarially before any render. 006's first design treated
  deterministic renders as replicates, and an amendment had to fix it.
- Statistical decisions go only through `ensemble.py` criteria or derived rules. Every decision reports an effect size
  next to complete-separation tests, along with the noise floor.
- Bit parity with the oracle uses `--halton exact`. Statistical work may use the default incremental Halton.
- Cheap implementers follow cards literally, so every card must be executable within its own scope. Card defects are
  caught by an independent gate (`card_defect`).
- Upstream Cycles is compiled in Blender's build environment (forced includes, platform definitions). When vendored code
  fails to build, look first for what Blender's CMake provides (`platform_win32.cmake`, `intern/cycles/CMakeLists.txt`).
