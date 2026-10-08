#!/usr/bin/env python3
"""Native coexistence (T2.3): _painterly inside `blender -b`, next to Blender's own Cycles.

run.sh runs this file as:
  $BLENDER -b --factory-startup --python-exit-code 1 --python coexist.py -- <build_dir>
  $BLENDER -b --factory-startup --python-exit-code 1 --python coexist.py -- <module_dir>

<build_dir> is a CMake build directory whose module lives in <build_dir>/src/blender.
<module_dir> is a directory that holds the _painterly module itself, such as a
wheel-installed module (T2.4 reuses this form).

1. Put the module directory first on sys.path, import _painterly, and record
   version_info() and selftest().
2. Set the scene to Cycles on the CPU device, 64 x 64 pixels, 4 samples.
3. Repeat 20 times: a Cycles render with write_still=False, then _painterly.selftest().
   Every selftest must equal the first one.
4. Write out/coexist.json and one out/cycles_NN.png per render. Any exception, or any
   selftest that differs from the first, raises after the JSON is written, so Blender exits
   with status 1 (--python-exit-code 1).
"""

import json
import sys
import time
from pathlib import Path

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = SCRIPT_DIR / "out"
RESULT_JSON = OUT_DIR / "coexist.json"
# The number of alternating Cycles renders and selftests (H2).
ITERATIONS = 20
# Cycles settings that keep each render tiny and fixed (T2.3 card, step 2).
RENDER_SAMPLES = 4
RESOLUTION_PX = 64
# The Render Result image holds the last render. Blender names it this way in every version.
RENDER_RESULT_IMAGE = "Render Result"


def _text(value: bytes | str) -> str:
    return value.decode() if isinstance(value, bytes) else str(value)


def module_dir_from_argument(argument: str) -> Path:
    """A build directory keeps the module under src/blender; any other directory is the module's."""
    given = Path(argument).resolve()
    build_module_dir = given / "src" / "blender"
    return build_module_dir if build_module_dir.is_dir() else given


def script_argument() -> str:
    """The one argument after the Blender '--' separator."""
    argv = sys.argv
    if "--" not in argv or argv.index("--") + 1 >= len(argv):
        raise SystemExit("usage: blender -b --python coexist.py -- <build_dir | module_dir>")
    return argv[argv.index("--") + 1]


def configure_scene() -> bpy.types.Scene:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = RENDER_SAMPLES
    scene.render.resolution_x = RESOLUTION_PX
    scene.render.resolution_y = RESOLUTION_PX
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    if scene.camera is None:
        raise RuntimeError("the startup scene has no camera to render")
    return scene


def run(module_dir: Path, record: dict) -> None:
    sys.path.insert(0, str(module_dir))
    import _painterly  # imported only after the module directory is first on sys.path

    record["module_file"] = _painterly.__file__
    record["version_info"] = dict(_painterly.version_info())
    first = dict(_painterly.selftest())
    record["selftest"] = first

    scene = configure_scene()
    for index in range(ITERATIONS):
        start = time.perf_counter()
        status = bpy.ops.render.render(write_still=False)
        render_s = time.perf_counter() - start
        if "FINISHED" not in status:
            raise RuntimeError(f"Cycles render {index} returned {sorted(status)}")
        bpy.data.images[RENDER_RESULT_IMAGE].save_render(
            filepath=str(OUT_DIR / f"cycles_{index:02d}.png"), scene=scene
        )

        start = time.perf_counter()
        result = dict(_painterly.selftest())
        selftest_s = time.perf_counter() - start
        record["iterations"].append(
            {
                "index": index,
                "render_s": render_s,
                "selftest_s": selftest_s,
                "selftest": result,
                "equal_to_first": result == first,
            }
        )


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    module_dir = module_dir_from_argument(script_argument())
    record = {
        "blender_version": bpy.app.version_string,
        "blender_version_tuple": list(bpy.app.version),
        "build_platform": _text(bpy.app.build_platform),
        "binary_path": _text(bpy.app.binary_path),
        "module_dir": str(module_dir),
        "module_file": None,
        "version_info": None,
        "selftest": None,
        "iterations": [],
        "iterations_requested": ITERATIONS,
        "all_selftests_equal_first": False,
        "error": None,
    }
    try:
        run(module_dir, record)
    except Exception as error:  # recorded here, then the process fails below
        record["error"] = f"{type(error).__name__}: {error}"
    iterations = record["iterations"]
    record["all_selftests_equal_first"] = (
        record["error"] is None
        and len(iterations) == ITERATIONS
        and all(item["equal_to_first"] for item in iterations)
    )
    OUT_DIR.mkdir(exist_ok=True)
    RESULT_JSON.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if not record["all_selftests_equal_first"]:
        reason = record["error"] or "a selftest differs from the first one"
        raise RuntimeError(f"coexistence failed: {reason}")
    print(
        f"coexist: Blender {record['blender_version']}, {len(iterations)} alternating renders and "
        f"selftests, every selftest equal to the first: {record['selftest']}"
    )


if __name__ == "__main__":
    main()
