"""Task 6.3: the identity check scans the tree, the staged files and a commit range (R10.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.checks import identities as ids

from tests.integration.conftest import Git

ENV = {"FANTADAMUS_CREATOR_IDENTITIES": "Creatore Fittizio"}


def test_tree_staged_and_range_modes(git_repo: tuple[Path, Git]) -> None:
    repo, git = git_repo
    (repo / "clean.md").write_text("nothing to see\n", encoding="utf-8")
    git("add", "clean.md")
    git("commit", "-q", "-m", "docs: clean")
    (repo / "notes.md").write_text("line one\nvideo by Creatore  Fittizio\n", encoding="utf-8")

    tree = ids.check_lines(ids.tree_lines(repo), env=ENV, config=Path("/absent"))
    assert tree.message == "FantaCreator identity found at notes.md:2"

    git("add", "notes.md")
    staged = ids.check_lines(ids.staged_lines(repo), env=ENV, config=Path("/absent"))
    assert staged.message == "FantaCreator identity found at notes.md:2"

    git("commit", "-q", "-m", "docs: notes")
    head = git("rev-parse", "HEAD").strip()
    ranged = ids.check_lines(ids.range_lines("HEAD~1..HEAD", repo), env=ENV, config=Path("/absent"))
    assert ranged.message == f"FantaCreator identity found at {head[:12]} notes.md:2"


def test_main_reports_and_exits(git_repo: tuple[Path, Git], monkeypatch: pytest.MonkeyPatch) -> None:
    repo, _ = git_repo
    monkeypatch.setattr(ids, "ROOT", repo)
    (repo / "notes.md").write_text("clean\n", encoding="utf-8")
    assert ids.main(["--tree"], env=ENV) == 0
    (repo / "notes.md").write_text("Creatore Fittizio\n", encoding="utf-8")
    assert ids.main(["--tree"], env=ENV) == 1
    missing = {"FANTADAMUS_PRIVATE_CONFIG": str(repo / "absent.toml")}
    assert ids.main(["--tree"], env=missing) == 1, "no list available must fail closed"


def test_main_staged_and_range(git_repo: tuple[Path, Git], monkeypatch: pytest.MonkeyPatch) -> None:
    repo, git = git_repo
    monkeypatch.setattr(ids, "ROOT", repo)
    (repo / "a.md").write_text("clean\n", encoding="utf-8")
    git("add", "a.md")
    git("commit", "-q", "-m", "docs: a")
    (repo / "b.md").write_text("Creatore Fittizio\n", encoding="utf-8")
    git("add", "b.md")
    assert ids.main(["--staged"], env=ENV) == 1
    git("commit", "-q", "-m", "docs: b")
    assert ids.main(["--range", "HEAD~1..HEAD"], env=ENV) == 1
    assert ids.main(["--range", "HEAD~1 -1"], env=ENV) == 0


def test_binary_and_deleted_files_are_skipped(git_repo: tuple[Path, Git]) -> None:
    repo, git = git_repo
    (repo / "image.bin").write_bytes(b"\xff\xfe\x00binary")
    (repo / "gone.md").write_text("x\n", encoding="utf-8")
    git("add", "gone.md")
    (repo / "gone.md").unlink()
    assert ids.check_lines(ids.tree_lines(repo), env=ENV, config=Path("/absent")).ok


def test_config_without_creators_table_is_missing(tmp_path: Path) -> None:
    config = tmp_path / "private.toml"
    config.write_text("[aws]\nregion = 'eu-north-1'\n", encoding="utf-8")
    assert ids.load_identities({}, config) is None
    assert ids.config_path({"FANTADAMUS_PRIVATE_CONFIG": str(config)}) == config
