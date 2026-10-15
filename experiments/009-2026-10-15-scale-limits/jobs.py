"""Render jobs of experiment 009: image-locking above 800 px, and the 200 px departure.

Every job uses ``chain=row`` and P = 64 passes per half render (README, Method). The scene and ghost
are the oracle defaults (``scene=gui``, ``ghost=all``), so they are left implicit.

Units. ``f`` is the jitter as a fraction of the image side, the SPEC §7 knob. The oracle's
``--jitter`` is in image-plane units, ``j = 2 f``, because the image plane spans 2 units across the
side. The largest displacement is ``j * s / 2 = f * s`` px at side ``s``. Three footprints:
- ``f = 1/1400``: j = 1/700, the oracle default. It is not passed, so the cache keys equal 006's.
- ``f = 0``: ``jitter=0.0``, passed as in 006.
- ``f = 1/400``: j = 1/200, i.e. 1/2 px at 200 px and 2 px at 800 px.

Each entry of ``DESIGN`` is one seed block of 8 pairs (16 half renders, consecutive seeds).
- Six blocks are experiment 006's cached blocks 27, 31, 32, 39, 40 and 41, with identical option
  sets (``REUSED``).
- The new blocks are 46-67, after experiment 008's blocks 42-45 (README, Method, "Block
  allocation"): 46-47 are the 1600 px blocks, 48-51 the H2 set at f = 1/400, and 52-67 the H3
  fresh set.
``CONFIGURATIONS`` lists the blocks of each configuration, first block first. ``BLOCK_SETS`` names
the blocks of each comparison's block set (README, Common definitions, "Block sets").

``build_ensembles(pairs, scale)`` divides every side by ``scale``. The experiment uses ``scale=1``.
Other values exist only so that ``analyze.py`` can be smoke-tested on a smaller subset. A fraction
of the side is the same image-plane jitter at every side, so a smoke run keeps every footprint.
"""

from fractions import Fraction

from painterly_analysis.experiment import Job, ensemble_jobs

PAIRS = 8  # pairs per seed block, as in 006
PASSES = 64  # P: passes per half render, as in 006
BLOCK = 16  # seeds per block: 8 pairs x 2 half renders
REFERENCE_SIDE = 400  # the reference image side in pixels (SPEC §7)
CHAIN = "row"  # the artist default chain (SPEC §3, experiment 003)
# The oracle's default image-plane jitter, 1/700 (smallpaint painterly.cpp:291-292). It is not
# passed, so that the reused option sets equal 006's.
ORACLE_DEFAULT_JITTER = Fraction(1, 700)
# Image-plane units per fraction of the side: the image plane spans 2 units across the fitted side
# (SPEC §7, tan(pi/4) = 1). This is a definition, not a tuned value.
IMAGE_PLANE_UNITS_PER_SIDE = 2

F_DEFAULT = Fraction(1, 1400)  # SPEC §7 default, a fraction of the side
F_ZERO = Fraction(0)
F_PIXEL_200 = Fraction(1, 400)  # half-width 1/2 px at 200 px: the footprint covers one 200 px pixel


def _block_name(configuration: str, block: int, first: int) -> str:
    """The first block keeps the configuration's name (006's name for a reused block)."""
    return configuration if block == first else f"{configuration}_b{block}"


# configuration: (native side in px, jitter f as a fraction of the side, its seed blocks, first
# block first). The base seed of block b is BLOCK * b.
_LAYOUT: dict[str, tuple[int, Fraction, tuple[int, ...]]] = {
    # f = 1/1400: 006 row_s200, row_s400, row_s800 (cached first blocks); new 1600 px; fresh blocks
    "row_s200": (200, F_DEFAULT, (31, 52, 56, 58, 60)),
    "row_s400": (400, F_DEFAULT, (27,)),
    "row_s800": (800, F_DEFAULT, (32, 53, 57, 59, 61)),
    "row_s1600": (1600, F_DEFAULT, (46,)),
    # f = 0: 006 row_j0_s200, row_j0_s400, row_j0_s800 (cached first blocks); new 1600 px; fresh
    "row_j0_s200": (200, F_ZERO, (39, 54, 62)),
    "row_j0_s400": (400, F_ZERO, (40,)),
    "row_j0_s800": (800, F_ZERO, (41, 55, 63)),
    "row_j0_s1600": (1600, F_ZERO, (47,)),
    # f = 1/400 (new): H2 set 48-51, H3 fresh set 64-67
    "row_f400_s200": (200, F_PIXEL_200, (48, 50, 64, 66)),
    "row_f400_s800": (800, F_PIXEL_200, (49, 51, 65, 67)),
}

