"""Task 6.4: the pinned gitleaks finds a fake AWS key committed in a range (R10.1, R10.2)."""

from __future__ import annotations

from pathlib import Path

from scripts.checks import secrets

from tests.conftest import Git

# Assembled at run time so this file never contains a key-shaped string itself.
FAKE_KEY = "".join(["AKIA", "QYLP", "MN7R", "B3XK", "Z2WD"])


def test_fake_aws_key_detected_in_range(git_repo: tuple[Path, Git]) -> None:
    repo, git = git_repo
    (repo / "README.md").write_text("start\n", encoding="utf-8")
    git("add", "README.md")
    git("commit", "-q", "-m", "docs: start")
    (repo / "settings.py").write_text(f'AWS_ACCESS_KEY_ID = "{FAKE_KEY}"\n', encoding="utf-8")
    git("add", "settings.py")
    git("commit", "-q", "-m", "feat: settings")
    result = secrets.check(secrets.Mode.RANGE, log_opts="HEAD~1..HEAD", repo=repo)
    assert not result.ok
    assert "settings.py:1" in result.message
    assert FAKE_KEY not in result.message
    assert secrets.check(secrets.Mode.RANGE, log_opts="HEAD~2..HEAD~1", repo=repo).ok
