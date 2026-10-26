"""The local gates (task 14.1, R20.1): each test hands the real gate a bad input, in a temporary directory or
repository, and asserts that the gate fails. CI runs the same `make check`; the GitHub-side parts are the
manual checklist of task 15.2. The agent hooks (AT-8) and the walking skeleton (AT-7) have their own files.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest
from scripts.checks import (
    audit,
    contracts,
    coverage_gate,
    identities,
    pre_push,
    secrets,
    suppressions,
    thresholds,
)
from scripts.checks._common import run_command
from scripts.checks.run_all import STATIC

from fantadamus.contracts.base import SCHEMA_DIR
from fantadamus.contracts.skeleton.player import SkeletonPlayer
from tests.conftest import Git

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = str(ROOT / "pyproject.toml")
FAKE_KEY = "".join(["AKIA", "QYLP", "MN7R", "B3XK", "Z2WD"])  # built at runtime, so no key sits in this file
IDENTITY = "Creatore Fittizio"  # an invented name; the real list stays in private configuration
ZEROS = "0" * 40


def _module(*args: str) -> subprocess.CompletedProcess[str]:
    return run_command([sys.executable, "-m", *args])


def _static(name: str) -> tuple[str, ...]:
    return next(check.command for check in STATIC if check.name == name)


def _push(git: Git, repo: Path, env: dict[str, str]) -> int:
    """Commit what is staged and run the pre-push hook on it, as for a new branch."""
    git("commit", "-q", "-m", "chore: add a file")
    head = git("rev-parse", "HEAD").strip()
    return pre_push.main(env={**env, "PRE_COMMIT_FROM_REF": ZEROS, "PRE_COMMIT_TO_REF": head}, repo=repo)


def test_at1_format_lint_gate(tmp_path: Path) -> None:
    messy = tmp_path / "messy.py"
    messy.write_text("x=[1,2 ,3]\n", encoding="utf-8")
    unused = tmp_path / "unused.py"
    unused.write_text("import os\n", encoding="utf-8")
    clean = tmp_path / "clean.py"
    clean.write_text("x = [1, 2, 3]\n", encoding="utf-8")
    assert _module("ruff", "format", "--check", "--config", PYPROJECT, str(messy)).returncode == 1
    assert _module("ruff", "check", "--config", PYPROJECT, str(unused)).returncode == 1
    assert _module("ruff", "format", "--check", "--config", PYPROJECT, str(clean)).returncode == 0
    assert _module("ruff", "check", "--config", PYPROJECT, str(clean)).returncode == 0
    assert _static("format")[-3:] == (
        "format",
        "--check",
        ".",
    )  # make check runs them on the whole repository
    assert _static("lint")[-2:] == ("check", ".")


def test_at2_type_gate(tmp_path: Path) -> None:
    wrong = tmp_path / "wrong.py"
    wrong.write_text('def answer() -> int:\n    return "forty-two"\n', encoding="utf-8")
    result = _module(
        "mypy", "--config-file", PYPROJECT, str(wrong)
    )  # the project's warm cache keeps this quick
    assert result.returncode == 1
    assert "Incompatible return value type" in result.stdout
    assert _static("types")[-1] == "mypy"


def test_at4_fake_aws_key_rejected(git_repo: tuple[Path, Git]) -> None:
    repo, git = git_repo
    (repo / "settings.py").write_text(f'AWS_ACCESS_KEY_ID = "{FAKE_KEY}"\n', encoding="utf-8")
    git("add", "settings.py")
    staged = secrets.check(secrets.Mode.STAGED, repo=repo)  # what the pre-commit hook runs
    assert not staged.ok
    assert "secrets found" in staged.message
    assert FAKE_KEY not in staged.message
    assert _push(git, repo, {"FANTADAMUS_CREATOR_IDENTITIES": IDENTITY}) == 1


def test_at5_coverage_gate(tmp_path: Path) -> None:
    report = tmp_path / "coverage.json"

    def measured(lines: int, branches: int) -> bool:
        totals = {
            "covered_lines": lines,
            "num_statements": 100,
            "covered_branches": branches,
            "num_branches": 100,
        }
        report.write_text(json.dumps({"totals": totals}), encoding="utf-8")
        return coverage_gate.check(report).ok

    assert not measured(lines=85, branches=95)
    assert not measured(lines=95, branches=85)
    assert measured(lines=95, branches=95)


def test_at12_identity_rejected(git_repo: tuple[Path, Git], capsys: pytest.CaptureFixture[str]) -> None:
    repo, git = git_repo
    env = {"FANTADAMUS_CREATOR_IDENTITIES": IDENTITY}
    (repo / "notes.md").write_text(f"# Notes\n\nA pick from {IDENTITY.upper()}.\n", encoding="utf-8")
    git("add", "notes.md")
    staged = identities.check_lines(identities.staged_lines(repo), env=env, config=repo / "absent.toml")
    assert not staged.ok
    assert staged.message == "FantaCreator identity found at notes.md:3"  # where, never what
    assert _push(git, repo, env) == 1
    output = capsys.readouterr()
    assert IDENTITY.casefold() not in (output.out + output.err).casefold()


@pytest.mark.parametrize(
    ("message", "accepted"),
    [("fixed the thing", False), ("feat:missing space", False), ("feat(ef): add the gate proofs", True)],
)
def test_at13_conventional_commits(tmp_path: Path, message: str, accepted: bool) -> None:
    # The same command checks commit messages (the commit-msg hook) and pull-request titles (CI).
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text(message + "\n", encoding="utf-8")
    tool = Path(sys.executable).parent / "conventional-pre-commit"
    assert (run_command([str(tool), "--strict", str(path)]).returncode == 0) == accepted


def test_at14_contract_versioning(tmp_path: Path) -> None:
    schemas = tmp_path / "schemas"
    shutil.copytree(SCHEMA_DIR, schemas)
    player = "skeleton.player.SkeletonPlayer.json"

    def main_had_a_shirt_field(filename: str) -> str:
        doc = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        if filename == player:
            doc["schema"]["properties"]["shirt"] = {"type": "integer"}
        return json.dumps(doc)

    result = contracts.check(schema_dir=schemas, load_base=main_had_a_shirt_field)
    assert not result.ok
    assert "schema changed without a version bump" in result.message
    base = json.loads(main_had_a_shirt_field(player))
    minor = SkeletonPlayer.schema_document() | {"version": "1.1.0"}
    issues = contracts.version_rules(base, minor, "## SkeletonPlayer 1.1.0\n")
    assert issues == [
        "skeleton.player.SkeletonPlayer: breaking change needs a major bump (1.0.0 → 1.1.0): $.shirt: removed"
    ]


def test_at15_suppressions(git_repo: tuple[Path, Git]) -> None:
    repo, _ = git_repo
    (repo / "bad.py").write_text(
        "import os  # noqa\nx: int = 'a'  # type: ignore\nimport sys  # noqa: F401  # reason: a demo\n",
        encoding="utf-8",
    )
    (repo / "test_later.py").write_text(
        "import pytest\n\n\n@pytest.mark.skip\ndef test_later() -> None:\n    pass\n", encoding="utf-8"
    )
    register = repo / "register.md"
    register.write_text("| S-001 | `bad.py` | ruff `F401` | a demo |  |\n", encoding="utf-8")
    message = suppressions.check(root=repo, register=register).message
    assert "bad.py:1: suppression names no rule" in message  # the blanket lint suppression
    assert "bad.py:2: suppression names no rule" in message  # the type-checker one without an error code
    assert "S-001 (F401 in bad.py) has no approval date from the owner" in message
    assert "test_later.py:4: suppression of skip gives no reason" in message


def test_at16_threshold_ratchet() -> None:
    current = thresholds.load_current()
    weaker = {name: dict(entry) for name, entry in current.items()}
    weaker["coverage_line"]["value"] = 80
    weaker["hypothesis_ci_examples"]["value"] = 100
    weaker["ci_time_budget_minutes"]["value"] = 9
    assert len(thresholds.compare(current, weaker)) == 3


def test_at17_dependency_audit() -> None:
    """The real pip-audit, on a lockfile export replaced by one old, vulnerable pin. Needs the network."""
    audited: list[subprocess.CompletedProcess[str]] = []

    def run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        if tuple(args) == audit.EXPORT:
            return subprocess.CompletedProcess(list(args), 0, stdout="jinja2==2.10\n", stderr="")
        if not audited:
            audited.append(run_command(args))
        return audited[0]

    today = dt.date(2026, 10, 26)
    failing = audit.check([], run=run, today=today)
    assert not failing.ok
    found = sorted(set(re.findall(r"jinja2 2\.10: (\S+)", failing.message)))
    assert found
    later, earlier = today + dt.timedelta(days=30), today - dt.timedelta(days=1)
    assert audit.check([audit.AllowEntry(vuln, "a test", later) for vuln in found], run=run, today=today).ok
    expired = audit.check([audit.AllowEntry(vuln, "a test", earlier) for vuln in found], run=run, today=today)
    assert not expired.ok
    assert "expired" in expired.message
