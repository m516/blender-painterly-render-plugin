# TQ.1 — Code-quality audit (Opus): M0–M3 kernel layer
Milestone: M3 · Depends on: T3.12 · Agent: Opus

Spend this whole slot auditing quality, not adding features.

## Scope
`src/**` (excluding `third_party`), `analysis/**`, `tools/**`, `tests/**`, `Makefile`, `CMakeLists.txt`.

## Checklist
- **Nomenclature.** The same concept has the same name everywhere: chain/lane/pass/K/ghost/spiral frame, `painterly_*` prefixes in the kernel, Cycles naming style.
- **Organization.** The source layout and naming rules in `docs/architecture.md`:
  - our code under `src/painterly/<layer>/`, shims only under `src/cycles/shim/`;
  - `Painterly`/`KernelPainterly` type prefixes and `painterly_` kernel function prefixes;
  - dependency direction `painterly/util ← painterly/kernel ← painterly/bvh ← {painterly/integrator, painterly/scene} ← painterly/session ← blender` (`painterly/integrator` and `painterly/scene` never include each other), with no upward includes
    except the one the architecture allows: the kernel's Embree call, `painterly/kernel/bvh/bvh.h` → `painterly/bvh/embree.h`.
- **Duplication** that should be shared, and abstractions that are not pulling their weight.
- **CLAUDE.md rule 2.** No magic numbers, thresholds or heuristic conditionals without a knob or a citation.
- **Comments.** Every smallpaint-reproducing expression cites its line. No stale or misleading comments.
- **Build.** No warnings-as-noise; consistent CMake target naming; tests registered once.

## Output
Write findings to `docs/audits/TQ.1.md`: severity, file:line, issue, proposed fix.
- Apply only trivial renames and comment fixes yourself, in one commit `TQ.1: code-quality audit fixes`.
- Everything else becomes Opus fix-up cards.
