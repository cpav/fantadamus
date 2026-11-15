"""P2 of mvp-alerts: a call compared with itself has no changes; two calls have changes exactly when they have
them the other way round; chances and the bench below each role's first place never count (design C1; R2.1,
R2.3)."""

from __future__ import annotations

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.alerts import Call, call_of, changes
from tests.alerts_data import AT, LATER, ROLES

_SQUAD = sorted(ROLES)
_CHANCES = st.dictionaries(st.sampled_from(_SQUAD), st.floats(0.0, 1.0))


@st.composite
def _parts(draw: st.DrawFn) -> dict[str, Any]:
    starters = draw(st.lists(st.sampled_from(_SQUAD), unique=True, min_size=1, max_size=11))
    bench = draw(st.permutations([player for player in _SQUAD if player not in starters]))
    return {
        "round": 12,
        "formation": draw(st.sampled_from(["3-4-3", "4-4-2", "4-3-3"])),
        "starters": starters,
        "bench": bench,
        "roles": ROLES,
        "captain": draw(st.none() | st.sampled_from(starters)),
        "vice": draw(st.none() | st.sampled_from(starters)),
        "chances": draw(_CHANCES),
        "at": AT,
    }


_CALLS = _parts().map(lambda parts: call_of(**parts))


@given(_CALLS)
def test_p2_a_call_has_no_changes_from_itself(call: Call) -> None:
    assert changes(call, call, ROLES) == []


@given(_CALLS, _CALLS)
def test_p2_changes_are_empty_exactly_both_ways(first: Call, second: Call) -> None:
    assert (changes(first, second, ROLES) == []) == (changes(second, first, ROLES) == [])


@given(_parts(), _CHANCES, st.data())
def test_p2_chances_and_lower_bench_places_never_count(
    parts: dict[str, Any], chances: dict[int, float], data: st.DataObject
) -> None:
    """Each role's first stays first; everyone below is shuffled, and every chance redrawn."""
    call = call_of(**parts)
    firsts = list(call.first_on_bench.values())
    below = data.draw(st.permutations([player for player in parts["bench"] if player not in firsts]))
    moved = call_of(**(parts | {"bench": [*firsts, *below], "chances": chances, "at": LATER}))
    assert changes(call, moved, ROLES) == []
