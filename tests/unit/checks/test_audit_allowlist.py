"""Task 7.2: a known vulnerability fails the audit unless allowlisted with a reason and expiry (R11)."""

from __future__ import annotations

import datetime as dt
import json
import subprocess
from collections.abc import Sequence

from scripts.checks import audit

TODAY = dt.date(2026, 10, 25)
REPORT = json.dumps(
    {
        "dependencies": [
            {
                "name": "cryptography",
                "version": "48.0.1",
                "vulns": [{"id": "PYSEC-2026-11", "fix_versions": ["49.0.0"]}],
            },
            {"name": "pydantic", "version": "2.14.1", "vulns": []},
        ]
    }
)


def _runner(audit_code: int, audit_out: str = REPORT, audit_err: str = "") -> audit.Runner:
    def run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        if args[0] == "uv":
            return subprocess.CompletedProcess(list(args), 0, stdout="pydantic==2.14.1\n", stderr="")
        return subprocess.CompletedProcess(list(args), audit_code, stdout=audit_out, stderr=audit_err)

    return run


def _allow(entry: str) -> list[audit.AllowEntry]:
    return audit.parse_allowlist(f"[[ignore]]\n{entry}\n")


def test_known_vulnerability_fails() -> None:
    result = audit.check([], run=_runner(1), today=TODAY)
    assert not result.ok
    assert result.message == "cryptography 48.0.1: PYSEC-2026-11 (fixed in 49.0.0)"


def test_allowlisted_vulnerability_passes() -> None:
    allow = _allow('id = "PYSEC-2026-11"\nreason = "no Intel-Mac wheel for 49"\nexpires = 2026-12-31')
    assert audit.check(allow, run=_runner(1), today=TODAY).ok


def test_expired_entry_fails() -> None:
    allow = _allow('id = "PYSEC-2026-11"\nreason = "no Intel-Mac wheel for 49"\nexpires = 2026-10-01')
    result = audit.check(allow, run=_runner(0, json.dumps({"dependencies": []})), today=TODAY)
    assert not result.ok
    assert result.message == "allowlist entry PYSEC-2026-11 expired on 2026-10-01"


def test_entry_requires_reason() -> None:
    allow = _allow('id = "PYSEC-2026-11"\nexpires = 2026-12-31')
    result = audit.check(allow, run=_runner(1), today=TODAY)
    assert not result.ok
    assert "allowlist entry PYSEC-2026-11 has no reason" in result.message


def test_offline_audit_fails_not_passes() -> None:
    result = audit.check([], run=_runner(1, "", "ConnectionError: Max retries exceeded"), today=TODAY)
    assert not result.ok
    assert result.message.startswith("audit could not run (it needs network access):")


def test_clean_audit_passes() -> None:
    assert audit.check([], run=_runner(0, json.dumps({"dependencies": []})), today=TODAY).ok


def test_failed_export_fails() -> None:
    def run(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(list(args), 2, stdout="", stderr="error: lockfile is stale")

    result = audit.check([], run=run, today=TODAY)
    assert result.message == "audit could not run (it needs network access): error: lockfile is stale"


def test_entry_without_expiry_fails() -> None:
    allow = _allow('id = "PYSEC-2026-11"\nreason = "no wheel"')
    assert (
        "allowlist entry PYSEC-2026-11 has no expiry date"
        in audit.check(allow, run=_runner(1), today=TODAY).message
    )


def test_repository_allowlist_entries_are_complete() -> None:
    entries = audit.parse_allowlist(audit.ALLOWLIST.read_text(encoding="utf-8"))
    assert all(entry.reason and entry.expires for entry in entries)
