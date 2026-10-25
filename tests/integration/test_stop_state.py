"""Task 9.3: the stop hook's notion of "changed since the last green check" (R17.3)."""

from __future__ import annotations

from pathlib import Path

from scripts.hooks.stop_check import tree_state

from tests.integration.conftest import Git


def test_state_tracks_edits_new_files_and_commits(git_repo: tuple[Path, Git]) -> None:
    repo, git = git_repo
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    (repo / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    git("add", "a.txt", ".gitignore")
    git("commit", "-q", "-m", "chore: start")
    clean = tree_state(repo)
    assert tree_state(repo) == clean

    (repo / "ignored").mkdir()
    (repo / "ignored" / "cache.bin").write_text("noise\n", encoding="utf-8")
    assert tree_state(repo) == clean

    (repo / "a.txt").write_text("two\n", encoding="utf-8")
    edited = tree_state(repo)
    assert edited != clean

    (repo / "b.txt").write_text("new\n", encoding="utf-8")
    added = tree_state(repo)
    assert added not in (clean, edited)
    (repo / "b.txt").write_text("changed\n", encoding="utf-8")
    assert tree_state(repo) != added

    git("add", "a.txt", "b.txt")
    git("commit", "-q", "-m", "chore: more")
    assert tree_state(repo) not in (clean, edited, added)


def test_state_of_a_repository_without_commits(git_repo: tuple[Path, Git]) -> None:
    repo, _ = git_repo
    empty = tree_state(repo)
    (repo / "first.txt").write_text("x\n", encoding="utf-8")
    assert tree_state(repo) != empty
