"""PreToolUse on Bash and the file tools: block what only the owner may do (R17.5).

- **Before the remote go-ahead** (no `origin` remote): every `git push`, `git remote add` and
  `gh repo create`.
- **After it:** force-pushes, and pushes to `main` (by refspec, `--all`, `--mirror`, or from `main` itself).
- **Always:** deploys (`terraform apply` or `destroy`, `make deploy`, `make bootstrap`) and writes to the
  private configuration.

Shell commands are split into simple commands on `;`, `&&`, `||`, `|`, `&`, newlines, subshells and
backticks, with quoting respected and heredoc bodies skipped. `bash -c` and `eval` are read recursively.
When a command can't be parsed, the guard falls back to a cruder split, so doubt blocks rather than allows.
A blocked call exits 2 and its reason goes back to the agent, which then asks the owner.
"""

from __future__ import annotations

import os
import re
import shlex
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from scripts.checks import identities
from scripts.checks._common import run_command
from scripts.hooks.event import HookEvent, HookResult, project_root, run_hook

FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
WRAPPERS = {"env", "command", "exec", "nohup", "time", "sudo", "nice", "xargs", "uv", "run"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
WRITERS = {
    "cp",
    "mv",
    "rm",
    "tee",
    "touch",
    "mkdir",
    "rmdir",
    "chmod",
    "chown",
    "ln",
    "install",
    "rsync",
    "truncate",
    "dd",
    "unlink",
    "shred",
}
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"}
PUSH_VALUE_OPTIONS = {"--repo", "-o", "--push-option", "--receive-pack", "--exec"}
MAKE_VALUE_OPTIONS = {"-C", "-f", "--file", "--directory", "-I", "-o", "-W", "-l"}
MAX_DEPTH = 5

_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
_HEREDOC = re.compile(r"(?<!<)<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
_PUNCTUATION = set(";&|()<>")


@dataclass(frozen=True)
class GuardState:
    """What the rules depend on: the go-ahead, the current branch, and the paths to protect."""

    go_ahead: bool
    branch: str | None
    home: Path
    cwd: Path
    private_paths: tuple[Path, ...]


# --- Splitting a shell script into simple commands -----------------------------------------------------


def _without_heredocs(script: str) -> list[str]:
    """The script's lines with heredoc bodies removed. A marker without a closing line removes nothing."""
    lines = script.split("\n")
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        for match in _HEREDOC.finditer(line):
            strip_tabs, delimiter = match.group(1) == "-", match.group(3)
            for end in range(index, len(lines)):
                candidate = lines[end].lstrip("\t") if strip_tabs else lines[end]
                if candidate.strip() == delimiter:
                    index = end + 1
                    break
    return kept


def _is_redirect(word: str) -> bool:
    return bool(word) and set(word) <= _PUNCTUATION and ("<" in word or ">" in word)


def _is_separator(word: str) -> bool:
    return bool(word) and set(word) <= _PUNCTUATION and not _is_redirect(word)


def split_commands(script: str) -> list[list[str]]:
    """Every simple command in a shell script, as an argument list. Redirections stay in their command."""
    text = "\n".join(_without_heredocs(script)).replace("`", " ; ").replace("\n", " ; ")
    lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        words = list(lexer)
    except ValueError:  # an unterminated quote: fall back to a crude split, so doubt blocks
        words = re.sub(r"([;&|()])", r" \1 ", text.replace("'", " ").replace('"', " ")).split()
    commands: list[list[str]] = []
    current: list[str] = []
    for word in words:
        if _is_separator(word):
            if current:
                commands.append(current)
            current = []
        else:
            current.append(word)
    if current:
        commands.append(current)
    return commands


def _strip_prefix(argv: Sequence[str]) -> list[str]:
    """Drop leading `VAR=value` assignments and wrappers such as `env`, `time`, `xargs` or `uv run`."""
    index = 0
    while index < len(argv):
        word = argv[index]
        if _ASSIGNMENT.fullmatch(word) or os.path.basename(word) in WRAPPERS:
            index += 1
        elif index > 0 and (word.startswith("-") or word.isdigit()):
            index += 1  # a wrapper's own options, such as `env -i` or `nice -n 5`
        else:
            break
    return list(argv[index:])


def _subcommand(args: Sequence[str], value_options: set[str]) -> tuple[str | None, list[str]]:
    """The first argument that isn't an option (skipping options that take a value), and what follows it."""
    index = 0
    while index < len(args):
        word = args[index]
        if word in value_options:
            index += 2
        elif word.startswith("-"):
            index += 1
        else:
            return word, list(args[index + 1 :])
    return None, []


# --- The rules -------------------------------------------------------------------------------------------


def _is_main(ref: str) -> bool:
    return ref.lstrip("+").removeprefix("refs/heads/") == "main"


def _push_problem(args: Sequence[str], state: GuardState) -> str | None:
    if not state.go_ahead:
        return "`git push` is blocked until the owner gives the remote go-ahead (task 15)"
    positionals: list[str] = []
    force = everything = False
    index = 0
    while index < len(args):
        word = args[index]
        if word == "--":
            positionals.extend(args[index + 1 :])
            break
        if word in PUSH_VALUE_OPTIONS:
            index += 2
            continue
        if word.startswith("--"):
            name = word.split("=", 1)[0]
            force = force or name in {"--force", "--force-with-lease", "--force-if-includes"}
            everything = everything or name in {"--all", "--mirror", "--branches"}
        elif word.startswith("-") and len(word) > 1:
            force = force or "f" in word[1:]
        else:
            positionals.append(word)
        index += 1
    refspecs = positionals[1:]
    if force or any(ref.startswith("+") for ref in refspecs):
        return "force-pushes are blocked"
    if everything:
        return "`git push --all` or `--mirror` would push `main`, which only changes through a pull request"
    if any(_is_main(ref.split(":")[-1]) for ref in refspecs):
        return "pushes to `main` are blocked: it only changes through a pull request"
    if state.branch == "main" and (not refspecs or any(ref.split(":")[-1] == "HEAD" for ref in refspecs)):
        return "this push is from `main`, which only changes through a pull request"
    return None


def _git_problem(args: Sequence[str], state: GuardState) -> str | None:
    sub, rest = _subcommand(args, GIT_VALUE_OPTIONS)
    if sub == "push":
        return _push_problem(rest, state)
    if sub == "remote" and rest[:1] == ["add"] and not state.go_ahead:
        return "`git remote add` is blocked until the owner gives the remote go-ahead (task 15)"
    return None


def _gh_problem(args: Sequence[str], state: GuardState) -> str | None:
    sub, rest = _subcommand(args, {"-R", "--repo"})
    if sub == "repo" and rest[:1] == ["create"] and not state.go_ahead:
        return "`gh repo create` is blocked until the owner gives the remote go-ahead (task 15)"
    return None


def _deploy_problem(name: str, args: Sequence[str]) -> str | None:
    if name in {"terraform", "tofu"}:
        sub, _ = _subcommand(args, set())
        if sub in {"apply", "destroy"}:
            return f"`{name} {sub}` is a deploy, which only the owner runs after seeing the plan"
    if name in {"make", "gmake"}:
        targets: list[str] = []
        index = 0
        while index < len(args):
            word = args[index]
            if word in MAKE_VALUE_OPTIONS:
                index += 2
                continue
            if not word.startswith("-") and not _ASSIGNMENT.fullmatch(word):
                targets.append(word)
            index += 1
        for target in ("deploy", "bootstrap"):
            if target in targets:
                return f"`make {target}` is a deploy, which only the owner runs after seeing the plan"
    return None


def _resolve(word: str, state: GuardState) -> Path:
    home = str(state.home)
    expanded = word.replace("${HOME}", home).replace("$HOME", home)
    if expanded == "~" or expanded.startswith("~/"):
        expanded = home + expanded[1:]
    path = Path(expanded)
    return Path(os.path.normpath(path if path.is_absolute() else state.cwd / path))


def is_private(word: str, state: GuardState) -> bool:
    path = _resolve(word, state)
    return any(path == private or private in path.parents for private in state.private_paths)


def _write_problem(argv: Sequence[str], state: GuardState, cwd: Path) -> str | None:
    local = GuardState(state.go_ahead, state.branch, state.home, cwd, state.private_paths)
    for index, word in enumerate(argv[:-1]):
        if _is_redirect(word) and ">" in word and is_private(argv[index + 1], local):
            return "writes to the private configuration are the owner's to make"
    name, args = os.path.basename(argv[0]), argv[1:]
    in_place = name == "sed" and any(arg.startswith("-i") or arg == "--in-place" for arg in args)
    if name in WRITERS or in_place:
        paths = [arg.removeprefix("of=") for arg in args if not arg.startswith("-") or arg.startswith("of=")]
        if any(is_private(path, local) for path in paths):
            return "writes to the private configuration are the owner's to make"
    return None


def _command_problems(script: str, state: GuardState, depth: int) -> Iterator[str]:
    cwd = state.cwd
    for raw in split_commands(script):
        if raw[:1] == ["cd"] and len(raw) > 1:
            cwd = _resolve(
                raw[1], GuardState(state.go_ahead, state.branch, state.home, cwd, state.private_paths)
            )
        argv = _strip_prefix(raw)
        if not argv:
            continue
        name, args = os.path.basename(argv[0]), argv[1:]
        if depth < MAX_DEPTH and name in SHELLS:
            options = [arg for arg in args if arg.startswith("-")]
            scripts = [arg for arg in args if not arg.startswith("-")]
            if any("c" in option.lstrip("-") for option in options) and scripts:
                yield from _command_problems(scripts[0], state, depth + 1)
        if depth < MAX_DEPTH and name == "eval":
            yield from _command_problems(" ".join(args), state, depth + 1)
        problem = (
            (_git_problem(args, state) if name == "git" else None)
            or (_gh_problem(args, state) if name == "gh" else None)
            or _deploy_problem(name, args)
            or _write_problem(raw, state, cwd)
        )
        if problem:
            yield problem


def check_command(script: str, state: GuardState) -> str | None:
    """The first reason to block a shell command, or None if it may run."""
    return next(_command_problems(script, state, 0), None)


def check_event(event: HookEvent, state: GuardState) -> str | None:
    if event.tool_name == "Bash" and event.command is not None:
        return check_command(event.command, state)
    if event.tool_name in FILE_TOOLS and event.file_path is not None and is_private(event.file_path, state):
        return "writes to the private configuration are the owner's to make"
    return None


def handle(event: HookEvent, state: GuardState) -> HookResult:
    reason = check_event(event, state)
    if reason is None:
        return HookResult(0)
    return HookResult(
        2,
        stderr=f"Blocked by the project guard (R17.5): {reason}. Ask the owner, who can run it.\n",
    )


def current_state(root: Path, env: Mapping[str, str], cwd: str) -> GuardState:
    remotes = run_command(["git", "-C", str(root), "remote"]).stdout.split()
    branch = run_command(["git", "-C", str(root), "symbolic-ref", "--short", "-q", "HEAD"]).stdout.strip()
    return GuardState(
        go_ahead="origin" in remotes,
        branch=branch or None,
        home=Path.home(),
        cwd=Path(cwd) if cwd else root,
        private_paths=(identities.config_path(env), identities.DEFAULT_CONFIG.parent),
    )


def main() -> int:
    root = project_root()

    def handler(event: HookEvent) -> HookResult:
        return handle(event, current_state(root, os.environ, event.cwd))

    # An unreadable event blocks: the guard fails closed.
    return run_hook(handler, invalid_code=2)


if __name__ == "__main__":
    raise SystemExit(main())
