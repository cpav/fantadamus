"""Task 6.5: the pre-push hook rejects outgoing commits with a secret or a FantaCreator identity (R9.6)."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.checks import pre_push

from tests.conftest import Git

FAKE_KEY = "".join(["AKIA", "QYLP", "MN7R", "B3XK", "Z2WD"])
IDENTITY = "Creatore Fittizio"
ZEROS = "0" * 40


def _commit(git: Git, repo: Path, name: str, text: str) -> str:
    (repo / name).write_text(text, encoding="utf-8")
    git("add", name)
    git("commit", "-q", "-m", f"chore: add {name}")
    return git("rev-parse", "HEAD").strip()


def _env(from_ref: str, to_ref: str) -> dict[str, str]:
    return {
        "PRE_COMMIT_FROM_REF": from_ref,
        "PRE_COMMIT_TO_REF": to_ref,
        "FANTADAMUS_CREATOR_IDENTITIES": IDENTITY,
    }


def test_outgoing_secret_rejected(git_repo: tuple[Path, Git], capsys: pytest.CaptureFixture[str]) -> None:
    repo, git = git_repo
    base = _commit(git, repo, "a.md", "clean\n")
    head = _commit(git, repo, "settings.py", f'KEY = "{FAKE_KEY}"\n')
    assert pre_push.main(env=_env(base, head), repo=repo) == 1
    output = capsys.readouterr()
    assert "FAIL secrets" in output.err
    assert FAKE_KEY not in output.out + output.err


def test_outgoing_identity_rejected(git_repo: tuple[Path, Git], capsys: pytest.CaptureFixture[str]) -> None:
    repo, git = git_repo
    base = _commit(git, repo, "a.md", "clean\n")
    head = _commit(git, repo, "notes.md", f"video by {IDENTITY}\n")
    assert pre_push.main(env=_env(base, head), repo=repo) == 1
    output = capsys.readouterr()
    assert f"FAIL identities: FantaCreator identity found at {head[:12]} notes.md:1" in output.err
    assert IDENTITY.casefold() not in (output.out + output.err).casefold()


def test_clean_new_branch_passes(git_repo: tuple[Path, Git]) -> None:
    repo, git = git_repo
    head = _commit(git, repo, "a.md", "clean\n")
    assert pre_push.log_opts(ZEROS, head) == f"{head} --not --remotes"
    assert pre_push.main(env=_env(ZEROS, head), repo=repo) == 0


def test_without_refs_there_is_nothing_to_check() -> None:
    assert pre_push.main(env={}, repo=Path("/absent")) == 0
