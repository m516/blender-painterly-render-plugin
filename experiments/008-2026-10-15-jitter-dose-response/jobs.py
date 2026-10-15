"""Render jobs of experiment 008: the jitter dose-response on the row chain at 400 px.

Six configurations, each an ensemble of 8 pairs with P = 64 passes per half render, ``chain=row``
and side 400 px (README, Method). The scene and ghost are the oracle defaults (``scene=gui``,
``ghost=all``), so they are left implicit.

Units. The dose is the jitter as a fraction ``f`` of the image side, the SPEC §7 knob. The oracle's
``--jitter`` is in image-plane units, ``j = 2 f``, because the image plane spans 2 units across the
side. The doses are f = 0, 1/5600, 1/2800, 1/1400, 1/700 and 1/350 of the side, i.e. j = 0, 1/2800,
1/1400, 1/700, 1/350 and 1/175 image-plane units. A configuration ``fN`` has f = 1/N of the side,
and ``f0`` has f = 0.

Two configurations reuse experiment 006's cached option sets and seed blocks:
- ``f0`` is 006 ``row_j0_s400`` (block 40), with ``jitter=0.0`` passed as in 006;
- ``f1400`` is 006 ``row_s400`` (block 27; also 004 ``row_s400`` and 003 ``row``). Its j = 1/700 is
  the oracle default, so it is not passed and the cache keys are identical.
The four new configurations take blocks 42-45, the first free blocks after 006's last block (41).

``build_ensembles(pairs, scale)`` divides the side by ``scale``. The experiment uses ``scale=1``.
Other values exist only so that ``analyze.py`` can be smoke-tested on a smaller subset. A fraction
of the side is the same image-plane jitter at every side, so a smoke run keeps every dose.
"""

from fractions import Fraction

from painterly_analysis.experiment import Job, ensemble_jobs

PAIRS = 8
PASSES = 64  # P: passes per half render, as in 006
BLOCK = 16  # seeds per configuration: 8 pairs x 2 half renders
SIDE = 400  # the reference image side in pixels (SPEC §7)
CHAIN = "row"  # the artist default chain (SPEC §3, experiment 003)
# The oracle's default image-plane jitter, 1/700 (smallpaint painterly.cpp:291-292). It is not
# passed, so that f1400's option set equals 006's row_s400.
ORACLE_DEFAULT_JITTER = Fraction(1, 700)
# Image-plane units per fraction of the side: the image plane spans 2 units across the fitted side
# (SPEC §7, tan(pi/4) = 1). This is a definition, not a tuned value.
IMAGE_PLANE_UNITS_PER_SIDE = 2

# name: (jitter as a fraction f of the side, seed block). The base seed is BLOCK times the block.
# The order is the dose order, from low to high f (README, Common definitions).
DESIGN: dict[str, tuple[Fraction, int]] = {
    "f0": (Fraction(0), 40),  # 006 row_j0_s400 (cache)
    "f5600": (Fraction(1, 5600), 42),  # new
    "f2800": (Fraction(1, 2800), 43),  # new
    "f1400": (Fraction(1, 1400), 27),  # 006 row_s400 = 004 row_s400 = 003 row (cache)
    "f700": (Fraction(1, 700), 44),  # new
    "f350": (Fraction(1, 350), 45),  # new
}
ORDER: tuple[str, ...] = tuple(DESIGN)
# Reused configurations: 008 name -> (earlier experiment, its ensemble name), with identical option
# sets and seeds (README, Method).
REUSED: dict[str, tuple[str, str]] = {"f0": ("006", "row_j0_s400"), "f1400": ("006", "row_s400")}


def image_plane_jitter(fraction: Fraction) -> Fraction:
    """The oracle's ``--jitter`` in image-plane units for a jitter of ``fraction`` of the side."""
    return IMAGE_PLANE_UNITS_PER_SIDE * fraction


def jitter_option(fraction: Fraction) -> dict[str, object]:
    """The oracle option for a jitter of ``fraction`` of the side, omitted at the oracle default."""
    jitter = image_plane_jitter(fraction)
    return {} if jitter == ORACLE_DEFAULT_JITTER else {"jitter": float(jitter)}


assert image_plane_jitter(DESIGN["f1400"][0]) == ORACLE_DEFAULT_JITTER  # SPEC §7 default


def build_ensembles(pairs: int = PAIRS, scale: int = 1) -> dict[str, list[Job]]:
    """The jobs of every configuration, keyed by configuration name, in dose order.

    The side is ``SIDE // scale``. The jitter option depends only on the fraction of the side, so it
    is the same at every scale.
    """
    if scale < 1 or SIDE % scale:
        raise ValueError(f"scale must divide the side {SIDE}, got {scale}")
    return {
        name: ensemble_jobs(
            name,
            pairs,
            base_seed=BLOCK * block,
            size=SIDE // scale,
            passes=PASSES,
            chain=CHAIN,
            **jitter_option(fraction),
        )
        for name, (fraction, block) in DESIGN.items()
    }


ENSEMBLES: dict[str, list[Job]] = build_ensembles(PAIRS, 1)
JOBS: list[Job] = [job for jobs in ENSEMBLES.values() for job in jobs]
