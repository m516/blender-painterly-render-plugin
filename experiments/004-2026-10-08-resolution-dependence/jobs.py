"""Render jobs of experiment 004 (T1.9): is the texture pixel-locked? (Resolution and jitter units.)

Four configurations, each an ensemble of 8 pairs with P = 64 passes and ``chain=image``, the
reference chain (SPEC §3). The scene and ghost are the oracle defaults (``scene=gui``,
``ghost=all``), so they are left implicit, as in experiments 001-003.

- ``s200``: size 200, jitter at the oracle default 1/700 (not passed).
- ``s400``: size 400, jitter at the default. Its options equal those of experiment 001's
  ``img64``, so its 16 renders are block 0 (seeds 0-15) from the cache. This is the positive
  control.
- ``s800``: size 800, jitter at the default 1/700 (not passed).
- ``s800_j1400``: size 800, jitter 1/1400. The only option that differs from ``s800``.

Each configuration owns a disjoint block of 16 seeds (base seed = 16 * block index). Block 0 is
shared with experiment 001 on purpose. The three new configurations take blocks 28-30, the first
free blocks after experiment 003's last block (27), so every seed is globally unique.

``build_ensembles(pairs, scale)`` divides every size by ``scale``. The experiment uses
``scale=1``. ``analyze.py`` uses ``pairs=2, scale=4`` (sizes 50, 100 and 200, the smoke run) and
``pairs=2, scale=2`` (sizes 100, 200 and 400) only to validate itself on a smoke subset in a scratch
cache (README D6).
"""

from painterly_analysis.experiment import Job, ensemble_jobs

PAIRS = 8
PASSES = 64  # P: passes per render
BLOCK = 16  # seeds per configuration: 8 pairs x 2 half renders
JITTER_TUNED = 1.0 / 1400.0  # image-plane jitter of s800_j1400 (SPEC §7); the default is 1/700

# name: (native size, extra oracle options, seed block). The base seed is BLOCK times the block.
DESIGN: dict[str, tuple[int, dict[str, object], int]] = {
    "s200": (200, {}, 28),
    "s400": (400, {}, 0),  # the positive control, experiment 001's img64 (reused from the cache)
    "s800": (800, {}, 29),
    "s800_j1400": (800, {"jitter": JITTER_TUNED}, 30),
    # Amendment before rendering (Opus, M1 review 3): the artist-mode chain at the same sizes (H1d).
    "row_s200": (200, {"chain": "row"}, 31),
    # experiment 003's row (same option set): reused from the cache
    "row_s400": (400, {"chain": "row"}, 27),
    "row_s800": (800, {"chain": "row"}, 32),
}


def build_ensembles(pairs: int = PAIRS, scale: int = 1) -> dict[str, list[Job]]:
    """The jobs of every configuration, keyed by configuration name.

    Every native size is divided by ``scale``. The experiment uses ``pairs=PAIRS`` and ``scale=1``.
    Other values exist only so that ``analyze.py`` can be validated on a smaller subset.
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
