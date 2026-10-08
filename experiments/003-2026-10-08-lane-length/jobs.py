"""Render jobs of experiment 003 (T1.8): how long must a chain be?

Ten configurations, each an ensemble of 8 pairs at 400 px with P = 64 passes. The chain is the only
option that varies: ``chain=lane:L`` for L in {1, 2, 4, 8, 16, 32, 64, 128}, ``chain=row`` and
``chain=image``. The scene and ghost are the oracle defaults (``scene=gui``, ``ghost=all``), so they
are left implicit, as in experiments 001 and 002.

Each configuration owns a disjoint block of 16 seeds (base seed = 16 * block index). The positive
control ``image`` is block 0 (seeds 0-15) with the option set of experiment 001's ``img64``, so its
16 renders come from the cache. The card's first free block, 10, is taken by experiment 002 (blocks
10-18). The nine other configurations therefore take blocks 19-27, the first free blocks after 002's
last block, so every seed is globally unique.
"""

from painterly_analysis.experiment import Job, ensemble_jobs

PAIRS = 8
SIZE = 400
PASSES = 64  # P: passes per render
BLOCK = 16  # seeds per configuration: 8 pairs x 2 half renders
LANE_LENGTHS = (1, 2, 4, 8, 16, 32, 64, 128)  # L of chain=lane:L, ascending (H1, H2)

# Seed block of each configuration. The base seed is BLOCK times the block index.
BLOCKS: dict[str, int] = {
    "image": 0,  # experiment 001's img64: the positive control, reused from the cache
    "lane_1": 19,
    "lane_2": 20,
    "lane_4": 21,
    "lane_8": 22,
    "lane_16": 23,
    "lane_32": 24,
    "lane_64": 25,
    "lane_128": 26,
    "row": 27,
}


def build_ensembles(pairs: int, size: int) -> dict[str, list[Job]]:
    """The jobs of every configuration, keyed by configuration name.

    The experiment uses ``PAIRS`` and ``SIZE``. Other values exist only so that ``analyze.py`` can
    be validated on a smaller subset in a scratch cache.
    """

    def ensemble(name: str, chain: str) -> list[Job]:
        return ensemble_jobs(
            name,
            pairs,
            base_seed=BLOCK * BLOCKS[name],
            size=size,
            passes=PASSES,
            chain=chain,
        )

    return {
        "image": ensemble("image", "image"),
        **{
            f"lane_{length}": ensemble(f"lane_{length}", f"lane:{length}")
            for length in LANE_LENGTHS
        },
        "row": ensemble("row", "row"),
    }


ENSEMBLES: dict[str, list[Job]] = build_ensembles(PAIRS, SIZE)
JOBS: list[Job] = [job for jobs in ENSEMBLES.values() for job in jobs]
