# TQ.3 — Code-quality audit: M3's queue commits since TQ.2

Auditors: three read-only Sonnet readers, with every finding below checked by Opus at its cited lines. Tree audited:
`528c098` (integration, the stack of landing 3). This is the M3 milestone review's audit (PLAN-TO-FINAL M3.7), run on
2026-10-24 inside landing 3's review. Scope:
- the M3 code of the 17 queue commits since TQ.2's tree `f7b633d`: `ce87e45` (T3.13a), `98f6793` (T3.27), `18a0a14`
  (T3.14), `82ea332` and `3b34c04` (TQ.2's fixes), `84fced7` (T3.28), `d4bf84d` (T3.13b), `4c36d73` (T3.15), `3c9b821`
  (T3.26), `d54fd06` (T3.16), `0818fdd` (T3.17), `e331037` (T3.18), `bea0b51` (TQ2-REPRO), `b11cbd5` (T3.15a),
  `8835777` (T3.17a), `2dc0196` (TOL-a), `528c098` (T3.17d);
- the landing review of `e155092..528c098`, which adds M4's `93ff499` (T4.3) and `d678cd5` (T4.2a) and the T7.1 draft
  revision `dc00d44`.

## Method

- As TQ.2: each commit read with `git show`, tests first; reading was static, plus read-only Python on committed JSON
  and text. Nothing was built or run; the landing's fresh-clone check runs the suites.
- Searched for: tests that cannot fail (each finding names the mutation that survives), stubs, dead or duplicated code,
  swallowed errors, numbers in comments that do not match the code, CLAUDE.md rule 2 violations; for the session code,
  unsynchronised state; for `test_triangle_diagnostics.cpp`, every CHECK that a different CPU or MSVC could break.
- Opus re-checked each finding at the cited lines before recording it. Severity scale as in TQ.1: **Medium**, a gap that
  lets regressions through, or a reproducibility problem with real cost; **Low**, consistency or hygiene.

## Verdict

No finding blocks the M3 review. T3.16's parity is bit for bit: `_assert_bit_equal` (`tests/core/test_oracle_parity.py:238-255`)
compares the float64 sums, `k_consumed` and `object_id` with `np.array_equal` and identical `tobytes()`, over a pairwise
cover of threads and batch sizes plus one slow 400 px run, against `smallpaint_oracle --halton exact --threads 1`
(the project's modified copy of smallpaint, built with the same `-ffp-contract=off`). Every finding is a test that a
mutation would pass, an edge case of the session or the bindings, or a wrong comment; none shows a wrong result.
The fix items are BACKLOG M3-FIX-TQ3a, -TQ3b, -TQ3c, M3-FIX-T3.17e and M4-FIX-T4.3a.

## Findings

| # | Sev. | Finding | Evidence | Status |
|---|---|---|---|---|
| F1 | Medium | No test sees `wait(timeout)` return false while a render runs: C++ calls only `wait(-1.0)` and Python drops the result. `return true;` survives, though the add-on's loop (`addon/session.py:159`) needs the false. | `src/painterly/session/session.cpp:84`; `src/test/test_session.cpp:215,251,268,308,322`; `tests/core/test_api_contract.py:656` | TQ3a |
| F2 | Medium | The destructor's `cancel()` is untested: without it the test passes, only slower (D27 forbids a latency threshold), and the add-on relies on it (`addon/session.py:143-149`). | `session.cpp:24`; `test_session.cpp:291-311` | TQ3a |
| F3 | Medium | `buffers_copy()`'s untorn copy (`session.h:95-97`) is never read during a render, and no sanitizer build exists, so deleting either lock passes. | `session.cpp:108,149`; nothing in CMake, Makefile or `.github` | TQ3a (a cross-thread test); a TSan build is open |
| F4 | Medium | Restarting a finished Session is documented (`session.h:86-89`) but never tested: deleting the join, `error_.clear()` or `cancel_requested_.store(false)` passes. | `session.cpp:48-50,62,67` | TQ3a |
| F5 | Medium | No test calls `set_camera_orthographic`, a valid `set_camera_perspective`, `add_sun`, `set_spiral_object`, `Scene.clear` or `add_sphere(spot=…)` for its effect; the contract test compares signatures, and every transform is the identity. Forwarding orthographic to perspective, or swapping `add_sun`'s direction and radiance, passes. | `src/blender/python.cpp:855-891`; `tests/core/test_api_contract.py:135-163` | TQ3b |
| F6 | Medium | The interior object-id check passes on an empty interior; the interior count is only printed. | `tests/core/test_triangle_path.py:192-196,200-203` | T3.17e |
| F7 | Medium | No test regenerates the committed REPRO.json and REPRO.md: the tests use a synthetic experiment 001, so an edit to `repro_report.py` or `compare_results.py` lets the committed files drift (TQ.2 F9's cost). | `tests/core/test_repro_report.py:20`; no test reads `docs/handoff/repro/` | TQ3c |
| F8 | Medium | T4.3's film tests take their expected values from `film.py`'s own constants, so `BYTE_MAX = 100.0` and `SRGB_EXPONENT = 2.2` pass; the junction test compares film with film. | `tests/core/test_film.py:27,110,123` | T4.3a |
| F9 | Medium | The row-flip test's rows are uniform, so a flip of both axes or a reversed RGBA order passes; the end-to-end test calls `to_blender_rows` on both sides. | `test_film.py:91-99`; `tests/blender/test_render_reference.py:148` | T4.3a |
| F10 | Medium | The end-to-end render covers scene_linear at 100 % only: the display_referred branch, `resolution_percentage` and `seed_per_frame` have no end-to-end check. | `src/blender/addon/session.py:49-52,73-74,101-104` | T4.3a |
| F11 | Medium | The monotonicity assert cannot fail: `np.diff` of a (257, 1) array runs along the axis of length 1, so it is empty. (Reader: Low; Opus: a test that cannot fail.) | `test_film.py:47-49` | T4.3a |
| F12 | Low | "Elapsed no longer grows" after a render is asserted only as positive. | `test_session.cpp:222-223` | TQ3a |
| F13 | Low | `start()` releases the GIL and sets STATE_RENDERING only after the snapshot, so two threads can both pass its guard; nothing says a Session and its Scene belong to one thread. No caller does it today. | `session.cpp:42,54,69`; `python.cpp:938` | TQ3a (session.h; the .pyi is a contract) |
| F14 | Low | If `std::thread` throws, the session stays STATE_RENDERING with no worker: `wait(-1)` never returns. | `session.cpp:69-71` | TQ3a |
| F15 | Low | `wait(inf)`, NaN or over about 9.2e9 s overflows the nanosecond cast (undefined behaviour). | `python.cpp:943`; `session.cpp:82` | TQ3a |
| F16 | Low | Two "device scene kept on a throwing path" checks run on an unchanged scene, where a rebuild gives identical bytes. | `src/test/test_scene.cpp:989-999` | TQ3c |
| F17 | Low | `lane_length=True` and `spiral_rotation=(0, 0, "a")` are untested wrong-type sites, as is a negative `k0_phase_lock_bits`; the message hard-codes 0…22 beside `PAINTERLY_K0_BITS`. | `python.cpp:302-305,330-331,414-416`; `test_api_contract.py:349-357` | TQ3b |
| F18 | Low | The real Python exception is cleared: `alpha=10**400` reports "must be a real number", and an error from a user's `__float__` vanishes. | `python.cpp:290-294,307-311` | TQ3b |
| F19 | Low | The selftest accepts any t below 0.75, so `SELFTEST_ORIGIN_Z = 1.4` passes. | `tests/core/test_import.py:48`; `src/blender/selftest.cpp:40` | TQ3b |
| F20 | Low | False comments: "the 16 hex digits after 0x1." are 13; "no per-source /arch switch" while `src/cycles/CMakeLists.txt:67-72` sets one; a third `make_ray`. | `test_scene.cpp:378,1038`; `src/test/CMakeLists.txt:59`; `src/test/test_bvh.cpp:167` | TQ3c |
| F21 | Low | TQ.2 F2 is half fixed: the prebuilt-Embree proofs still skip unless three `PAINTERLY_*` variables name this host's prepared inputs, which only BOOT-0b's verify sets. | `tests/core/test_embree_prebuilt.py:302` | By design (host inputs); open |
| F22 | Low | A comment gives the wrong reason an entry is dropped, and the `_under` check it relies on is untested (deleting it passes). | `test_embree_prebuilt.py:63-70`; `tools/embree_prebuilt.py:270` | TQ3c |
| F23 | Low | API test details: a missing `keep_alive` shows only as undefined behaviour; the GIL test's precondition rests on a hand-picked 500-quad mesh; the module docstring's "every check reads the .pyi" is false for `:167-244`; `:116-117` is dead. | `test_api_contract.py:3,116-117,427-439,618-629` | TQ3b |
| F24 | Low | `ALPHA = 0.01` repeats `ensemble.DEFAULT_ALPHA`; test names say "equivalent" for an "indistinguishable" verdict; the module purges `painterly_analysis` from `sys.modules` at collection. | `test_triangle_path.py:84-88,112,273,355` | T3.17e |
| F25 | Low | The experiments index still lists 010 as a DeepSeek draft, though `e155092` made its Conclusion final. | `experiments/README.md:19` | Fixed by Opus with this audit |
| F26 | Low | Experiment 010's `analyze.py` takes `wait() is True` as success, which an error or a cancel also returns, and records no build identity. | `experiments/010-2026-10-22-cpu-throughput/analyze.py:286-289` | Won't fix: the results are final and re-derived; the script stays as run |
| F27 | Low | `vendor_sync` reports every git failure as "not a file in upstream" or "not a directory". | `tools/vendor_sync.py:337-338` | After sprint S1 lands (the file is in its scope) |
| F28 | Low | The wheels path filter misses files its job runs (`tools/fetch_blender.py`, experiment 005, `tests/core/test_import.py`). | `.github/workflows/wheels.yml:12-19` | After sprint S1 lands (NODE24 edits the file) |
| F29 | Low | A test duplicates a parametrised case; `scenes.py` re-exports two constants nothing uses. | `tests/core/test_compare_results.py:178-184`; `tests/core/scenes.py:45,48` | TQ3c (the duplicate); the re-exports stay |
| F30 | Low | T4.3's half-inverse bound, 7·2^-53·0.5, is not a sound bound for one libm `pow` and a 2.4 power. | `test_film.py:116-127` | T4.3a |
| F31 | Low | Two docstrings name Blender's row order for functions that return the core's. | `src/blender/addon/film.py:92,107` | T4.3a |
| F32 | Low | The diagnostics header states an untested mechanism (near hits "cost nothing") and places the bias in per-path radiance, against its own open-cause sentence and its 1e-7 one-chain-per-pixel agreement. | `src/test/test_triangle_diagnostics.cpp:40-46,52-55` | T3.17e (after T3.17c, which edits the file) |
| F33 | Low | TOL-a's two derivations are loose though both tolerances hold: one bounds a single evaluation where two are compared; the other applies radix-2 operation counts to a 22-point transform. | `analysis/tests/test_report.py:570-583`; `analysis/tests/test_scale_metrics.py:157-170` | T3.17e |
| F34 | Low | `test_the_oracle_is_the_binary_of_this_build` recomputes the path `oracle_binary()` builds, so it cannot fail and shows nothing about freshness. | `tests/core/test_oracle_parity.py:160-167` | TQ3c |

## Rejected

None: every reader claim recorded above survived Opus's check. F11's severity was raised from Low.

## Open

- `painterly_session` and `painterly_util` start `std::thread`, but only `smallpaint_oracle` links `Threads::Threads`
  (`src/app/CMakeLists.txt:1-4`). Inside Python the interpreter brings libpthread, but a standalone test binary on
  glibc before 2.34 (manylinux_2_28) would fail at its first thread. TQ3a links it; M8's wheel run confirms.
- TQ.2 F1's FMA canary: `-mfma` now reaches `test_math_double3.cpp`; one build without `-ffp-contract=off` settles it.
- Whether block 68's pass in T3.17's slow test holds on every CPU: Embree picks SSE4.2, AVX2 or AVX-512 kernels at
  run time. Not asserted anywhere as evidence of a match (T3.17d).
- Experiment 010's "identical digests across two runs": the earlier `results.json` was overwritten, so it can be
  re-checked only by a rerun.
- Rule 5: `vendor_sync.py check` runs without `-I` (`tests/core/test_vendored.py:27-28`, `Makefile:96`). It hashes
  committed files only and reads no download, so rule 5 does not require `-I` there.

## Clean

- Every CHECK and REQUIRE in `test_triangle_diagnostics.cpp` holds on any machine: the BVH asserts, the per-hit
  normal by value (axis-aligned planes make Embree's edge differences exact), K against the kernel's own trace, no
  miss, and every path reaching bounces 0 and 1. No exact count of the chaotic walk is asserted.
- T4.3 moved the scene builders without a change: constants, knobs and builders are byte-identical, apart from
  `_material` becoming `material_of`, which nothing imported. T4.2a's every-scene test fails for an active-scene-only
  handler. TOL-a and the T7.1 revision stay in scope.
- Re-derived and correct: experiment 010's README figures against `results.json`; REPRO.json's ties and maxima; the
  two licence hashes of T3.28; the 4.4e-8 figure of T3.17's quad (4.371e-8); TQ.2 F3-F7's fixes.
- `3c9b821` (T3.26) and the session's worker/reader locking: nothing to report.
