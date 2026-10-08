"""Experiment harness: cached, resumable, time-budgeted oracle ensembles (T1.4).

An experiment declares its renders as data: a jobs file with ``JOBS: list[Job]``. Each job renders
once with ``smallpaint_oracle`` into ``cache_root()/<job_key>/``. The key covers the exact options,
the seed, the meta.json contract version and the oracle binary's sha256, so a rebuilt oracle never
reuses stale renders. A ``done`` marker is written after each successful render.

``python -m painterly_analysis.experiment run jobs.py --budget 540`` renders what fits in the time
budget. It exits 0 once no job remains and 3 otherwise, so callers loop until 0.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import importlib.util
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from . import metrics
from .io import OracleRender, read_oracle
from .oracle import REPO_ROOT, oracle_binary, run_many

# meta.json "oracle_version" written by smallpaint_oracle (src/app/smallpaint_oracle.cpp:557).
ORACLE_VERSION = "1"
# Hex digits of the sha256 that name a job's cache directory (T1.4 card).
_KEY_HEX_DIGITS = 16
# Per-command time budget of the CLI, so no single command exceeds about 9 minutes (T1.4 Goal).
DEFAULT_BUDGET_SECONDS = 540.0
# Exit status of `run` while jobs remain. It is not an error: callers loop until the status is 0.
EXIT_REMAINING = 3
# Read size when hashing the oracle binary. It affects I/O only, never the digest.
_HASH_CHUNK_BYTES = 1 << 20
_DONE = "done"


@dataclass(frozen=True)
class Job:
    """One oracle render.

    ``options`` are oracle flags without the leading dashes, stored as a sorted tuple of
    (name, value) pairs so that a job is hashable. ``seed`` is passed to the oracle as ``--seed``.
    """

    name: str
    options: tuple[tuple[str, object], ...]
    seed: int

    @classmethod
    def make(cls, name: str, seed: int, **options: Any) -> Job:
        """Build a job; the keyword arguments are the oracle options."""
        if "threads" in options:
            raise ValueError("threads is set by the harness (one thread per job), not by a job")
        return cls(name=name, options=tuple(sorted(options.items())), seed=seed)


@dataclass(frozen=True)
class RunStatus:
    """Outcome of ``run_jobs``: jobs with a ``done`` marker, jobs still missing, wall seconds."""

    completed: int
    remaining: int
    elapsed: float


@functools.cache
def _file_sha256(path: str, mtime_ns: int, size: int) -> str:
    # mtime and size only key the cache: a rebuilt binary has a new mtime and gets a fresh digest.
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _oracle_sha256() -> str:
    path = oracle_binary()
    if not path.is_file():
        raise FileNotFoundError(f"{path} is missing: run `make build` first")
    stat = path.stat()
    return _file_sha256(str(path), stat.st_mtime_ns, stat.st_size)


def job_key(job: Job) -> str:
    """Cache key: the first 16 hex digits of the sha256 of the canonical JSON of the job's options,
    seed, ``ORACLE_VERSION`` and the oracle binary's sha256. The job name is not part of the key."""
    canonical = {
        "options": dict(job.options),
        "seed": job.seed,
        "oracle_version": ORACLE_VERSION,
        "oracle_sha256": _oracle_sha256(),
    }
    text = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:_KEY_HEX_DIGITS]


def cache_root() -> Path:
    """``$PAINTERLY_CACHE``, then ``/renders``. Without the variable the base is ``<repo>/.cache``.

    A relative ``$PAINTERLY_CACHE`` is resolved against the repository root, as
    ``PAINTERLY_BUILD_DIR`` is in ``oracle.py``.
    """
    base = Path(os.environ.get("PAINTERLY_CACHE") or REPO_ROOT / ".cache")
    if not base.is_absolute():
        base = REPO_ROOT / base
    return base / "renders"


def _job_dir(key: str) -> Path:
    return cache_root() / key


def _is_done(directory: Path) -> bool:
    return (directory / _DONE).is_file()


def _mark_done(directory: Path, job: Job) -> None:
    record = {"name": job.name, "seed": job.seed, "options": dict(job.options)}
    (directory / _DONE).write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")


