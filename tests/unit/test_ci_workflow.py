"""Task 13: the CI workflow, the weekly audit and Dependabot (R1.2, R9.5, R10.2, R11, R12)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _load(path: Path) -> dict[Any, Any]:
    loaded: dict[Any, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


def _triggers(workflow: dict[Any, Any]) -> dict[str, Any]:
    # PyYAML reads the bare key `on` as the boolean True.
    triggers = workflow["on"] if "on" in workflow else workflow[True]
    assert isinstance(triggers, dict)
    return triggers


def _all_workflows() -> dict[str, dict[Any, Any]]:
    return {path.name: _load(path) for path in sorted(WORKFLOWS.glob("*.yml"))}


def _runs(job: dict[str, Any]) -> list[str]:
    return [step["run"] for step in job["steps"] if "run" in step]


def test_check_job_runs_make_check() -> None:
    ci = _load(WORKFLOWS / "ci.yml")
    assert set(_triggers(ci)) == {"pull_request", "push"}
    assert _triggers(ci)["push"] == {"branches": ["main"]}
    job = ci["jobs"]["check"]
    assert job["runs-on"] == "ubuntu-latest"
    runs = _runs(job)
    assert "make setup" in runs
    assert runs[-1] == "make check"  # one job running all of `make check`, so the union holds (R1.2)
    assert job["env"]["FANTADAMUS_CREATOR_IDENTITIES"] == "${{ secrets.FANTADAMUS_CREATOR_IDENTITIES }}"


def test_actions_pinned_to_sha() -> None:
    for name, workflow in _all_workflows().items():
        for job in workflow["jobs"].values():
            for step in job["steps"]:
                if "uses" in step:
                    assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", step["uses"]), (name, step["uses"])


def test_no_pull_request_target() -> None:
    for name, workflow in _all_workflows().items():
        assert not {"pull_request_target", "workflow_run"} & set(_triggers(workflow)), name


def test_read_only_permissions() -> None:
    for name, workflow in _all_workflows().items():
        assert workflow["permissions"] == {"contents": "read"}, name
        for job in workflow["jobs"].values():
            assert "permissions" not in job, name


def test_job_timeouts() -> None:
    for name, workflow in _all_workflows().items():
        for job_name, job in workflow["jobs"].items():
            assert 0 < job["timeout-minutes"] <= 10, (name, job_name)
    ci = _load(WORKFLOWS / "ci.yml")
    assert ci["concurrency"]["cancel-in-progress"] is True


def test_pr_job_checks_title_and_commit_range() -> None:
    job = _load(WORKFLOWS / "ci.yml")["jobs"]["pr"]
    assert job["if"] == "github.event_name == 'pull_request'"
    assert job["env"]["PR_TITLE"] == "${{ github.event.pull_request.title }}"
    runs = "\n".join(_runs(job))
    assert "conventional-pre-commit --strict" in runs
    assert 'scripts.checks.secrets --range "$BASE_SHA..$HEAD_SHA"' in runs
    assert 'scripts.checks.identities --range "$BASE_SHA..$HEAD_SHA"' in runs
    # Untrusted text reaches the shell only through environment variables, never through `${{ }}`.
    for name, workflow in _all_workflows().items():
        for each in workflow["jobs"].values():
            assert all("${{" not in run for run in _runs(each)), name


def test_audit_schedule_weekly() -> None:
    audit = _load(WORKFLOWS / "audit.yml")
    assert _triggers(audit)["schedule"] == [{"cron": "0 6 * * 1"}]
    assert "make check-audit" in _runs(audit["jobs"]["audit"])


def test_dependency_updates_cover_uv_actions_precommit() -> None:
    config = _load(ROOT / ".github" / "dependabot.yml")
    updates = {entry["package-ecosystem"]: entry for entry in config["updates"]}
    assert set(updates) == {"uv", "github-actions", "pre-commit"}
    for entry in updates.values():
        assert entry["schedule"]["interval"] == "weekly"
        # Conventional titles, so the PR title check passes.
        assert entry["commit-message"]["prefix"] == "build"
        # Only releases at least two weeks old (a supply-chain precaution), one pull request per ecosystem.
        assert entry["cooldown"]["default-days"] >= 14
        assert entry["groups"]["all"]["patterns"] == ["*"]
