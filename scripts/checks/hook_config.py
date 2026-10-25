"""`.claude/settings.json` follows Claude Code's documented hooks format and wires the project's hooks
(R17.1, R17.7).

The format is the one recorded in ADR-0001: event → matcher groups → command handlers. Beyond the format,
the check requires the three project hooks: the guard on every tool that can push, deploy or write (and
failing closed), `post_edit` on the file-editing tools, and `stop_check` with a timeout longer than its own
10-minute limit, so an overrun is reported by the hook rather than cut off.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.checks._common import CheckResult, report
from scripts.hooks.stop_check import TIMEOUT_SECONDS

ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / ".claude" / "settings.json"
HOOKS_DIR = ROOT / "scripts" / "hooks"
NAME = "hook-config"

EVENTS = {
    "PreToolUse", "PermissionRequest", "PostToolUse", "PostToolUseFailure", "Notification",
    "UserPromptSubmit", "Stop", "SubagentStart", "SubagentStop", "PreCompact", "SessionStart", "SessionEnd",
}  # fmt: skip
GROUP_KEYS = {"matcher", "hooks"}
HANDLER_KEYS = {"type", "command", "timeout"}
# (event, module, tools its matcher must cover)
REQUIRED = (
    ("PreToolUse", "guard", ("Bash", "Write", "Edit", "MultiEdit", "NotebookEdit")),
    ("PostToolUse", "post_edit", ("Edit", "Write", "MultiEdit")),
    ("Stop", "stop_check", ()),
)
_MODULE = re.compile(r"-m scripts\.hooks\.(\w+)")

Wired = tuple[str, str, str, int | None, str]  # event, matcher, module, timeout, command


def _matches(matcher: str, tool: str) -> bool:
    return matcher in ("", "*") or re.fullmatch(matcher, tool) is not None


def _handler_problems(
    where: str, handler: object, hooks_dir: Path
) -> tuple[list[str], list[tuple[str, int | None, str]]]:
    if not isinstance(handler, dict):
        return [f"{where}: must be an object"], []
    issues = [f"{where}: unknown field {key}" for key in sorted(set(handler) - HANDLER_KEYS)]
    if handler.get("type") != "command":
        issues.append(f'{where}: type must be "command"')
    timeout = handler.get("timeout")
    if timeout is not None and (isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0):
        issues.append(f"{where}: timeout must be a positive number of seconds")
        timeout = None
    command = handler.get("command")
    if not isinstance(command, str) or not command.strip():
        return [*issues, f"{where}: command must be a non-empty string"], []
    modules = []
    for module in _MODULE.findall(command):
        if not (hooks_dir / f"{module}.py").is_file():
            issues.append(f"{where}: scripts.hooks.{module} does not exist")
        modules.append((module, timeout, command))
    return issues, modules


def _group_problems(event: str, index: int, group: object, hooks_dir: Path) -> tuple[list[str], list[Wired]]:
    where = f"{event}[{index}]"
    if not isinstance(group, dict):
        return [f"{where}: must be an object"], []
    issues = [f"{where}: unknown field {key}" for key in sorted(set(group) - GROUP_KEYS)]
    matcher = group.get("matcher", "")
    if not isinstance(matcher, str):
        issues.append(f"{where}: matcher must be a string")
        matcher = ""
    else:
        try:
            re.compile(matcher)
        except re.error:
            issues.append(f"{where}: matcher is not a valid regular expression")
            matcher = ""
    handlers = group.get("hooks")
    if not isinstance(handlers, list) or not handlers:
        return [*issues, f"{where}: hooks must be a non-empty list"], []
    wired: list[Wired] = []
    for position, handler in enumerate(handlers):
        found, modules = _handler_problems(f"{where}.hooks[{position}]", handler, hooks_dir)
        issues.extend(found)
        wired.extend((event, matcher, module, timeout, command) for module, timeout, command in modules)
    return issues, wired


def _required_problems(wired: list[Wired]) -> list[str]:
    issues: list[str] = []
    for event, module, tools in REQUIRED:
        entries = [entry for entry in wired if entry[0] == event and entry[2] == module]
        if not entries:
            issues.append(f"{event} must run scripts.hooks.{module}")
            continue
        issues.extend(
            f"{event} must run scripts.hooks.{module} for the {tool} tool"
            for tool in tools
            if not any(_matches(entry[1], tool) for entry in entries)
        )
        if module == "guard":
            issues.extend(
                "the guard's command must end with `|| exit 2`, so it fails closed"
                for entry in entries
                if not entry[4].rstrip().endswith("|| exit 2")
            )
        if module == "stop_check":
            issues.extend(
                f"Stop runs scripts.hooks.stop_check with a timeout under {TIMEOUT_SECONDS + 1} s"
                for entry in entries
                if entry[3] is None or entry[3] <= TIMEOUT_SECONDS
            )
    return issues


def problems(settings: object, hooks_dir: Path = HOOKS_DIR) -> list[str]:
    """Everything wrong with a parsed settings file."""
    if not isinstance(settings, dict):
        return ["settings must be a JSON object"]
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return ['"hooks" must be an object mapping events to matcher groups']
    issues: list[str] = []
    wired: list[Wired] = []
    for event, groups in hooks.items():
        if event not in EVENTS:
            issues.append(f"{event}: not a documented hook event")
            continue
        if not isinstance(groups, list) or not groups:
            issues.append(f"{event}: must be a non-empty list of matcher groups")
            continue
        for index, group in enumerate(groups):
            found, entries = _group_problems(event, index, group, hooks_dir)
            issues.extend(found)
            wired.extend(entries)
    return issues + _required_problems(wired)


def check(path: Path = SETTINGS) -> CheckResult:
    if not path.is_file():
        return CheckResult(NAME, ok=False, message=f"{path} is missing")
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return CheckResult(NAME, ok=False, message=f"{path.name} is not valid JSON: {error}")
    issues = problems(settings)
    if issues:
        return CheckResult(NAME, ok=False, message="; ".join(issues))
    return CheckResult(NAME, ok=True)


if __name__ == "__main__":
    raise SystemExit(report(check()))
