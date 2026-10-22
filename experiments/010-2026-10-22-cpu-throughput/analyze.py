#!/usr/bin/env python3
"""Analysis of experiment 010 (T3.18): CPU throughput of the native core.

Implements the Common definitions and H1 to H3 of ``README.md``, which is the specification. It
renders nothing to disk: it builds the scenes of ``tests/core/scenes.py``, times
``_painterly.Session`` directly, and writes ``results.json`` beside this file.

Run it after ``make build``, from the repository root:

    PYTHONPATH="$PWD/analysis" PAINTERLY_BUILD_DIR="$PWD/build/q" .venv/bin/python \
        experiments/010-2026-10-22-cpu-throughput/analyze.py

``PAINTERLY_BUILD_DIR`` (default ``build/dev``, a relative value resolved against the repository
root, as ``tests/conftest.py`` does) names the CMake build directory whose ``src/blender`` holds
``_painterly``. ``tests/core/scenes.py`` is loaded by file path, because a script run puts neither
directory on ``sys.path``.

The times vary from run to run, so the digest recorded for every configuration (the SHA-256 of the
``combined``, ``k_consumed`` and ``object_id`` buffers of a 1-pass, 1-thread render) is what makes
the scene setup checkable across runs; SPEC §3 makes those buffers independent of the thread
count and the batch size, and the digests must be identical between two runs.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np

EXP_DIR = Path(__file__).resolve().parent
EXPERIMENT = EXP_DIR.name
REPO_ROOT = EXP_DIR.parents[1]

# The image side of every timed render, in pixels: the experiments' reference side (001-009 render
# SPEC §9 at 400 px).
SIZE = 400
# The passes of one timed render. 16 passes is at most 1/16 = 6.25% of snapshot and object-id
# overhead (README, Common definitions, Measurement).
TIMED_PASSES = 16
# The repeats of every configuration, and the statistic reported of them (the card's Method).
REPEATS = 3
# The thread counts of H1 (the card).
THREAD_COUNTS = (1, 2, 4)
# SPEC §3: `chain=lane`'s `lane_length` default, in pixels.
LANE_LENGTH = 16
# The subdivided icosphere's level: 20 * 4**6 = 81,920 triangles, the level nearest the plan's
# 100k-triangle mesh (the card, H2).
ICOSPHERE_LEVEL = 6
# The icosphere's centre in smallpaint units and its radius. Inside SPEC §9's box, and 2.30 units
# from the light's centre (radius 0.5), so it does not intersect the light (README, Method).
ICOSPHERE_CENTRE = (0.0, 1.2, -3.5)
ICOSPHERE_RADIUS = 1.0
# The object id of the icosphere. SPEC §9's ten objects are ids 0-9, so 10 is the next free id.
ICOSPHERE_OBJECT_ID = 10
# smallpaint's `cl` of the box's walls (tests/core/scenes.py, REFERENCE_SCENE), the icosphere's
# diffuse colour.
ICOSPHERE_COLOUR = (6.0, 6.0, 6.0)
# The light's object id in SPEC §9: its list position (tests/core/scenes.py, REFERENCE_SCENE).
LIGHT_OBJECT_ID = 9
# The plan's X-throughput row: 1920x1080, the default `passes` and `chain=row` (H3).
PROJECTION_WIDTH = 1920
PROJECTION_HEIGHT = 1080
# `passes`' default, 1024 (src/painterly/scene/integrator.cpp, SOCKET_INT(passes, "Passes", 1024)).
PROJECTION_PASSES = 1024
# Seconds in an hour and in a minute, for H3's report.
SECONDS_PER_MINUTE = 60.0
SECONDS_PER_HOUR = 3600.0
# The digest render: 1 pass, 1 thread (README, Common definitions, Determinism).
DIGEST_PASSES = 1
DIGEST_THREADS = 1

#: Paths of one timed render, dimensionless: the image's pixels times its passes.
PATHS_PER_RENDER = SIZE * SIZE * TIMED_PASSES


def _load_scenes() -> ModuleType:
    """``tests/core/scenes.py``, loaded by file path.

    A script run puts neither ``tests/core`` nor the build directory on ``sys.path``, so the
    reference scene is loaded the way ``tests/core/test_triangle_path.py`` loads it.
    """
    path = REPO_ROOT / "tests" / "core" / "scenes.py"
    spec = importlib.util.spec_from_file_location("scenes", path)
    if spec is None or spec.loader is None:  # pragma: no cover - a broken checkout
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _import_painterly() -> ModuleType:
    """``_painterly`` from the build directory ``PAINTERLY_BUILD_DIR`` names.

    A relative value is resolved against the repository root, as ``tests/conftest.py`` does.
    """
    build_dir = Path(os.environ.get("PAINTERLY_BUILD_DIR", "build/dev"))
    if not build_dir.is_absolute():
        build_dir = REPO_ROOT / build_dir
    sys.path.insert(0, str(build_dir / "src" / "blender"))
    import _painterly  # noqa: PLC0415 - imported only after the build directory is first on sys.path

    return _painterly


def _midpoint(
    vertices: list[np.ndarray], midpoints: dict[tuple[int, int], int], a: int, b: int
) -> int:
    """The index of the edge (a, b)'s midpoint, projected onto the unit sphere.

    ``vertices`` grows by the new vertex; ``midpoints`` caches the edge so that the two triangles
    sharing it share one vertex.
    """
    key = (a, b) if a < b else (b, a)
    if key not in midpoints:
        middle = vertices[a] + vertices[b]
        vertices.append(middle / np.linalg.norm(middle))
        midpoints[key] = len(vertices) - 1
    return midpoints[key]


def icosphere(subdivisions: int) -> tuple[np.ndarray, np.ndarray]:
    """The unit icosphere of ``subdivisions`` levels, as (V, 3) vertices and (T, 3) triangles.

    The regular icosahedron's 12 vertices and 20 faces, every triangle split into four by its edge
    midpoints projected onto the unit sphere, once per level. Level *s* has 20·4^s triangles and
    10·4^s + 2 vertices, so level 6 is 81,920 triangles and 40,962 vertices.

    The vertex coordinates are float64; the triangles wind counter-clockwise seen from outside, so
    the geometric normal points away from the centre (T3.17's orientation convention).
    """
    # The icosahedron: the 12 vertices (0, +-1, +-t) and its cyclic permutations, with
    # t = (1 + sqrt 5) / 2 the golden ratio, normalized onto the unit sphere.
    golden = (1.0 + 5.0**0.5) / 2.0
    vertices = [
        np.array(point, dtype=np.float64)
        for point in (
            (-1, golden, 0),
            (1, golden, 0),
            (-1, -golden, 0),
            (1, -golden, 0),
            (0, -1, golden),
            (0, 1, golden),
            (0, -1, -golden),
            (0, 1, -golden),
            (golden, 0, -1),
            (golden, 0, 1),
            (-golden, 0, -1),
            (-golden, 0, 1),
        )
    ]
    for vertex in vertices:
        vertex /= np.linalg.norm(vertex)
    triangles: list[tuple[int, int, int]] = [
        (0, 11, 5),
        (0, 5, 1),
        (0, 1, 7),
        (0, 7, 10),
        (0, 10, 11),
        (1, 5, 9),
        (5, 11, 4),
        (11, 10, 2),
        (10, 7, 6),
        (7, 1, 8),
        (3, 9, 4),
        (3, 4, 2),
        (3, 2, 6),
        (3, 6, 8),
        (3, 8, 9),
        (4, 9, 5),
        (2, 4, 11),
        (6, 2, 10),
        (8, 6, 7),
        (9, 8, 1),
    ]
    for _ in range(subdivisions):
        midpoints: dict[tuple[int, int], int] = {}
        subdivided: list[tuple[int, int, int]] = []
        for a, b, c in triangles:
            ab = _midpoint(vertices, midpoints, a, b)
            bc = _midpoint(vertices, midpoints, b, c)
            ca = _midpoint(vertices, midpoints, c, a)
            subdivided.extend([(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)])
        triangles = subdivided
    return np.array(vertices, dtype=np.float64), np.array(triangles, dtype=np.int64)


def _add_icosphere(scene: Any, vertices: np.ndarray, triangles: np.ndarray) -> None:
    """Add the icosphere to ``scene`` as one diffuse mesh with object id 10."""
    material = scene.add_material(lobes=[("diffuse", ICOSPHERE_COLOUR, 0.0)])
    placed = (vertices * ICOSPHERE_RADIUS + np.array(ICOSPHERE_CENTRE)).astype(np.float32)
    tri_material = np.full(len(triangles), material, dtype=np.int32)
    mesh = scene.add_mesh(
        np.ascontiguousarray(placed),
        np.ascontiguousarray(triangles, dtype=np.uint32),
        tri_material,
        None,
    )
    scene.add_object(mesh, np.eye(4, dtype=np.float32), ICOSPHERE_OBJECT_ID)


def _load_average() -> list[float]:
    """The three load averages, as ``uptime`` prints them (the three fields of /proc/loadavg)."""
    return [float(value) for value in os.getloadavg()]


def _cpu_record() -> dict[str, Any]:
    """The CPU model, the thread count and the load, with the command each came from.

    ``lscpu`` reads /sys, which a sandboxed worker does not have, so its failure is recorded and
    the model name is then taken from /proc/cpuinfo's ``model name`` line.
    """
    try:
        completed = subprocess.run(
            ["lscpu"], capture_output=True, text=True, check=False, timeout=60
        )
        lscpu_output = completed.stdout
        lscpu_error = completed.stderr.strip() or None
    except (OSError, subprocess.SubprocessError) as error:  # pragma: no cover - host dependent
        lscpu_output = ""
        lscpu_error = str(error)
    model = None
    for line in lscpu_output.splitlines():
        if line.startswith("Model name:"):
            model = line.split(":", 1)[1].strip()
    cpuinfo_model = None
    cpuinfo_path = Path("/proc/cpuinfo")
    if cpuinfo_path.is_file():
        for line in cpuinfo_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                cpuinfo_model = line.split(":", 1)[1].strip()
                break
    return {
        "cpu_model_lscpu": model,
        "cpu_model_proc_cpuinfo": cpuinfo_model,
        "lscpu_stdout": lscpu_output,
        "lscpu_stderr": lscpu_error,
        "os_cpu_count": os.cpu_count(),
        "affinity_cpu_count": len(os.sched_getaffinity(0)),
        "load_average_at_start": _load_average(),
    }


def _build_scene(
    painterly: ModuleType,
    scenes: ModuleType,
    name: str,
    icosphere_mesh: tuple[np.ndarray, np.ndarray] | None,
) -> Any:
    """The scene of one configuration (README, Common definitions, Scene)."""
    scene = painterly.Scene()
    if name == "analytic":
        scenes.build_smallpaint_scene(scene, size=SIZE)
    elif name == "triangles":
        scenes.build_smallpaint_scene_triangles(scene, size=SIZE)
    elif name == "triangles+icosphere":
        scenes.build_smallpaint_scene_triangles(scene, size=SIZE)
        if icosphere_mesh is None:  # pragma: no cover - a programming error
            raise RuntimeError("the icosphere mesh was not built")
        _add_icosphere(scene, *icosphere_mesh)
    else:  # pragma: no cover - a programming error
        raise ValueError(f"unknown scene {name!r}")
    return scene


def _timed_render(painterly: ModuleType, scene: Any, chain: str, threads: int) -> dict[str, Any]:
    """One timed render: 16 passes at ``threads``, with the load before and after it.

    The elapsed time is from the ``start()`` call to the return of ``wait()``, so it includes the
    scene snapshot and the object-id pass (README, Common definitions, Measurement).
    """
    scene.set_integrator(chain=chain, lane_length=LANE_LENGTH)
    session = painterly.Session(scene, threads)
    load_before = _load_average()
    started = time.perf_counter()
    session.start(TIMED_PASSES, 1)
    finished = session.wait()
    elapsed = time.perf_counter() - started
    load_after = _load_average()
    if finished is not True:  # pragma: no cover - the core always finishes
        raise RuntimeError(f"the render of {chain}/{threads} did not finish")
    return {
        "elapsed_s": elapsed,
        "paths_per_s": PATHS_PER_RENDER / elapsed,
        "load_before": load_before,
        "load_after": load_after,
    }


def _digest_render(painterly: ModuleType, scene: Any, chain: str) -> dict[str, str]:
    """The SHA-256 of the three output buffers of a 1-pass, 1-thread render.

    SPEC §3: the buffers are bit-identical for any thread count and batch size, so the digests of
    two runs of this script must agree while their times need not.
    """
    scene.set_integrator(chain=chain, lane_length=LANE_LENGTH)
    session = painterly.Session(scene, DIGEST_THREADS)
    session.start(DIGEST_PASSES, 1)
    if session.wait() is not True:  # pragma: no cover - the core always finishes
        raise RuntimeError(f"the digest render of {chain} did not finish")
    return {
        "combined": hashlib.sha256(np.ascontiguousarray(session.combined()).tobytes()).hexdigest(),
        "k_consumed": hashlib.sha256(
            np.ascontiguousarray(session.k_consumed()).tobytes()
        ).hexdigest(),
        "object_id": hashlib.sha256(
            np.ascontiguousarray(session.object_id()).tobytes()
        ).hexdigest(),
    }


def _configurations() -> list[dict[str, Any]]:
    """The eleven configurations of README's Method table."""
    configs: list[dict[str, Any]] = []
    for chain in ("row", "lane", "image"):
        for threads in THREAD_COUNTS:
            configs.append({"scene": "analytic", "chain": chain, "threads": threads})
    configs.append({"scene": "triangles", "chain": "row", "threads": 4})
    configs.append({"scene": "triangles+icosphere", "chain": "row", "threads": 4})
    return configs


def _name(config: dict[str, Any]) -> str:
    """The results key of one configuration, e.g. ``analytic-row-t4``."""
    chain = "lane16" if config["chain"] == "lane" else config["chain"]
    return f"{config['scene']}-{chain}-t{config['threads']}"


def _median(values: list[float]) -> float:
    return statistics.median(values)


def _speedup(medians: dict[int, float], threads: int) -> float:
    """The median throughput at ``threads`` divided by the median at ``threads // 2``."""
    return medians[threads] / medians[threads // 2]


def _h1(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """H1 and the two reported chains, with the card's decision rule.

    The rule: throughput at T threads is greater than at T/2 in all 3 repeats, for T = 2 and 4.
    Repeats are paired by their index.
    """
    result: dict[str, Any] = {}
    for chain in ("row", "lane", "image"):
        medians = {
            threads: _median(
                records[_name({"scene": "analytic", "chain": chain, "threads": threads})][
                    "paths_per_s"
                ]
            )
            for threads in THREAD_COUNTS
        }
        per_thread: dict[str, Any] = {}
        for threads in (2, 4):
            half = [
                records[_name({"scene": "analytic", "chain": chain, "threads": threads})][
                    "paths_per_s"
                ][index]
                > records[_name({"scene": "analytic", "chain": chain, "threads": threads // 2})][
                    "paths_per_s"
                ][index]
                for index in range(REPEATS)
            ]
            per_thread[str(threads)] = {
                "all_repeats_greater": all(half),
                "greater_per_repeat": half,
                "speedup": _speedup(medians, threads),
            }
        result[chain] = {"median_paths_per_s": medians, "per_thread": per_thread}
    result["supported"] = all(
        result["row"]["per_thread"][str(threads)]["all_repeats_greater"] for threads in (2, 4)
    )
    return result


def _h2(records: dict[str, dict[str, Any]], triangle_counts: dict[str, int]) -> dict[str, Any]:
    """H2: the three medians and the two ratios, with no threshold (the card)."""
    medians = {
        scene: _median(
            records[_name({"scene": scene, "chain": "row", "threads": 4})]["paths_per_s"]
        )
        for scene in ("analytic", "triangles", "triangles+icosphere")
    }
    return {
        "median_paths_per_s": medians,
        "triangle_counts": triangle_counts,
        "ratio_triangles_analytic": medians["triangles"] / medians["analytic"],
        "ratio_icosphere_triangles": medians["triangles+icosphere"] / medians["triangles"],
    }


def _projection(paths_per_s: float) -> dict[str, Any]:
    """H3's projection: the time of 1920x1080 x 1024 passes at ``paths_per_s``.

    ``seconds``, ``hours`` and ``minutes`` are exact quotients; ``hours_whole`` and
    ``minutes_whole`` are the truncation the card's "in hours and minutes" report needs.
    """
    paths = PROJECTION_WIDTH * PROJECTION_HEIGHT * PROJECTION_PASSES
    seconds = paths / paths_per_s
    return {
        "paths": paths,
        "seconds": seconds,
        "hours": seconds / SECONDS_PER_HOUR,
        "minutes": seconds / SECONDS_PER_MINUTE,
        "hours_whole": int(seconds // SECONDS_PER_HOUR),
        "minutes_whole": int((seconds % SECONDS_PER_HOUR) // SECONDS_PER_MINUTE),
    }


def _check_light_unoccluded(
    painterly: ModuleType, scenes: ModuleType, icosphere_mesh: tuple[np.ndarray, np.ndarray]
) -> dict[str, int]:
    """The icosphere does not occlude the light (README, Method, The icosphere).

    The set of pixels whose unjittered primary hit is the light must be the same in the
    ``triangles`` and the ``triangles+icosphere`` scenes. The object-id map is one primary hit per
    pixel, so one pass suffices.
    """
    counts: dict[str, int] = {}
    for name in ("triangles", "triangles+icosphere"):
        scene = _build_scene(painterly, scenes, name, icosphere_mesh)
        scene.set_integrator(chain="row", lane_length=LANE_LENGTH)
        session = painterly.Session(scene, DIGEST_THREADS)
        session.start(DIGEST_PASSES, 1)
        if session.wait() is not True:  # pragma: no cover - the core always finishes
            raise RuntimeError(f"the object-id render of {name} did not finish")
        counts[name] = int((session.object_id() == LIGHT_OBJECT_ID).sum())
    if counts["triangles"] != counts["triangles+icosphere"]:
        raise RuntimeError(
            "the icosphere occludes the light: "
            f"{counts['triangles+icosphere']} light pixels against {counts['triangles']}"
        )
    return counts


def main() -> int:
    # _painterly first: scenes.py imports it, so the build directory must be on sys.path already.
    painterly = _import_painterly()
    scenes = _load_scenes()
    machine = _cpu_record()

    vertices, triangles = icosphere(ICOSPHERE_LEVEL)
    icosphere_mesh = (vertices, triangles)
    light_pixels = _check_light_unoccluded(painterly, scenes, icosphere_mesh)

    configs = _configurations()
    records: dict[str, dict[str, Any]] = {}
    # The scene setup is timed once per configuration; it is not part of the timed render.
    for config in configs:
        scene = _build_scene(painterly, scenes, config["scene"], icosphere_mesh)
        records[_name(config)] = {
            **config,
            "paths_per_s": [],
            "elapsed_s": [],
            "loads": [],
            "digest": _digest_render(painterly, scene, config["chain"]),
        }

    # The repeats are interleaved: repeat i times every configuration in the table's order, so the
    # three repeats of one configuration are spread over the run (README, Common definitions).
    for _ in range(REPEATS):
        for config in configs:
            scene = _build_scene(painterly, scenes, config["scene"], icosphere_mesh)
            timed = _timed_render(painterly, scene, config["chain"], config["threads"])
            record = records[_name(config)]
            record["paths_per_s"].append(timed["paths_per_s"])
            record["elapsed_s"].append(timed["elapsed_s"])
            record["loads"].append({"before": timed["load_before"], "after": timed["load_after"]})

    for record in records.values():
        record["median_paths_per_s"] = _median(record["paths_per_s"])
        record["median_elapsed_s"] = _median(record["elapsed_s"])

    triangle_counts = {
        "analytic": 0,
        "triangles": 2 * 6,  # six quads of two triangles (tests/core/scenes.py)
        "triangles+icosphere": 2 * 6 + len(triangles),
    }
    h1 = _h1(records)
    h2 = _h2(records, triangle_counts)
    h3 = {
        "configuration": _name({"scene": "analytic", "chain": "row", "threads": 4}),
        "paths_per_s": h2["median_paths_per_s"]["analytic"],
        "projection": _projection(h2["median_paths_per_s"]["analytic"]),
        "projection_triangles": _projection(h2["median_paths_per_s"]["triangles"]),
        "projection_triangles_icosphere": _projection(
            h2["median_paths_per_s"]["triangles+icosphere"]
        ),
    }
    machine["load_average_at_end"] = _load_average()

    results = {
        "experiment": EXPERIMENT,
        "size": SIZE,
        "timed_passes": TIMED_PASSES,
        "paths_per_timed_render": PATHS_PER_RENDER,
        "repeats": REPEATS,
        "thread_counts": list(THREAD_COUNTS),
        "lane_length": LANE_LENGTH,
        "icosphere": {
            "level": ICOSPHERE_LEVEL,
            "triangles": int(len(triangles)),
            "vertices": int(len(vertices)),
            "centre": list(ICOSPHERE_CENTRE),
            "radius": ICOSPHERE_RADIUS,
            "object_id": ICOSPHERE_OBJECT_ID,
            "colour": list(ICOSPHERE_COLOUR),
            "light_pixels": light_pixels,
        },
        "machine": machine,
        "configurations": records,
        "h1": h1,
        "h2": h2,
        "h3": h3,
    }

    # The results writer of painterly_analysis: sorted keys, two spaces, a final newline, and a
    # ValueError for any non-finite number.
    sys.path.insert(0, str(REPO_ROOT / "analysis"))
    from painterly_analysis.report import write_results_json  # noqa: PLC0415

    write_results_json(EXP_DIR / "results.json", results)
    _print_tables(results)
    return 0


def _print_tables(results: dict[str, Any]) -> None:
    """The printed tables of README's ``## Results``."""
    machine = results["machine"]
    model = machine["cpu_model_lscpu"] or machine["cpu_model_proc_cpuinfo"]
    print(f"machine: {model}")
    print(
        f"threads: os.cpu_count()={machine['os_cpu_count']}, "
        f"sched_getaffinity={machine['affinity_cpu_count']}"
    )
    if machine["lscpu_stderr"]:
        print(f"lscpu: {machine['lscpu_stderr']}")
    print(f"load average at start: {machine['load_average_at_start']}")
    print(f"load average at end: {machine['load_average_at_end']}")
    print(
        f"timed render: {results['size']} px, {results['timed_passes']} passes, "
        f"{results['paths_per_timed_render']} paths, {results['repeats']} repeats"
    )
    print()
    print("| configuration | elapsed s (3) | paths/s (3) | median paths/s | load before -> after |")
    print("|---|---|---|---|---|")
    for name, record in results["configurations"].items():
        elapsed = ", ".join(f"{value:.3f}" for value in record["elapsed_s"])
        rates = ", ".join(f"{value:.0f}" for value in record["paths_per_s"])
        loads = "; ".join(
            f"{entry['before'][0]:.2f} -> {entry['after'][0]:.2f}" for entry in record["loads"]
        )
        print(f"| {name} | {elapsed} | {rates} | {record['median_paths_per_s']:.0f} | {loads} |")
    print()
    h1 = results["h1"]
    print("| chain | T | greater in all 3 repeats | speedup |")
    print("|---|---|---|---|")
    for chain in ("row", "lane", "image"):
        for threads in ("2", "4"):
            entry = h1[chain]["per_thread"][threads]
            print(
                f"| {chain} | {threads} | {entry['all_repeats_greater']} | {entry['speedup']:.3f} |"
            )
    print(f"H1 supported: {h1['supported']}")
    print()
    h2 = results["h2"]
    print("| scene | triangles | median paths/s |")
    print("|---|---|---|")
    for scene in ("analytic", "triangles", "triangles+icosphere"):
        print(
            f"| {scene} | {h2['triangle_counts'][scene]} | {h2['median_paths_per_s'][scene]:.0f} |"
        )
    print(
        f"triangles/analytic = {h2['ratio_triangles_analytic']:.4f}, "
        f"(triangles+icosphere)/triangles = {h2['ratio_icosphere_triangles']:.4f}"
    )
    print()
    projection = results["h3"]["projection"]
    print(
        f"H3: {projection['paths']:.0f} paths at {results['h3']['paths_per_s']:.0f} paths/s = "
        f"{projection['seconds']:.0f} s = {projection['hours']:.3f} h = "
        f"{projection['minutes']:.1f} min "
        f"({projection['hours_whole']} h {projection['minutes_whole']} min)"
    )
    print(
        f"digest of the analytic-row-t1 configuration: {
            json.dumps(results['configurations']['analytic-row-t1']['digest'], sort_keys=True)
        }"
    )


if __name__ == "__main__":
    raise SystemExit(main())
