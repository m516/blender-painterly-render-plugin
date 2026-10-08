"""Render jobs of experiment 001 (T1.6): does the compiled oracle reproduce the reference?

Ten configurations, each an ensemble of 8 pairs at 400 px with the GUI scene and ghost=all. The
scene and ghost are the oracle defaults, so they are left implicit: the options then match the
cache keys of the README example, which T1.7 shares.

Each configuration owns a disjoint block of 16 seeds (base seed = 16 * block index). No two
configurations share a seed, so their samples are independent, and the passes of different P do
not nest. The exception is the positive control ``img64`` (block 0, seeds 0-15), which is the
cache shared with the later experiments.
"""

from painterly_analysis.experiment import Job, ensemble_jobs

PAIRS = 8
SIZE = 400
BLOCK = 16  # seeds per configuration: 8 pairs x 2 half renders


def _ensemble(name: str, block: int, **options: object) -> list[Job]:
    return ensemble_jobs(name, PAIRS, base_seed=BLOCK * block, size=SIZE, **options)


# Keys are configuration names. Each value is the list of jobs of that configuration.
ENSEMBLES: dict[str, list[Job]] = {
    # chain=image at P = 16, 32, 64, 128, 256, 512 (H1, H3, H4, the figures).
    "img16": _ensemble("img16", 1, chain="image", passes=16),
    "img32": _ensemble("img32", 2, chain="image", passes=32),
    "img64": _ensemble("img64", 0, chain="image", passes=64),
    "img128": _ensemble("img128", 3, chain="image", passes=128),
    "img256": _ensemble("img256", 4, chain="image", passes=256),
    "img512": _ensemble("img512", 5, chain="image", passes=512),
    # Thread restarts (H2) and the generator (H3) at P = 64.
    "omp4_64": _ensemble("omp4_64", 6, chain="omp-restart:4", passes=64),
    "omp16_64": _ensemble("omp16_64", 7, chain="omp-restart:16", passes=64),
    "exact64": _ensemble("exact64", 8, chain="image", passes=64, halton="exact"),
    # Loop order (H5) at P = 64.
    "pm64": _ensemble("pm64", 9, chain="pixel-major", passes=64),
}

JOBS: list[Job] = [job for jobs in ENSEMBLES.values() for job in jobs]
