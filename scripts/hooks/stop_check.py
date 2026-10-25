"""Stop: run `make check` when the turn changed anything, and send a failure back to the agent (R17.3).

"Changed" means the working tree differs from the last time `make check` passed: the hash covers HEAD and
the status and contents of every changed or untracked, non-ignored path, and is kept in
`<git dir>/fantadamus-last-green`.

- No change: report that no check was needed.
- Green: record the state.
- Red: exit 2 with the failing checks, so the agent keeps working.
- Red again while `stop_hook_active` is set: exit 1, a non-blocking error the user sees, so the turn can end
  but never silently on a red build.
- A run over 10 minutes counts as a failure, naming the check that was running.

The full output of the last run is kept in `<git dir>/fantadamus-stop-check.log`, because Claude Code shows
only the summary.
"""

from __future__ import annotations

import hashlib
import subprocess
from collections.abc import Callable
from pathlib import Path

from scripts.checks._common import run_command
from scripts.hooks.event import HookEvent, HookResult, git_dir, project_root, run_hook

TIMEOUT_SECONDS = 600
STATE_FILE = "fantadamus-last-green"
LOG_FILE = "fantadamus-stop-check.log"
TAIL_LINES = 20

CheckRunner = Callable[[], subprocess.CompletedProcess[str]]


def tree_state(root: Path) -> str:
    """A hash of HEAD, the status of every changed or untracked, non-ignored path, and their contents."""
    digest = hashlib.sha256()
    head = run_command(["git", "-C", str(root), "rev-parse", "--verify", "--quiet", "HEAD"])
    digest.update((head.stdout if head.returncode == 0 else "no-head").encode())
    status = run_command(["git", "-C", str(root), "status", "--porcelain=v1", "-z", "--untracked-files=all"])
    digest.update(status.stdout.encode())
    for entry in filter(None, status.stdout.split("\0")):
        # An entry is "XY path"; a rename's original path follows as its own entry.
        path = root / (entry[3:] if len(entry) > 3 and entry[2] == " " else entry)
        try:
            digest.update(b"\0" + path.read_bytes())
        except OSError:
            digest.update(b"\0<missing>")
    return digest.hexdigest()


def summary(output: str) -> str:
    """The failing checks and tests and the totals line of `make check`, or its last lines if none match."""
    lines = output.splitlines()
    picked = [
        line
        for line in lines
        if line.startswith(("FAIL ", "FAILED ", "ERROR ")) or (" passed, " in line and " failed" in line)
    ]
    return "\n".join(picked or lines[-TAIL_LINES:])


def _running(partial: str) -> str:
    """The check `make check` was running, from the last `==> name` header in its output so far."""
    headers = [line.removeprefix("==> ") for line in partial.splitlines() if line.startswith("==> ")]
    return headers[-1] if headers else "unknown"


def _text(value: str | bytes | None) -> str:
    return value.decode(errors="replace") if isinstance(value, bytes) else value or ""


def handle(
    event: HookEvent, *, state: str, last_green: Path, run_check: CheckRunner, log: Path | None = None
) -> HookResult:
    if last_green.is_file() and last_green.read_text(encoding="utf-8").strip() == state:
        return HookResult(0, stdout="No changes since the last green make check; no check needed.\n")
    passed = False
    try:
        completed = run_check()
    except subprocess.TimeoutExpired as expired:
        output = _text(expired.output) + _text(expired.stderr)
        failure = (
            f"make check timed out after 10 minutes while running: {_running(output)}. "
            "A timeout counts as a failure."
        )
    else:
        output = completed.stdout + completed.stderr
        passed = completed.returncode == 0
        failure = "" if passed else summary(output) or f"make check exited with {completed.returncode}"
    if log is not None:
        log.write_text(output, encoding="utf-8")
    if passed:
        last_green.write_text(state + "\n", encoding="utf-8")
        return HookResult(0, stdout="make check passed.\n")
    where = f"\nFull output: {log}" if log is not None else ""
    if event.stop_hook_active:
        return HookResult(
            1, stderr=f"make check is still red; the turn ends with these failures:\n{failure}{where}\n"
        )
    return HookResult(
        2, stderr=f"make check failed. Fix it, or tell the owner why it is red:\n{failure}{where}\n"
    )


def _make_check(root: Path) -> CheckRunner:
    def run() -> subprocess.CompletedProcess[str]:
        return run_command(["make", "check"], cwd=root, timeout=TIMEOUT_SECONDS)

    return run


def main() -> int:
    root = project_root()

    def handler(event: HookEvent) -> HookResult:
        directory = git_dir(root)
        return handle(
            event,
            state=tree_state(root),
            last_green=directory / STATE_FILE,
            run_check=_make_check(root),
            log=directory / LOG_FILE,
        )

    return run_hook(handler, invalid_code=1)


if __name__ == "__main__":
    raise SystemExit(main())
