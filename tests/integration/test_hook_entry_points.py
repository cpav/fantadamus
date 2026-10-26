"""Tasks 9.1 to 9.4: each hook's entry point, run on a real (throwaway) git repository."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from scripts.hooks import event, guard, post_edit, stop_check

from tests.conftest import Git

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "hooks"


def _stdin(monkeypatch: pytest.MonkeyPatch, payload: dict[str, object] | str) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


def _fixture(name: str, **changes: object) -> dict[str, object]:
    payload: dict[str, object] = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    payload.update(changes)
    return payload


@pytest.fixture
def project(git_repo: tuple[Path, Git], monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Git]:
    repo, git = git_repo
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    monkeypatch.delenv("FANTADAMUS_HOOK_SHAPES", raising=False)
    return repo, git


def test_guard_main_blocks_and_records_the_shape(
    project: tuple[Path, Git], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, _ = project
    _stdin(monkeypatch, _fixture("pre_tool_use_bash_git_push", cwd=str(repo)))
    assert guard.main() == 2
    assert "Blocked by the project guard" in capsys.readouterr().err
    shapes = (repo / ".git" / event.SHAPES_FILE).read_text(encoding="utf-8")
    assert '"event": "PreToolUse"' in shapes


def test_guard_main_fails_closed_on_garbage(
    project: tuple[Path, Git], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stdin(monkeypatch, "{not json")
    assert guard.main() == 2
    assert "not a Claude Code hook event" in capsys.readouterr().err


def test_guard_state_follows_the_remote_and_branch(project: tuple[Path, Git]) -> None:
    repo, git = project
    before = guard.current_state(repo, {}, "")
    assert (before.go_ahead, before.branch, before.cwd) == (False, "main", repo)
    git("remote", "add", "origin", "https://example.org/repo.git")
    git("checkout", "-q", "-b", "feat/x")
    after = guard.current_state(repo, {"FANTADAMUS_PRIVATE_CONFIG": "/srv/private.toml"}, "/work")
    assert (after.go_ahead, after.branch, after.cwd) == (True, "feat/x", Path("/work"))
    assert Path("/srv/private.toml") in after.private_paths


def test_post_edit_main_ignores_other_files(
    project: tuple[Path, Git], monkeypatch: pytest.MonkeyPatch
) -> None:
    _stdin(monkeypatch, _fixture("post_tool_use_edit_python"))
    assert post_edit.main() == 0


def test_post_edit_formats_a_real_file(project: tuple[Path, Git]) -> None:
    repo, _ = project
    source = repo / "module.py"
    source.write_text("x=1\nprint(undefined_name)\n", encoding="utf-8")
    edited = event.HookEvent(
        hook_event_name="PostToolUse", tool_name="Edit", tool_input={"file_path": str(source)}
    )
    result = post_edit.handle(edited, root=repo)
    assert source.read_text(encoding="utf-8").startswith("x = 1\n")
    assert result.code == 2
    assert "F821" in result.stderr


def test_stop_check_main_runs_make_and_reports_red(
    project: tuple[Path, Git], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo, _ = project
    (repo / "Makefile").write_text("test-fast:\n\t@echo 'FAIL demo: on purpose'; exit 1\n", encoding="utf-8")
    _stdin(monkeypatch, _fixture("stop"))
    assert stop_check.main() == 2
    assert "FAIL demo: on purpose" in capsys.readouterr().err
    (repo / "Makefile").write_text("test-fast:\n\t@echo '1 passed'\n", encoding="utf-8")
    _stdin(monkeypatch, _fixture("stop"))
    assert stop_check.main() == 0
    _stdin(monkeypatch, _fixture("stop"))
    assert stop_check.main() == 0
    assert "no check needed" in capsys.readouterr().out


def test_invalid_event_is_a_visible_error_for_other_hooks(
    project: tuple[Path, Git], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _stdin(monkeypatch, "[]")
    assert post_edit.main() == 1
    assert "not a Claude Code hook event" in capsys.readouterr().err
