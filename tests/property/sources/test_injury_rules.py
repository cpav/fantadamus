"""P3 of mvp-sources: the injury rules give a known kind or "other", a known body part or none, and a return
window, if any, that holds together and isn't in a month before the read's (design C4; R3.1)."""

from __future__ import annotations

import datetime as dt
from typing import get_args

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.contracts.xy.unavailable import BodyPart, InjuryKind
from fantadamus.web.readers.injury_rules import back_of, body_part_of, kind_of

MONTHS = (
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)
_KIND = st.sampled_from(
    [
        "",
        "una lesione muscolare",
        "la frattura",
        "una contusione",
        "operato",
        "la febbre",
        "ko in Nazionale",
        "un fastidio fisico",
        "una lesione del crociato",
        "durante la sosta per le Nazionali",
    ]
)
_PART = st.sampled_from(
    [
        "",
        "al ginocchio",
        "alla coscia",
        "al bicipite femorale",
        "agli adduttori",
        "alla caviglia",
        "alla mano",
    ]
)
_MONTH = st.sampled_from(MONTHS)


@st.composite
def _back(draw: st.DrawFn) -> str:
    month = draw(_MONTH)
    part = draw(st.sampled_from(["", "inizio di ", "metà ", "la seconda metà di ", "la fine di ", "fine "]))
    number = draw(st.sampled_from(["due", "tre", "sei", "4", "10"]))
    unit = draw(st.sampled_from(["giorni", "settimane", "mesi"]))
    day = draw(st.integers(1, 28))
    return draw(
        st.sampled_from(
            [
                "",
                f"rientro da{'l' if part.startswith('la') else ''} {part}{month}",
                f"recuperabile da {part}{month}",
                f"stop di circa {number} {unit}",
                f"stop di circa {number} {unit} dal {day} {month}",
                f"fermo dal {day} {month}",
                "da valutare",
            ]
        )
    )


@given(_KIND, _PART, _back(), st.dates(dt.date(2026, 7, 1), dt.date(2027, 6, 30)))
def test_p3_a_known_kind_and_a_later_return(kind: str, part: str, back: str, today: dt.date) -> None:
    sentence = f"Il giocatore fermato per {kind} {part}, {back}."
    assert kind_of(sentence) in get_args(InjuryKind)
    assert body_part_of(sentence) in (*get_args(BodyPart), None)
    found = back_of(sentence, today)
    assert (found.back_from is None) == (found.back_until is None)
    if found.back_from is not None and found.back_until is not None:
        assert found.back_from <= found.back_until
        assert found.back_until >= today.replace(day=1)
        assert not found.to_be_assessed