# block name: (native side in px, jitter f as a fraction of the side, seed block)
DESIGN: dict[str, tuple[int, Fraction, int]] = {
    _block_name(name, block, blocks[0]): (side, fraction, block)
    for name, (side, fraction, blocks) in _LAYOUT.items()
    for block in blocks
}
# configuration: its block names, first block first. The first block is the 8-pair set.
CONFIGURATIONS: dict[str, tuple[str, ...]] = {
    name: tuple(_block_name(name, block, blocks[0]) for block in blocks)
    for name, (_, _, blocks) in _LAYOUT.items()
}


def _blocks(configuration: str, *blocks: int) -> tuple[str, ...]:
    first = _LAYOUT[configuration][2][0]
    assert all(block in _LAYOUT[configuration][2] for block in blocks)
    return tuple(_block_name(configuration, block, first) for block in blocks)


# Block sets (README, Common definitions): block set -> configuration -> its block names.
# - "h2": the f = 1/400 blocks of H2, on which D_400 is also located.
# - "fresh": H3's blocks, none of which selected a departure set (D_0 and D_1400 were selected on
#   006's blocks 39/41 and 31/32, D_400 is located on blocks 48-51).
BLOCK_SETS: dict[str, dict[str, tuple[str, ...]]] = {
    "h2": {
        "row_f400_s200": _blocks("row_f400_s200", 48, 50),
        "row_f400_s800": _blocks("row_f400_s800", 49, 51),
    },
    "fresh": {
        "row_s200": _blocks("row_s200", 52, 56, 58, 60),
        "row_s800": _blocks("row_s800", 53, 57, 59, 61),
        "row_j0_s200": _blocks("row_j0_s200", 54, 62),
        "row_j0_s800": _blocks("row_j0_s800", 55, 63),
        "row_f400_s200": _blocks("row_f400_s200", 64, 66),
        "row_f400_s800": _blocks("row_f400_s800", 65, 67),
    },
}

# Reused blocks: 009 block name -> (earlier experiment, its ensemble name), with identical option
# sets and seeds (README, Method).
REUSED: dict[str, tuple[str, str]] = {
    "row_s200": ("006", "row_s200"),
    "row_s400": ("006", "row_s400"),
    "row_s800": ("006", "row_s800"),
    "row_j0_s200": ("006", "row_j0_s200"),
    "row_j0_s400": ("006", "row_j0_s400"),
    "row_j0_s800": ("006", "row_j0_s800"),
}

assert len({block for _, _, block in DESIGN.values()}) == len(DESIGN)
assert sorted(n for blocks in CONFIGURATIONS.values() for n in blocks) == sorted(DESIGN)
assert all(
    DESIGN[name][:2] == DESIGN[blocks[0]][:2]
    for blocks in CONFIGURATIONS.values()
    for name in blocks
)
# No fresh block is a reused block, an H2 block or a first (8-pair-set) block.
_FRESH_SET = {n for blocks in BLOCK_SETS["fresh"].values() for n in blocks}
assert not _FRESH_SET & (set(REUSED) | {n for b in BLOCK_SETS["h2"].values() for n in b})
assert not _FRESH_SET & {blocks[0] for blocks in CONFIGURATIONS.values()}


def image_plane_jitter(fraction: Fraction) -> Fraction:
    """The oracle's ``--jitter`` in image-plane units for a jitter of ``fraction`` of the side."""
    return IMAGE_PLANE_UNITS_PER_SIDE * fraction


def jitter_option(fraction: Fraction) -> dict[str, object]:
    """The oracle option for a jitter of ``fraction`` of the side, omitted at the oracle default."""
    jitter = image_plane_jitter(fraction)
    return {} if jitter == ORACLE_DEFAULT_JITTER else {"jitter": float(jitter)}


assert image_plane_jitter(F_DEFAULT) == ORACLE_DEFAULT_JITTER  # SPEC §7 default


def build_ensembles(pairs: int = PAIRS, scale: int = 1) -> dict[str, list[Job]]:
    """The jobs of every block, keyed by block name, in ``DESIGN`` order.

    Every native side is divided by ``scale``. The jitter option depends only on the fraction of
    the side, so it is the same at every scale.
    """
    if scale < 1 or any(side % scale for side, _, _ in DESIGN.values()):
        raise ValueError(f"scale must divide every native side, got {scale}")
    return {
        name: ensemble_jobs(
            name,
            pairs,
            base_seed=BLOCK * block,
            size=side // scale,
            passes=PASSES,
            chain=CHAIN,
            **jitter_option(fraction),
        )
        for name, (side, fraction, block) in DESIGN.items()
    }


ENSEMBLES: dict[str, list[Job]] = build_ensembles(PAIRS, 1)
# Rendered smallest side first, so the short jobs finish in the first calls (README, Commands:
# with --budget 90 a 1600 px job then starts only at the beginning of a call). The order does not
# change any result.
JOBS: list[Job] = sorted(
    (job for jobs in ENSEMBLES.values() for job in jobs),
    key=lambda job: dict(job.options)["size"],
)
