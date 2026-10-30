"""`.github/workflows/release.yml` and `wheels.yml`: the release's jobs and triggers (T8.1).

PyYAML (YAML 1.1) loads a workflow's `on:` key as the boolean `True`, so the triggers are read as
`wf[True]`, never `wf["on"]`.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
RELEASE_WORKFLOW = WORKFLOW_DIR / "release.yml"
WHEELS_WORKFLOW = WORKFLOW_DIR / "wheels.yml"
RELEASE_TOOL = REPO_ROOT / "tools" / "release.py"

# The five jobs of the release workflow, in the order they run.
RELEASE_JOBS = ["plan", "wheels", "package", "install", "publish"]


def _load_by_path(name: str, path: Path) -> ModuleType:
    """Import a tool by file path; `tools/` is not a package."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"no module spec for {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


release = _load_by_path("release", RELEASE_TOOL)
release_workflow = yaml.safe_load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
wheels_workflow = yaml.safe_load(WHEELS_WORKFLOW.read_text(encoding="utf-8"))
jobs = release_workflow["jobs"]


def test_release_triggers_on_a_tag_and_on_dispatch() -> None:
    assert release_workflow[True] == {"push": {"tags": ["v*"]}, "workflow_dispatch": None}
    assert release_workflow["permissions"] == {"contents": "read"}


def test_release_has_the_five_jobs() -> None:
    assert list(jobs) == RELEASE_JOBS


def test_wheels_job_calls_the_reusable_workflow() -> None:
    assert jobs["wheels"]["uses"] == "./.github/workflows/wheels.yml"
    assert jobs["wheels"]["needs"] == "plan"


def test_each_job_needs_the_previous_ones() -> None:
    assert jobs["package"]["needs"] == ["plan", "wheels"]
    assert jobs["install"]["needs"] == "package"
    assert jobs["publish"]["needs"] == ["plan", "package", "install"]


def test_only_a_release_tag_publishes() -> None:
    assert jobs["publish"]["if"] == "needs.plan.outputs.mode == 'release'"
    assert jobs["publish"]["permissions"] == {"contents": "write"}
    writers = [
        name
        for name, job in jobs.items()
        if (job.get("permissions") or {}).get("contents") == "write"
    ]
    assert writers == ["publish"]


def test_exactly_one_step_creates_the_release() -> None:
    found = [
        (name, step)
        for name, job in jobs.items()
        # The wheels job is a reusable-workflow call, so it has no steps of its own.
        for step in job.get("steps", [])
        if "gh release" in (step.get("run") or "")
    ]
    assert len(found) == 1
    name, step = found[0]
    assert name == "publish"
    assert "gh release create" in step["run"]
    assert "--verify-tag" in step["run"]
    assert "dist/release/*" in step["run"]


def test_package_builds_the_assets_and_install_renders_through_them() -> None:
    package_runs = [step.get("run") or "" for step in jobs["package"].get("steps", [])]
    assert any("tools/release.py package" in run for run in package_runs)
    install_runs = [step.get("run") or "" for step in jobs["install"].get("steps", [])]
    assert any("tests/blender_it/run_reference.py" in run for run in install_runs)


def test_install_legs_are_the_install_platforms() -> None:
    legs = {entry["platform"] for entry in jobs["install"]["strategy"]["matrix"]["include"]}
    assert legs == set(release.INSTALL_PLATFORMS)
    assert set(release.INSTALL_PLATFORMS) <= set(release.RELEASE_PLATFORMS)


def test_both_workflows_fetch_the_same_blender() -> None:
    assert release_workflow["env"]["BLENDER_VERSION"] == wheels_workflow["env"]["BLENDER_VERSION"]


def test_wheels_is_reusable_and_has_no_tag_trigger() -> None:
    # Comparing the key set also proves that `push` is gone: release.yml calls this workflow on
    # every tag, so a tag builds the wheels once, inside the Release run.
    assert set(wheels_workflow[True]) == {"workflow_call", "workflow_dispatch", "pull_request"}
