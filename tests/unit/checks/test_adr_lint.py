"""Task 4.4: every ADR has a dated status, the required sections and at least one source (R18.1, R18.2)."""

from __future__ import annotations

from pathlib import Path

from scripts.checks import adr_lint

GOOD = """# ADR-0042: Something

- **Status:** Accepted by the owner, 2026-10-24
- **Deciders:** the owner

## Context
c
## Options
o
## Decision
d
## Consequences
c
## Sources
- [A source](https://example.org/)
"""


def test_good_adr_passes() -> None:
    assert adr_lint.problems("0042-something.md", GOOD) == []


def test_missing_section_fails() -> None:
    text = GOOD.replace("## Options\no\n", "")
    assert adr_lint.problems("0042-something.md", text) == ["0042-something.md: missing section ## Options"]


def test_no_sources_fails() -> None:
    text = GOOD.replace("- [A source](https://example.org/)\n", "- none yet\n")
    assert adr_lint.problems("0042-something.md", text) == ["0042-something.md: ## Sources cites no link"]


def test_undated_status_fails() -> None:
    text = GOOD.replace("Accepted by the owner, 2026-10-24", "Accepted")
    assert adr_lint.problems("0042-something.md", text) == [
        "0042-something.md: status line must name Proposed, Accepted or Superseded and a YYYY-MM-DD date"
    ]


def test_repo_adrs_pass() -> None:
    adr_dir = Path(__file__).resolve().parents[3] / "docs" / "adr"
    for path in sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md")):
        if path.name.startswith("0000-"):
            continue
        assert adr_lint.problems(path.name, path.read_text(encoding="utf-8")) == []


def test_check_reports_bad_adrs_and_skips_template(tmp_path: Path) -> None:
    (tmp_path / "0000-template.md").write_text("# template without sections\n", encoding="utf-8")
    (tmp_path / "0001-good.md").write_text(GOOD, encoding="utf-8")
    assert adr_lint.check(tmp_path).ok
    (tmp_path / "0002-bad.md").write_text(GOOD.replace("## Decision\nd\n", ""), encoding="utf-8")
    result = adr_lint.check(tmp_path)
    assert not result.ok
    assert result.message == "0002-bad.md: missing section ## Decision"
