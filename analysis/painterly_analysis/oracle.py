"""Runner for the headless smallpaint reference oracle (``smallpaint_oracle``, T1.1).

Each option maps to one CLI flag. ``chain="lane:16"`` becomes ``--chain lane:16``, underscores
become dashes, and a boolean becomes ``yes`` or ``no``: ``continue_after_emitter=False`` becomes
``--continue-after-emitter no``.
"""

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .io import OracleRender, read_oracle

# Repository root. A relative PAINTERLY_BUILD_DIR is resolved against it, as tests/conftest.py does.
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUILD_DIR = "build/dev"


def oracle_binary() -> Path:
    """Path of ``smallpaint_oracle``: ``$PAINTERLY_BUILD_DIR`` (default ``build/dev``) then
    ``/src/app/smallpaint_oracle``.

    A relative build directory is resolved against the repository root.
    """
    build_dir = Path(os.environ.get("PAINTERLY_BUILD_DIR", DEFAULT_BUILD_DIR))
    if not build_dir.is_absolute():
        build_dir = REPO_ROOT / build_dir
    return build_dir / "src" / "app" / "smallpaint_oracle"


def _option_flags(options: dict[str, Any]) -> list[str]:
    args: list[str] = []
    for key, value in options.items():
        text = ("yes" if value else "no") if isinstance(value, bool) else str(value)
        args += [f"--{key.replace('_', '-')}", text]
    return args


def run_oracle(out_dir: str | Path, **options: Any) -> OracleRender:
    """Render with ``smallpaint_oracle --out out_dir`` plus one flag per option, then load it."""
    if "out" in options:
        raise TypeError("pass the output directory as out_dir, not as out=")
    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cmd = [str(oracle_binary()), *_option_flags(options), "--out", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"smallpaint_oracle exited with status {proc.returncode}: {' '.join(cmd)}\n"
            f"{proc.stderr}"
        )
    return read_oracle(out)


def run_many(jobs: list[tuple[Path, dict]], workers: int | None = None) -> list[OracleRender]:
    """Run ``(out_dir, options)`` jobs and return the renders in job order.

    ``workers=None`` uses ``os.cpu_count()``, capped at the number of jobs. Each job is its own
    subprocess, so threads are sufficient. With more than one worker every job gets
    ``--threads 1``, so the workers do not oversubscribe the cores. With one worker the options
    are passed through unchanged.
    """
    if workers is None:
        workers = os.cpu_count() or 1
    workers = max(1, min(workers, len(jobs)))
    if workers == 1:
        return [run_oracle(out_dir, **options) for out_dir, options in jobs]

    def _run(job: tuple[Path, dict]) -> OracleRender:
        out_dir, options = job
        return run_oracle(out_dir, **{**options, "threads": 1})

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_run, jobs))
