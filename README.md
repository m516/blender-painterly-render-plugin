# Painterly — smallpaint's beautiful bug as a Blender render engine

Painterly reproduces, and makes controllable, the painterly look of Károly Zsolnai-Fehér's `smallpaint_painterly`. That look comes from a Halton-sequence bug in smallpaint. The native core is new C++20, laid out and named like Cycles, and the Blender side is a pure-Python extension that mirrors Cycles too.

## Status

pre-alpha; under construction per docs/plan.md

## Layout

```
CMakeLists.txt  pyproject.toml (scikit-build-core + nanobind; uv dependency-groups dev/analysis/blender)  Makefile  uv.lock
src/                       # mirrors Cycles' src/ + Blender's intern/cycles/blender
  util/  param.h(ustring/TypeDesc shim) task.h(deterministic pool) thread.h(≥2 MB stacks)
  kernel/ types.h globals.h camera/ geom/ film/ integrator/path.h svm/svm.h svm/closure_painterly.h
          painterly/{sampler.h, ghost.h, bounce.h}    device/cpu/kernel.cpp
  bvh/embree.{h,cpp}   graph/(shim glue)   scene/{scene,object,mesh,light,camera,film,integrator,background,image,shader,shader_graph,svm}.{h,cpp}  scene/shader_nodes/<node>.cpp
  integrator/path_trace.{h,cpp}   # lane scheduler
  session/{session,buffers}.{h,cpp}
  blender/python.cpp               # nanobind module _painterly
  blender/addon/                   # THE EXTENSION (pure Python): blender_manifest.toml __init__.py engine.py properties.py ui.py presets.py operators.py version_update.py
                                   #   sync/{depsgraph,camera,geometry,light,world,image}.py  sync/shader/{flatten,node_table,export}.py
  app/smallpaint_oracle.cpp        # reference CLI (like Cycles' src/app)
  test/                            # doctest unit tests (like Cycles' src/test)
third_party/cycles/ (vendored verbatim; VENDORED.md path+sha256; patches/)   third_party/smallpaint/ (original sources, MIT)
analysis/painterly_analysis/ (JAX metric suite + oracle runner)   tests/ (pytest: core/, blender/, data/reference/, scenes/)
tools/ (vendor_sync.py, symbol_audit.py, gen_node_registry.py, make_reference_scene.py, fetch_blender.py)
experiments/  docs/{spec.md, architecture.md, tasks/, artist-guide.md}  .github/workflows/
```

## Development

- `make env`: create or update the project virtual environment (`.venv`, via uv).
- `make build`: CMake/Ninja Release build into `build/dev`.
- `make check`: lint, build and test.

## Credits

- Károly Zsolnai-Fehér for smallpaint and its painterly bug.
- Michael Oppitz for the GUI port.
- The Blender Foundation and Cycles authors for the template.

## Licence

GPL-3.0-or-later; see THIRD_PARTY_NOTICES.md.
