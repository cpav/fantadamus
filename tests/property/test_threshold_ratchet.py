"""Property P9: the ratchet fails iff some threshold moved against its direction (R6.5)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from scripts.checks import thresholds

ENTRY = st.fixed_dictionaries(
    {"value": st.integers(min_value=0, max_value=1000), "direction": st.sampled_from(["up", "down"])}
)
NAMES = st.sampled_from(
    ["coverage_line", "coverage_branch", "hypothesis_ci_examples", "ci_time_budget_minutes"]
)


@given(
    base=st.dictionaries(NAMES, ENTRY, min_size=1),
    deltas=st.lists(st.integers(-50, 50), min_size=4, max_size=4),
)
def test_threshold_ratchet(base: dict[str, dict[str, object]], deltas: list[int]) -> None:
    new = {
        name: {"value": int(str(entry["value"])) + delta, "direction": entry["direction"]}
        for (name, entry), delta in zip(sorted(base.items()), deltas, strict=False)
    }
    weakened = any(
        (entry["direction"] == "up" and int(str(new[name]["value"])) < int(str(entry["value"])))
        or (entry["direction"] == "down" and int(str(new[name]["value"])) > int(str(entry["value"])))
        for name, entry in base.items()
    )
    assert (thresholds.compare(base, new) != []) == weakened
