"""P5 of mvp-alerts: every change is written out, naming its players (a bench place names who has it now), or
counted in "more changes"; the text always fits (design C3; R3.1)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.alerts import Cause, Change, alert_text

_IDS = st.integers(1, 30)
_NAMES = st.dictionaries(
    _IDS, st.text(st.characters(categories=["L"]), min_size=1, max_size=30), min_size=30, max_size=30
)
_CHANGES = st.lists(
    st.one_of(
        st.builds(Change, st.just("swap"), now=_IDS, before=_IDS, role=st.just("D")),
        st.builds(Change, st.just("in"), now=_IDS),
        st.builds(Change, st.just("out"), before=_IDS),
        st.builds(Change, st.just("captain"), now=_IDS, before=_IDS),
        st.builds(Change, st.just("bench"), now=_IDS, before=_IDS, role=st.just("C")),
        st.just(Change("formation", formations=("3-4-3", "4-4-2"))),
    ),
    min_size=1,
    max_size=8,
)
_CAUSES = st.none() | st.builds(
    Cause, st.sampled_from(["official", "injury", "ban", "outlets"]), st.text(max_size=120)
)


@given(_CHANGES, st.data(), _NAMES, st.integers(120, 400))
def test_p5_every_change_named_or_counted(
    found: list[Change], data: st.DataObject, names: dict[int, str], limit: int
) -> None:
    causes = [data.draw(_CAUSES) for _ in found]
    alert = alert_text(12, found, causes, names, limit=limit)
    assert len(alert.text) <= limit
    assert 1 <= alert.shown <= len(found)
    for change in found[: alert.shown]:
        named = (change.now,) if change.kind == "bench" else (change.now, change.before)
        for player in named:
            if player is not None:
                assert names[player] in alert.text
    rest = len(found) - alert.shown
    if rest:
        assert f"And {rest} more change" in alert.text
