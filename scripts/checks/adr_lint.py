"""Every ADR has a dated status line, the required sections and a cited source (R18.1, R18.2).

The template (0000-template.md) is skipped. Extra sections, such as Guardrails or Amendments, are allowed.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.checks._common import CheckResult, report

ROOT = Path(__file__).resolve().parents[2]
ADR_DIR = ROOT / "docs" / "adr"
SECTIONS = ("Context", "Options", "Decision", "Consequences", "Sources")

_STATUS = re.compile(r"^- \*\*Status:\*\*\s*(Proposed|Accepted|Superseded)\b.*\b\d{4}-\d{2}-\d{2}\b", re.M)
_HEADING = re.compile(r"^## (?P<title>.+?)\s*$", re.M)
_LINK = re.compile(r"\[[^\]]+\]\((https?://|\.{0,2}/?[\w./-]+)[^)]*\)|https?://\S+")


def problems(name: str, text: str) -> list[str]:
    """List what this ADR lacks."""
    issues: list[str] = []
    if not _STATUS.search(text):
        issues.append(f"{name}: status line must name Proposed, Accepted or Superseded and a YYYY-MM-DD date")
    headings = [match.group("title") for match in _HEADING.finditer(text)]
    issues.extend(f"{name}: missing section ## {section}" for section in SECTIONS if section not in headings)
    if "Sources" in headings:
        body = text.split("## Sources", 1)[1]
        following = _HEADING.search(body)
        sources = body[: following.start()] if following else body
        if not _LINK.search(sources):
            issues.append(f"{name}: ## Sources cites no link")
    return issues


def check(adr_dir: Path = ADR_DIR) -> CheckResult:
    issues: list[str] = []
    for path in sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md")):
        if path.name.startswith("0000-"):
            continue
        issues.extend(problems(path.name, path.read_text(encoding="utf-8")))
    if issues:
        return CheckResult("adr-lint", ok=False, message="; ".join(issues))
    return CheckResult("adr-lint", ok=True)


if __name__ == "__main__":
    raise SystemExit(report(check()))
