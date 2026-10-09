# Architecture

Painterly is a small render engine with Cycles' anatomy. It is written to reproduce one beautiful bug exactly
(`docs/spec.md`), then generalized so artists can control it.

```
            Blender 5.2 (Python)                                   _painterly (C++20, one stable-ABI module)
 ┌───────────────────────────────────────────┐      ┌──────────────────────────────────────────────────────────────────┐
 │ src/blender/addon/  (the extension)       │      │ src/blender/python.cpp     nanobind bindings (= Cycles _cycles)   │
 │  __init__.py   PainterlyRender engine     │      │ src/painterly/session/     PainterlySession: async, cancellable   │
 │  engine.py     thin facade (as Cycles)    │ ───▶ │ src/painterly/integrator/  PainterlyPathTrace: lane scheduler     │
 │  session.py    render loop, RenderResult  │      │ src/painterly/scene/       PainterlyScene, PainterlyIntegrator    │
 │  properties.py generated from reflection  │ ◀─── │ src/painterly/bvh/         Embree 4 (static, namespaced)          │
 │  ui.py presets.py operators.py ...        │      │ src/painterly/kernel/      header-only, POD, ccl_device style     │
 │  sync/  camera geometry light world       │      │   camera/ geom/ closure/ light/ sample/ integrator/ film/ bvh/   │
 │         material reference shader/        │      │ src/painterly/util/        double3 math, deterministic thread pool│
 └───────────────────────────────────────────┘      │ src/cycles/                builds vendored Cycles (cycles_util,   │
                                                      │   shim/                    cycles_graph, …) with OIIO-free shims  │
                                                      └──────────────────────────────────────────────────────────────────┘
                                                      third_party/cycles/  verbatim Cycles files (pinned, hashed)
 src/app/smallpaint_oracle.cpp  ── reference renderer (minimal diff of smallpaint) ── ground truth for every test
 analysis/painterly_analysis/   ── JAX metrics + statistics; experiments/ ── numbered, dated experiment reports
```

## Source layout and naming

All C++ code lives in one namespace, `painterly` (`CCL_NAMESPACE_BEGIN`). That includes the vendored Cycles code, so
Cycles' names (`Scene`, `KernelData`, `KernelCamera`, `Ray`, `scene_intersect`, `CameraType`, …) and our own share one
namespace and one include path. Three rules keep them apart:

1. **Paths.**
   - `src/painterly/<layer>/` holds our engine: `util`, `kernel`, `bvh`, `scene`, `integrator`, `session`. Upstream Cycles has no
     `painterly/` directory, so nothing here can shadow a vendored header. Includes read `#include "painterly/kernel/types.h"`.
   - `src/cycles/shim/<upstream path>` holds headers and sources that deliberately shadow an upstream Cycles path, so vendored
     code compiles without OIIO, TBB, OCIO or glog. Each starts with `Shim: replaces Cycles <path> …`.
   - A shimmed path is never also vendored (`tests/core/test_shims.py`).
   - `src/cycles/CMakeLists.txt` builds the vendored code into `cycles_*` libraries. Their public include order is
     `src/cycles/shim`, `third_party/cycles`, `third_party`, `src`.
2. **Types.** Every type defined under `src/painterly/` carries the prefix `Painterly` (host, integrator, session), or
   `KernelPainterly` (kernel device data, as Cycles' `Kernel*`). Kernel globals are `PainterlyGlobalsCPU`, passed as
   `PainterlyGlobals`, as Cycles passes `KernelGlobals`.
3. **Kernel functions** carry the prefix `painterly_`. Enumerators carry a domain prefix that Cycles does not use
   (`CHAIN_`, `LOBE_`, `PURPOSE_`, …), or `PAINTERLY_` where Cycles does (`PAINTERLY_CAMERA_PERSPECTIVE`).

The Python API (`_painterly.Scene`, `_painterly.Session`) keeps short names: Python modules are their own namespace.

Why: M6 evaluates Blender shader graphs with Cycles' SVM, vendored verbatim. Those headers need Cycles' own
`kernel/types.h` (`ShaderData`, `KernelData`, …) and a Cycles-shaped `Scene` (`scene->shader_manager`, `dscene.data.svm_usage`),
in the same translation units as the painterly kernel. The research behind this rule is in the M6 notes:
the SVM include closure is 149 files, and 49 of 108 evaluator cases read `ShaderData`.

## Dependency direction
`painterly/util ← painterly/kernel ← {painterly/bvh, painterly/scene} ← painterly/integrator ← painterly/session ← blender`.
Every painterly library links `cycles_util`, and `painterly/scene` also links `cycles_graph`.
- The kernel never includes `scene/` or STL headers.
- `PainterlyScene::device_update()` is the only bridge. It produces `KernelPainterlyData` plus arrays
  (`painterly/kernel/types.h`, `painterly/kernel/globals.h`).

## Why not fork Cycles?
The painterly integrator throws away most of what makes Cycles Cycles:
- NEE/MIS;
- Russian roulette;
- stateless per-pixel sampling;
- Fresnel;
- adaptive sampling;
- tiles.

Painterly keeps Cycles' *shape* and copies its reusable parts verbatim: util math, hashing and transforms; node reflection;
SVM node evaluators and their `compile()` bodies.

It also avoids clashing with the Cycles that lives inside Blender's own process, and it stays small enough that every
behaviour can be tested against the oracle. The Python sync emits Cycles node type and socket names, so a later fork would
reuse it unchanged.

## Determinism contract
Output is bit-identical for any thread count and batch size, because lanes are independent and pixels within a lane are
processed in SPEC §3 order.

On analytic scenes the core equals `smallpaint_oracle` **bit for bit** (`tests/core/test_oracle_parity.py`):
- kernel math is double precision with smallpaint's operation order (`painterly/util/math_double3.h`);
- every build uses `-ffp-contract=off`.

## Isolation inside Blender
`_painterly` exports exactly one symbol, `PyInit__painterly`, and shares no C++ library with Blender's process:
- Embree is static, in its own API namespace, with internal tasking (no TBB);
- the C++ runtime is static;
- vendored Cycles code is compiled into `namespace painterly`.

`tools/symbol_audit.py` enforces this on every build. Experiment 005 found that on Linux Blender's process-wide TBB malloc
proxy also serves the module's `malloc`. libc shares that allocator, so allocation stays coherent.

## Distribution
extensions.blender.org requires pure-Python extensions (ToS §3.6, August 2026), so Painterly is self-hosted:
- per-platform extension zips, each with one cp312-abi3 wheel;
- published as GitHub Releases;
- a remote-repository `index.json` on GitHub Pages.
