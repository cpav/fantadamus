"""Property P10: a suppression passes the lint iff it names its rule and gives a reason (R6.1, R6.2)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from scripts.checks import suppressions as sup

CODES = st.sampled_from(["S603", "S607", "E501", "B008", "RUF012"])
REASONS = st.text(alphabet=st.characters(categories=["L", "N", "Zs"]), min_size=1, max_size=30).filter(
    lambda s: s.strip() != ""
)


@given(code=CODES, has_code=st.booleans(), reason=REASONS, has_reason=st.booleans(), above=st.booleans())
def test_suppression_lint(code: str, has_code: bool, reason: str, has_reason: bool, above: bool) -> None:
    noqa = f"# noqa: {code}" if has_code else "# noqa"
    if has_reason and above:
        source = f"# reason: {reason}\nrun()  {noqa}\n"
    elif has_reason:
        source = f"run()  {noqa}  # reason: {reason}\n"
    else:
        source = f"run()  {noqa}\n"
    register = sup.parse_register(
        "| ID | Path | Rule | Reason | Approved |\n|---|---|---|---|---|\n"
        f"| S-001 | `m.py` | ruff `{code}` | r | 2026-10-24 |\n"
    )
    problems = sup.problems(sup.find_in_python("m.py", source), register)
    assert (problems == []) == (has_code and has_reason)
