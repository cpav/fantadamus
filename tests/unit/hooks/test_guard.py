"""Task 9.4: the guard blocks pushes, remote creation, deploys and private-configuration writes (R17.5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.hooks import guard
from scripts.hooks.event import HookEvent

HOME = Path("/home/owner")
BEFORE = guard.GuardState(
    go_ahead=False,
    branch="feat/x",
    home=HOME,
    cwd=Path("/repo"),
    private_paths=(HOME / ".config/fantadamus",),
)
AFTER = guard.GuardState(
    go_ahead=True, branch="feat/x", home=HOME, cwd=Path("/repo"), private_paths=(HOME / ".config/fantadamus",)
)
ON_MAIN = guard.GuardState(
    go_ahead=True, branch="main", home=HOME, cwd=Path("/repo"), private_paths=(HOME / ".config/fantadamus",)
)


def _bash(command: str) -> HookEvent:
    return HookEvent(hook_event_name="PreToolUse", tool_name="Bash", tool_input={"command": command})


@pytest.mark.parametrize(
    "command",
    [
        "git push",
        "git push -u origin feat/ef-9-agent-hooks",
        "git -C /repo push origin feat/x",
        "cd /repo && git status && git push",
        "FOO=1 command git push origin feat/x",
        "bash -lc 'git push origin feat/x'",
        "echo $(git push origin feat/x)",
        "echo `git push origin feat/x`",
        "git status\ngit push origin feat/x",
        "git remote add origin git@github.com:owner/fantadamus.git",
        "gh repo create fantadamus --public",
    ],
)
def test_pre_go_ahead_blocks_any_push(command: str) -> None:
    result = guard.handle(_bash(command), BEFORE)
    assert result.code == 2
    assert "Blocked by the project guard" in result.stderr
    assert "owner" in result.stderr


@pytest.mark.parametrize(
    ("command", "blocked"),
    [
        ("git push -u origin feat/x", False),
        ("git push origin feat/x:feat/x", False),
        ("git push --tags origin", False),
        ("git remote add upstream https://example.org/x.git", False),
        ("gh repo create other --private", False),
        ("git push --force origin feat/x", True),
        ("git push --force-with-lease origin feat/x", True),
        ("git push -uf origin feat/x", True),
        ("git push origin +feat/x", True),
        ("git push origin main", True),
        ("git push origin HEAD:main", True),
        ("git push origin feat/x:refs/heads/main", True),
        ("git push --all origin", True),
        ("git push --mirror origin", True),
        ("git push --delete origin main", True),
    ],
)
def test_after_go_ahead_blocks_only_force_and_main(command: str, blocked: bool) -> None:
    assert (guard.check_command(command, AFTER) is not None) == blocked, command


def test_pushing_the_current_branch_from_main_is_blocked() -> None:
    assert guard.check_command("git push", ON_MAIN) is not None
    assert guard.check_command("git push -u origin HEAD", ON_MAIN) is not None
    assert guard.check_command("git push", AFTER) is None


@pytest.mark.parametrize(
    "command",
    [
        "terraform apply",
        "terraform -chdir=infra/stack apply -auto-approve",
        "terraform destroy",
        "make deploy",
        "make -C /repo bootstrap",
        "make check && make deploy",
        "uv run make deploy",
    ],
)
def test_deploys_are_always_blocked(command: str) -> None:
    for state in (BEFORE, AFTER):
        assert guard.check_command(command, state) is not None, command


@pytest.mark.parametrize(
    "command",
    [
        "echo x > ~/.config/fantadamus/private.toml",
        "cat >> $HOME/.config/fantadamus/private.toml <<'EOF'\n[creators]\nEOF",
        "cp /tmp/x.toml ${HOME}/.config/fantadamus/private.toml",
        "rm -f /home/owner/.config/fantadamus/private.toml",
        "sed -i '' 's/a/b/' ~/.config/fantadamus/private.toml",
        "tee /home/owner/.config/fantadamus/new.toml",
        "cd /home/owner/.config && touch fantadamus/private.toml",
    ],
)
def test_private_configuration_writes_are_blocked(command: str) -> None:
    assert guard.check_command(command, AFTER) is not None, command


@pytest.mark.parametrize(
    "command",
    [
        "git status --short",
        "cat ~/.config/fantadamus/private.toml",
        "ls ~/.config/fantadamus",
        'git commit -m "docs: say when to git push origin main"',
        "grep -rn 'make deploy' Makefile",
        'echo "terraform apply"',
        "python3 - <<'PY'\nprint('git push origin main')\nPY\necho done",
        "cat > notes.txt <<EOF\ngit push --force\nmake deploy\nEOF",
        "make check",
        "terraform -chdir=infra/stack plan",
        "uv run pytest -q tests/unit/hooks",
        "git log --oneline -3 # git push later",
        "",
    ],
)
def test_harmless_commands_pass(command: str) -> None:
    for state in (BEFORE, AFTER):
        assert guard.check_command(command, state) is None, command


def test_unterminated_quote_still_finds_the_push() -> None:
    assert guard.check_command("echo 'unterminated && git push", BEFORE) is not None


def test_heredoc_marker_without_an_end_is_not_a_hiding_place() -> None:
    assert guard.check_command('echo "x <<EOF"\ngit push origin feat/x', BEFORE) is not None


def test_file_tools_guard_the_private_configuration() -> None:
    write = HookEvent(
        hook_event_name="PreToolUse",
        tool_name="Write",
        tool_input={"file_path": "/home/owner/.config/fantadamus/private.toml", "content": "x"},
    )
    edit = HookEvent(
        hook_event_name="PreToolUse", tool_name="Edit", tool_input={"file_path": "/repo/README.md"}
    )
    assert guard.handle(write, AFTER).code == 2
    assert "private configuration" in guard.handle(write, AFTER).stderr
    assert guard.handle(edit, BEFORE).code == 0
    other = HookEvent(hook_event_name="PreToolUse", tool_name="Read", tool_input={"file_path": "/x"})
    assert guard.handle(other, BEFORE).code == 0