def run_jobs(
    jobs: list[Job], *, budget_seconds: float | None = None, workers: int | None = None
) -> RunStatus:
    """Render every job whose cache directory lacks a ``done`` marker.

    Jobs render in parallel through ``oracle.run_many`` with one thread per job. They are
    dispatched in batches of ``workers`` (default ``os.cpu_count()``). The budget is checked
    before each batch, so no job starts once ``budget_seconds`` has elapsed. A batch already
    running finishes. Identical jobs render once. ``done`` is written only after a successful
    render.
    """
    start = time.monotonic()
    width = workers if workers is not None else (os.cpu_count() or 1)
    if width < 1:
        raise ValueError("workers must be >= 1")
    keys = [job_key(job) for job in jobs]
    todo: dict[str, Job] = {}
    for key, job in zip(keys, jobs, strict=True):
        if not _is_done(_job_dir(key)):
            todo.setdefault(key, job)
    pending = list(todo.items())
    for first in range(0, len(pending), width):
        if budget_seconds is not None and time.monotonic() - start >= budget_seconds:
            break
        batch = pending[first : first + width]
        run_many(
            [
                (_job_dir(key), {**dict(job.options), "seed": job.seed, "threads": 1})
                for key, job in batch
            ],
            workers=width,
        )
        for key, job in batch:
            _mark_done(_job_dir(key), job)
    completed = sum(_is_done(_job_dir(key)) for key in keys)
    return RunStatus(
        completed=completed,
        remaining=len(jobs) - completed,
        elapsed=time.monotonic() - start,
    )


def load(job: Job) -> OracleRender:
    """The cached render of ``job``. Raises FileNotFoundError until ``run_jobs`` has rendered it."""
    directory = _job_dir(job_key(job))
    if not _is_done(directory):
        raise FileNotFoundError(f"job {job.name!r} (seed {job.seed}) is not rendered yet")
    return read_oracle(directory)


def ensemble(name: str, pairs: int, base_seed: int = 0, **options: Any) -> list[Job]:
    """``2 * pairs`` jobs named ``name`` with seeds ``base_seed … base_seed + 2 * pairs - 1``.

    Consecutive seeds form the pairs that ``measure_ensemble`` compares.
    """
    if pairs < 1:
        raise ValueError("pairs must be >= 1")
    return [Job.make(name, base_seed + i, **options) for i in range(2 * pairs)]


def measure_ensemble(
    jobs: list[Job], ref8: np.ndarray, object_id: np.ndarray | None = None
) -> list[dict[str, float]]:
    """``metrics.measure`` for each consecutive pair of jobs, in order.

    ``ref8`` is the reference display image. ``object_id`` is the SPEC §9 id map shared by the
    pairs. When it is None, the first job's ``object_id`` is used. All jobs must be rendered.
    """
    if not jobs or len(jobs) % 2 != 0:
        raise ValueError("jobs must form pairs: a non-zero, even number of jobs")
    if object_id is None:
        object_id = load(jobs[0]).object_id
    results: list[dict[str, float]] = []
    for first, second in zip(jobs[0::2], jobs[1::2], strict=True):
        a = load(first)
        b = load(second)
        if a.passes != b.passes:
            raise ValueError(f"pair {first.name!r}: passes differ ({a.passes} vs {b.passes})")
        results.append(metrics.measure(a.sum, b.sum, a.passes, ref8, object_id))
    return results


def _load_jobs(path: Path) -> list[Job]:
    spec = importlib.util.spec_from_file_location("painterly_experiment_jobs", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"{path}: not a Python source file")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    jobs = getattr(module, "JOBS", None)
    if not isinstance(jobs, list) or not all(isinstance(job, Job) for job in jobs):
        raise SystemExit(f"{path}: JOBS must be a list of Job")
    return jobs


def main(argv: list[str] | None = None) -> int:
    """CLI: ``run <jobs.py> [--budget SECONDS] [--workers N]``. Returns the exit status."""
    parser = argparse.ArgumentParser(prog="python -m painterly_analysis.experiment")
    commands = parser.add_subparsers(dest="command", required=True)
    run_parser = commands.add_parser("run", help="render the jobs of a jobs file, resumably")
    run_parser.add_argument("jobs_file", type=Path, help="Python file defining JOBS: list[Job]")
    run_parser.add_argument(
        "--budget",
        type=float,
        default=DEFAULT_BUDGET_SECONDS,
        help="seconds after which no new job starts (default: %(default)s)",
    )
    run_parser.add_argument(
        "--workers", type=int, default=None, help="parallel jobs (default: CPU count)"
    )
    args = parser.parse_args(argv)
    status = run_jobs(_load_jobs(args.jobs_file), budget_seconds=args.budget, workers=args.workers)
    print(f"completed={status.completed} remaining={status.remaining}")
    return 0 if status.remaining == 0 else EXIT_REMAINING


if __name__ == "__main__":
    # `python -m` runs this file as __main__, whose Job class differs from the one a jobs file
    # imports from painterly_analysis.experiment. Dispatch to the package copy so the type check
    # in _load_jobs holds.
    from painterly_analysis.experiment import main as package_main

    sys.exit(package_main())
