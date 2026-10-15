# Owner decisions (binding)

The owner, Micah, made these decisions in the planning conversation (2026-10-08 to 2026-10-15). Engineering decisions
D1-D39 are in `decisions-M3.md`.

| Topic | Decision |
|---|---|
| Goal | Turn smallpaint_painterly (Károly Zsolnai-Fehér) into an accelerated Blender extension, using Cycles as the code template. **Preserving the typo-born painterly look and making it accessible to artists is the goal.** |
| Fidelity | Two modes: a reference mode that reproduces smallpaint, and an artist mode with knobs. |
| Materials | Node-graph evaluation: Cycles' SVM, vendored (M6). |
| Platforms | CPU only. |
| Backend | Native C++ like Cycles. No JAX or GLSL backends ("Cycles doesn't use any of these backends. Why should we?"). JAX is for compute-heavy analysis Python only. |
| Ghosting | Point and spot lights become ghost spheres, plus research into mesh ghosting (M9). |
| Viewport | Final render first. |
| Review | Tests, plus a strong-model review panel per milestone. |
| Implementers | "Proceed with all modules, and use Haiku": cheap models implement cards, strong models plan and review. |
| macOS | Low priority (2026-10-10, D39): no new macOS-specific work. The existing jobs stay while green. |
| Handoff | 2026-10-15: bundle the work so cheaper agents can take over (this directory). |

## Owner preferences that bind every agent
- **Hypotheses.** Test every hypothesis where possible. Report how it was derived, how it was tested and what the result
  was.
- **Experiments.** Numbered and dated sequentially. Each README has exactly Background, Hypothesis, Method, Results and
  Conclusion. Flag any experiment folder that does not follow this.
- **No magic numbers.** No thresholds, heuristic conditionals or hand-picked tolerances unless they are a named knob or a
  derived bound (CLAUDE.md rule 2). Prefer the more robust, more principled design over a patch and a knob.
- **Environment.** Virtual environments (uv, `.venv`). JAX for compute-heavy Python.
- **Code.** Clean, elegant, consistently named code. Spend one turn in about twelve on a quality audit, and reorganize when
  the structure makes a feature awkward.
- **Pace.** Quality over speed; any one process may take up to a day.
