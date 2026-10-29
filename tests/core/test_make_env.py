"""`make env` keeps the packages it does not manage, so it never removes the blender group.

M4-FIX-ENV: `make -n` prints a target's recipe without running it, so these tests install
nothing, fetch nothing and use no network: they read the two `uv sync` lines that the `env` and
`env-blender` targets would run.
"""

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# The `uv sync` commands the two targets must run, as the Makefile spells them.
# - `env` installs the dev and analysis groups and passes `--inexact`, which uv documents as "Do
#   not remove extraneous packages present in the environment": without it uv's default exact
#   sync removes the blender group's bpy that `make env-blender` installed.
# - `env-blender` installs the blender group too, and stays exactly as it is.
ENV_SYNC = "uv sync --locked --group dev --group analysis"
ENV_BLENDER_SYNC = "uv sync --locked --group dev --group analysis --group blender"


def _dry_run(target: str) -> list[str]:
    """The non-empty recipe lines `make -n <target>` prints, run in the repository root."""
    result = subprocess.run(
        ["make", "-n", target],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _uv_sync_lines(target: str) -> list[str]:
    """The lines of the target's dry-run recipe that run `uv sync`."""
    return [line for line in _dry_run(target) if line.startswith("uv sync")]


def test_env_syncs_inexactly_so_bpy_survives() -> None:
    """`make -n env` runs uv sync with --inexact, so the blender group's packages stay installed."""
    lines = _uv_sync_lines("env")
    assert len(lines) == 1, f"env must have exactly one uv sync line, got {lines}"
    assert lines[0] == f"{ENV_SYNC} --inexact"


def test_env_blender_syncs_the_blender_group() -> None:
    """`make -n env-blender` runs exactly the uv sync line that adds the blender group."""
    lines = _uv_sync_lines("env-blender")
    assert len(lines) == 1, f"env-blender must have exactly one uv sync line, got {lines}"
    assert lines[0] == ENV_BLENDER_SYNC
