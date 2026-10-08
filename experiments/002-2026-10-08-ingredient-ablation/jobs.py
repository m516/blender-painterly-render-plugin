"""Render jobs of experiment 002 (T1.7): which smallpaint ingredients are necessary for the look?

Ten configurations: a positive control and nine variants. Each variant changes exactly one option
of the positive control. Every configuration is an ensemble of 8 pairs at 400 px with P = 64
passes. The positive control is ``chain=image`` with the oracle defaults (``scene=gui``,
``ghost=all``), so its option set equals that of experiment 001's ``img64`` and its renders are
reused from the cache.

Each configuration owns a disjoint block of 16 seeds (base seed = 16 * block index). Block 0 is
the positive control, shared with experiment 001. The nine variants take blocks 10-18, the first
free blocks after experiment 001's last block (9), so every seed is globally unique.
"""

from painterly_analysis.experiment import Job, ensemble_jobs

PAIRS = 8
SIZE = 400
PASSES = 64  # P: passes per render
BLOCK = 16  # seeds per configuration: 8 pairs x 2 half renders


def build_ensembles(pairs: int, size: int) -> dict[str, list[Job]]:
    """The jobs of every configuration, keyed by configuration name.

    The experiment uses ``PAIRS`` and ``SIZE``. Other values exist only so that ``analyze.py`` can
    be validated on a smaller subset in a scratch cache.
    """

    def ensemble(name: str, block: int, **options: object) -> list[Job]:
        return ensemble_jobs(
            name, pairs, base_seed=BLOCK * block, size=size, passes=PASSES, **options
        )

    return {
        "positive": ensemble("positive", 0, chain="image"),
        "ghost_none": ensemble("ghost_none", 10, chain="image", ghost="none"),
        "ghost_lights": ensemble("ghost_lights", 11, chain="image", ghost="lights"),
        "alpha_025": ensemble("alpha_025", 12, chain="image", alpha=0.25),
        "alpha_05": ensemble("alpha_05", 13, chain="image", alpha=0.5),
        "alpha_1": ensemble("alpha_1", 14, chain="image", alpha=1.0),
        "u2_independent": ensemble("u2_independent", 15, chain="image", u2="independent"),
        "u2_base3": ensemble("u2_base3", 16, chain="image", u2="base3"),
        "per_path_start": ensemble("per_path_start", 17, chain="lane:1"),
        "stop_at_emitter": ensemble(
            "stop_at_emitter", 18, chain="image", continue_after_emitter=False
        ),
    }


ENSEMBLES: dict[str, list[Job]] = build_ensembles(PAIRS, SIZE)
JOBS: list[Job] = [job for jobs in ENSEMBLES.values() for job in jobs]
