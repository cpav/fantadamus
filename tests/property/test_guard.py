"""Property P11: generated pushes, remote creations and deploys are blocked as R17.5 says; harmless commands
pass."""

from __future__ import annotations

from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st
from scripts.hooks import guard

HOME = Path("/home/owner")


def _state(go_ahead: bool) -> guard.GuardState:
    return guard.GuardState(
        go_ahead=go_ahead,
        branch="feat/x",
        home=HOME,
        cwd=Path("/repo"),
        private_paths=(HOME / ".config/fantadamus",),
    )


SAFE = st.sampled_from(
    [
        "git status --short",
        "ls -la",
        "echo done",
        "uv run pytest -q",
        "git log --oneline -3",
        "grep -rn push scripts",
        'echo "git push origin main"',
        "git commit -m 'make deploy later'",
        "git diff HEAD",
        "make check",
        "terraform -chdir=infra/stack validate",
        "cat ~/.config/fantadamus/private.toml",
    ]
)
PREFIX = st.lists(st.sampled_from(["FOO=1", "GIT_TRACE=0", "env", "command", "nohup", "time"]), max_size=2)
GIT_GLOBALS = st.lists(
    st.sampled_from(["-C /repo", "-c core.pager=cat", "--no-pager", "--git-dir=/repo/.git"]), max_size=2
)
SEPARATOR = st.sampled_from([" && ", "; ", " || ", " | ", "\n", " & "])

# kind → (blocked before the go-ahead, blocked after it)
KINDS = {
    "push_feature": (True, False),
    "push_force": (True, True),
    "push_main": (True, True),
    "remote_add": (True, False),
    "repo_create": (True, False),
    "deploy": (True, True),
}


@st.composite
def risky(draw: st.DrawFn, kind: str) -> str:
    git = " ".join(["git", *draw(GIT_GLOBALS)])
    if kind == "push_feature":
        flags = draw(st.lists(st.sampled_from(["-u", "--set-upstream", "-v", "--tags", "-q"]), max_size=2))
        return " ".join([git, "push", *flags, "origin", "feat/x"])
    if kind == "push_force":
        force = draw(
            st.sampled_from(["-f", "--force", "--force-with-lease", "-uf", "--force-with-lease=feat/x"])
        )
        return draw(st.sampled_from([f"{git} push {force} origin feat/x", f"{git} push origin +feat/x"]))
    if kind == "push_main":
        target = draw(st.sampled_from(["main", "HEAD:main", "refs/heads/main", "feat/x:main", "+main"]))
        return f"{git} push origin {target}"
    if kind == "remote_add":
        return f"{git} remote add origin git@github.com:owner/fantadamus.git"
    if kind == "repo_create":
        return "gh repo create fantadamus --public --source=."
    return draw(
        st.sampled_from(
            [
                "terraform apply",
                "terraform -chdir=infra/stack apply -auto-approve",
                "make deploy",
                "make bootstrap",
                "make -C . deploy",
                "terraform destroy",
            ]
        )
    )


@st.composite
def scripts_with(draw: st.DrawFn) -> tuple[str, str]:
    kind = draw(st.sampled_from(sorted(KINDS)))
    command = " ".join([*draw(PREFIX), draw(risky(kind))])
    wrapping = draw(st.sampled_from(["plain", "bash", "subshell", "backticks"]))
    if wrapping == "bash":
        command = f"bash -c '{command}'" if "'" not in command else command
    elif wrapping == "subshell":
        command = f"echo $({command})"
    elif wrapping == "backticks":
        command = f"echo `{command}`"
    before = draw(st.lists(SAFE, max_size=2))
    after = draw(st.lists(SAFE, max_size=2))
    parts = [*before, command, *after]
    script = parts[0]
    for part in parts[1:]:
        script += draw(SEPARATOR) + part
    return kind, script


@given(case=scripts_with(), go_ahead=st.booleans())
def test_guard_commands(case: tuple[str, str], go_ahead: bool) -> None:
    kind, script = case
    expected = KINDS[kind][1 if go_ahead else 0]
    assert (guard.check_command(script, _state(go_ahead)) is not None) == expected, script


@given(
    parts=st.lists(SAFE, min_size=1, max_size=4),
    separators=st.lists(SEPARATOR, min_size=3, max_size=3),
    go_ahead=st.booleans(),
)
def test_harmless_scripts_pass(parts: list[str], separators: list[str], go_ahead: bool) -> None:
    script = parts[0]
    for separator, part in zip(separators, parts[1:], strict=False):
        script += separator + part
    assert guard.check_command(script, _state(go_ahead)) is None, script
