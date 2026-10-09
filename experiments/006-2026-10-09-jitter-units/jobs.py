"""Render jobs of experiment 006: which jitter unit makes the look independent of resolution?

Thirteen configurations, each an ensemble of 8 pairs with P = 64 passes (README, Method). The scene
and ghost are the oracle defaults (``scene=gui``, ``ghost=all``), so they are left implicit.

Three jitter families:
- image-plane: the oracle default 1/700 at every size (not passed, so the cache keys equal 004's);
- pixel: the reference 2/7 px at every size, i.e. 1/350 at 200 px and 1/1400 at 800 px;
- zero: jitter 0.

Seven configurations reuse 004's cached option sets and seed blocks. The six new ones take blocks
33-38, the first free blocks after 004's last block (32), so every seed is globally unique.

``build_ensembles(pairs, scale)`` divides every size by ``scale``. The experiment uses ``scale=1``.
Other values exist only so that ``analyze.py`` can be validated on a smaller subset.
"""

from fractions import Fraction

from painterly_analysis.experiment import Job, ensemble_jobs

PAIRS = 8
PASSES = 64  # P: passes per render, as in 004
BLOCK = 16  # seeds per configuration: 8 pairs x 2 half renders
REFERENCE_SIDE = 400  # the reference image side in pixels (SPEC §7)
# The reference jitter: 1/700 image-plane units at the 400 px reference
# (smallpaint painterly.cpp:291-292).
REFERENCE_JITTER = Fraction(1, 700)
# A pixel is 2/s image-plane units wide (SPEC §7, tan(pi/4) = 1), so the reference jitter is
# 2/7 px.
PIXEL_JITTER_PX = REFERENCE_JITTER * REFERENCE_SIDE / 2


def pixel_jitter(side: int) -> Fraction:
    """Image-plane jitter whose maximum displacement is PIXEL_JITTER_PX pixels at this side."""
    return PIXEL_JITTER_PX * 2 / side


assert Fraction(2, 7) == PIXEL_JITTER_PX  # SPEC §7's default in pixels
assert pixel_jitter(REFERENCE_SIDE) == REFERENCE_JITTER


def _jitter_option(jitter: Fraction) -> dict[str, object]:
    """The oracle option for an image-plane jitter, omitted at the oracle default (as in 004)."""
    return {} if jitter == REFERENCE_JITTER else {"jitter": float(jitter)}


# name: (native size, extra oracle options, seed block). The base seed is BLOCK times the block.
DESIGN: dict[str, tuple[int, dict[str, object], int]] = {
    # image chain, image-plane jitter (004 s200, 001 img64 / 004 s400, 004 s800)
    "s200": (200, {}, 28),
    "s400": (400, {}, 0),
    "s800": (800, {}, 29),
    # image chain, pixel jitter (new; 004 s800_j1400)
    "s200_px": (200, _jitter_option(pixel_jitter(200)), 33),
    "s800_px": (800, _jitter_option(pixel_jitter(800)), 30),
    # row chain, image-plane jitter (004 row_s200, 003 row / 004 row_s400, 004 row_s800)
    "row_s200": (200, {"chain": "row"}, 31),
    "row_s400": (400, {"chain": "row"}, 27),
    "row_s800": (800, {"chain": "row"}, 32),
    # row chain, pixel jitter (new)
    "row_s200_px": (200, {"chain": "row", **_jitter_option(pixel_jitter(200))}, 34),
    "row_s800_px": (800, {"chain": "row", **_jitter_option(pixel_jitter(800))}, 35),
    # image chain, zero jitter (new)
    "j0_s200": (200, {"jitter": 0.0}, 36),
    "j0_s400": (400, {"jitter": 0.0}, 37),
    "j0_s800": (800, {"jitter": 0.0}, 38),
}


def build_ensembles(pairs: int = PAIRS, scale: int = 1) -> dict[str, list[Job]]:
    """The jobs of every configuration, keyed by configuration name.

    Every native size is divided by ``scale``. The jitter options stay those of the native size,
    so a smoke run keeps the design's option structure.
    """
    if scale < 1 or any(size % scale for size, _, _ in DESIGN.values()):
        raise ValueError(f"scale must divide every native size, got {scale}")
    return {
        name: ensemble_jobs(
            name,
            pairs,
            base_seed=BLOCK * block,
            size=size // scale,
            passes=PASSES,
            **{"chain": "image", **extra},
        )
        for name, (size, extra, block) in DESIGN.items()
    }


ENSEMBLES: dict[str, list[Job]] = build_ensembles(PAIRS, 1)
JOBS: list[Job] = [job for jobs in ENSEMBLES.values() for job in jobs]
