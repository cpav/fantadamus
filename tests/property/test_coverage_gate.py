"""Property P13: the coverage gate fails iff line or branch coverage is below its threshold (R8.2, R8.3)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from scripts.checks import coverage_gate


@st.composite
def counts(draw: st.DrawFn) -> tuple[int, int]:
    total = draw(st.integers(min_value=0, max_value=5000))
    return draw(st.integers(min_value=0, max_value=total)), total


@given(lines=counts(), branches=counts(), line_min=st.integers(0, 100), branch_min=st.integers(0, 100))
def test_coverage_gate(
    lines: tuple[int, int], branches: tuple[int, int], line_min: int, branch_min: int
) -> None:
    totals = {
        "covered_lines": lines[0],
        "num_statements": lines[1],
        "covered_branches": branches[0],
        "num_branches": branches[1],
    }
    line_pct = 100.0 if lines[1] == 0 else 100.0 * lines[0] / lines[1]
    branch_pct = 100.0 if branches[1] == 0 else 100.0 * branches[0] / branches[1]
    expected_ok = line_pct >= line_min and branch_pct >= branch_min
    assert coverage_gate.evaluate(totals, line_min=line_min, branch_min=branch_min).ok == expected_ok
