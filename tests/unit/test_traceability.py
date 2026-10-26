"""Task 14.2: every acceptance test proves existing requirements, and every local one has a test (R21.3)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = ROOT / ".kiro" / "specs" / "engineering-foundation" / "requirements.md"
ACCEPTANCE = ROOT / "tests" / "acceptance"


def _table() -> list[tuple[str, str, str]]:
    """(AT number, the "Proves" cell, the "Gate" cell) for each row of the acceptance-test table."""
    rows = []
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        if match := re.match(r"\| AT-(\d+) \|", line):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            rows.append((match.group(1), cells[2], cells[3]))
    return rows


def test_acceptance_tests_map_to_existing_requirements() -> None:
    text = REQUIREMENTS.read_text(encoding="utf-8")
    known = set(re.findall(r"^- \*\*(R\d+\.\d+)\*\*", text, re.M))
    rows = _table()
    assert len(rows) == 21
    for number, proves, _ in rows:
        ids = re.findall(r"R\d+\.\d+", proves)  # both ends of a range such as R16.1 to R16.13
        assert ids, f"AT-{number} proves nothing"
        for rid in ids:
            assert rid in known, f"AT-{number} names {rid}"


def test_local_acceptance_tests_exist() -> None:
    defined = set()
    for path in ACCEPTANCE.glob("test_*.py"):
        defined |= set(re.findall(r"^def test_at(\d+)_", path.read_text(encoding="utf-8"), re.M))
    local = {number for number, _, gate in _table() if gate in {"Local", "Both"}}
    assert local - defined == set(), "local acceptance tests without a test function"
