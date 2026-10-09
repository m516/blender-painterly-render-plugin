# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
#
# CONTRACT: Opus-owned. The public Python API of the native module `_painterly`
# (the counterpart of Cycles' `_cycles`). src/blender/python.cpp must implement exactly this.
# Arrays are numpy; shapes and dtypes are part of the contract. All positions/directions are
# world space unless noted. Indices returned by add_* are dense, starting at 0.
"""Native core of the Painterly render engine (mirrors Cycles' _cycles)."""

from typing import Literal, TypedDict

import numpy as np
import numpy.typing as npt

class VersionInfo(TypedDict):
    version: str
    compiler: str
    build_type: str
    stable_abi: bool

def version_info() -> VersionInfo: ...
def selftest() -> dict: ...

class SocketInfo(TypedDict):
    name: str  # socket identifier, e.g. "lane_length"
    type: Literal["boolean", "int", "uint", "float", "enum", "vector"]
    # bool | int | float | str (enum identifier) | tuple[float, float, float] (vector)
    default: object
    enum_items: list[str]  # empty unless type == "enum"; identifiers in C++ enum value order
    min: float | None
    max: float | None
    soft_min: float | None
    soft_max: float | None
    ui_name: str
    description: str
    group: Literal["Sampling", "Brush", "Path", "Lights", "Film"]

def integrator_sockets() -> list[SocketInfo]:
    """Reflection of PainterlyIntegrator (SPEC §8). Blender properties are generated from this."""

LobeKind = Literal["diffuse", "mirror", "glass", "transparent"]
# (kind, weight, ior); ior is ignored unless kind is "glass"
Lobe = tuple[LobeKind, tuple[float, float, float], float]

class Scene:
    def __init__(self) -> None: ...
    def clear(self) -> None: ...

    # --- materials: lobe mixtures (SPEC §6). M6 adds add_shader (SVM node graphs). ---
    def add_material(
        self,
        lobes: list[Lobe],  # at least one lobe
        emission: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> int: ...

    # --- analytic primitives, kept in call order (SPEC §5, §9) ---
    def add_sphere(
        self,
        center: tuple[float, float, float],
        radius: float,
        material: int,
        intersection: Literal["ghost", "exact"] = "ghost",
        object_id: int = -1,
        # (axis, cos_half_angle, blend); axis: unit vector (normalized by the caller)
        spot: tuple[tuple[float, float, float], float, float] | None = None,
    ) -> int: ...
    def add_plane(
        self,
        normal: tuple[float, float, float],
        d: float,
        material: int,
        object_id: int = -1,
    ) -> int: ...

    # --- triangle meshes and instances ---
    def add_mesh(
        self,
        vertices: npt.NDArray[np.float32],  # (V, 3) object space
        triangles: npt.NDArray[np.uint32],  # (T, 3) vertex indices
        tri_material: npt.NDArray[np.int32],  # (T,) scene material indices
        corner_normals: npt.NDArray[np.float32] | None = None,  # (T, 3, 3) object space
    ) -> int: ...
    def add_object(
        self,
        mesh: int,
        object_to_world: npt.NDArray[np.float32],  # (3, 4) or (4, 4) row-major
        object_id: int = -1,
    ) -> int: ...

    # --- camera, world, integrator ---
    # Cameras take no jitter: the integrator socket `jitter` (a fraction of the fitted image side,
    # SPEC §7) is the only jitter knob, converted per camera type in the core.
    def set_camera_smallpaint(self, width: int, height: int) -> None: ...
    def set_camera_perspective(
        self,
        width: int,
        height: int,
        raster_to_camera: npt.NDArray[np.float64],  # (4, 4) row-major
        camera_to_world: npt.NDArray[np.float64],  # (3, 4) or (4, 4) row-major
        # the fitted image side (Blender sensor_fit, resolved by the add-on)
        fit: Literal["horizontal", "vertical"],
    ) -> None: ...
    def set_camera_orthographic(
        self,
        width: int,
        height: int,
        raster_to_camera: npt.NDArray[np.float64],
        camera_to_world: npt.NDArray[np.float64],
        fit: Literal["horizontal", "vertical"],
    ) -> None: ...
    def set_background(self, radiance: tuple[float, float, float]) -> None: ...
    def set_spiral_object(
        self,
        # (3, 3) row-major rotation, used when spiral_frame == "object" (SPEC §1)
        rotation: npt.NDArray[np.float64],
    ) -> None: ...
    def add_sun(
        self,
        # toward the sun, world space (normalized by the core)
        direction: tuple[float, float, float],
        angle: float,  # angular diameter, radians (Blender sun `angle`)
        radiance: tuple[float, float, float],
    ) -> int: ...
    def set_integrator(self, **knobs: object) -> None:
        """Set PainterlyIntegrator sockets by name; unknown names or bad values raise ValueError."""
    def get_integrator(self) -> dict[str, object]: ...

class Session:
    """One render of a Scene snapshot. The snapshot is taken in start()."""

    def __init__(self, scene: Scene, threads: int = 0) -> None:
        """threads=0 means hardware concurrency."""
    def start(self, passes: int, batch: int = 1) -> None:
        """Begin rendering asynchronously.

        Output is bit-identical for any threads/batch (SPEC §3).
        """
    def wait(self, timeout: float | None = None) -> bool:
        """Block (GIL released) until done/cancelled/error or timeout; True if finished."""
    def cancel(self) -> None: ...
    def progress(self) -> dict:
        """{'state': 'idle'|'rendering'|'done'|'cancelled'|'error', 'passes_done': int,
        'passes_total': int, 'elapsed': float, 'error': str}"""
    def combined(self) -> npt.NDArray[np.float64]:
        """(H, W, 3) per-pixel radiance SUMS over completed passes; row 0 = top (SPEC §0)."""
    def k_consumed(self) -> npt.NDArray[np.uint64]:
        """(H, W) diffuse draws consumed per pixel over completed passes."""
    def object_id(self) -> npt.NDArray[np.int32]:
        """(H, W) object_id of the unjittered primary hit, -1 on miss."""
