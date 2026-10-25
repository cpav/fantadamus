"""Audit the locked dependencies for known vulnerabilities (R11.1 to R11.3).

A vulnerability fails the audit unless config/audit-allowlist.toml has an entry for its ID (or an alias)
with a reason and an expiry date that hasn't passed. An expired entry fails on its own, and an audit that
can't run (for example offline) fails rather than passes.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.checks._common import CheckResult, Runner, report, run_command

__all__ = ["AllowEntry", "Runner", "check", "parse_allowlist"]

ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST = ROOT / "config" / "audit-allowlist.toml"
EXPORT = (
    "uv",
    "export",
    "--frozen",
    "--all-groups",
    "--no-emit-project",
    "--no-hashes",
    "--format",
    "requirements-txt",
)


@dataclass(frozen=True)
class AllowEntry:
    id: str
    reason: str
    expires: dt.date | None


def parse_allowlist(text: str) -> list[AllowEntry]:
    entries = []
    for raw in tomllib.loads(text).get("ignore", []):
        expires = raw.get("expires")
        entries.append(
            AllowEntry(
                id=str(raw.get("id", "")),
                reason=str(raw.get("reason", "")).strip(),
                expires=expires if isinstance(expires, dt.date) else None,
            )
        )
    return entries


def _allowlist_issues(allow: Sequence[AllowEntry], today: dt.date) -> list[str]:
    issues = []
    for entry in allow:
        if not entry.reason:
            issues.append(f"allowlist entry {entry.id} has no reason")
        if entry.expires is None:
            issues.append(f"allowlist entry {entry.id} has no expiry date")
        elif entry.expires < today:
            issues.append(f"allowlist entry {entry.id} expired on {entry.expires.isoformat()}")
    return issues


def _audit(run: Runner) -> tuple[list[dict[str, Any]] | None, str]:
    exported = run(list(EXPORT))
    if exported.returncode != 0:
        return None, exported.stderr.strip() or "uv export failed"
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
        handle.write(exported.stdout)
    command = [sys.executable, "-m", "pip_audit", "-r", handle.name, "--no-deps", "--disable-pip"]
    command += ["--format", "json", "--progress-spinner", "off", "--strict"]
    completed = run(command)
    Path(handle.name).unlink(missing_ok=True)
    try:
        dependencies: list[dict[str, Any]] = json.loads(completed.stdout)["dependencies"]
    except (json.JSONDecodeError, KeyError, TypeError):
        detail = (completed.stderr or completed.stdout).strip().splitlines()
        return None, detail[-1] if detail else f"pip-audit exited {completed.returncode}"
    return dependencies, ""


def check(
    allow: Sequence[AllowEntry], run: Runner = run_command, today: dt.date | None = None
) -> CheckResult:
    today = today or dt.date.today()
    issues = _allowlist_issues(allow, today)
    dependencies, error = _audit(run)
    if dependencies is None:
        issues.insert(0, f"audit could not run (it needs network access): {error}")
    else:
        allowed = {entry.id for entry in allow if entry.reason and entry.expires and entry.expires >= today}
        for dependency in dependencies:
            for vuln in dependency.get("vulns") or []:
                ids = {str(vuln.get("id")), *map(str, vuln.get("aliases", []) or [])}
                if ids & allowed:
                    continue
                fixes = ", ".join(vuln.get("fix_versions", []) or []) or "no fix yet"
                issues.append(
                    f"{dependency['name']} {dependency['version']}: {vuln.get('id')} (fixed in {fixes})"
                )
    issues = list(dict.fromkeys(issues))  # a package can appear once per platform fork
    if issues:
        return CheckResult("audit", ok=False, message="; ".join(issues))
    return CheckResult("audit", ok=True)


def main() -> int:
    allow = parse_allowlist(ALLOWLIST.read_text(encoding="utf-8")) if ALLOWLIST.exists() else []
    return report(check(allow))


if __name__ == "__main__":
    raise SystemExit(main())
