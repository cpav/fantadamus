"""mvp-sources task 5.1: what the injured and suspended pages say about one player, as an answer says it: the
reason, when he's back, one booking from a ban, and where an outlet disagrees (design C5; R3.2, R3.3)."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from fantadamus.domains.availability.consensus import (
    Availability,
    OfficialStatus,
    OfficialView,
    Status,
    combine,
    outlet_view,
)
from fantadamus.domains.availability.news import back_said, current, news_of, page_disagreement, reason_said
from fantadamus.domains.availability.silver import InjuryRow, SuspensionRow
from fantadamus.domains.facts import Source
from fantadamus.domains.players.resolve import KnownPlayer
from fantadamus.domains.sources import describe

SOURCE = Source(
    source_url="https://www.fantacalcio.it/infortunati-serie-a",
    captured_at=dt.datetime(2026, 11, 15, 9, 0, tzinfo=dt.UTC),
    content_sha256="0" * 64,
)
BANS = SOURCE.model_copy(
    update={"source_url": "https://www.fantacalcio.it/squalificati-e-diffidati-campionato-serie-a"}
)
MATES = [
    KnownPlayer(player_id=1, name="Rossi Marco", club="alfa"),
    KnownPlayer(player_id=2, name="Bianchi", club="alfa"),
    KnownPlayer(player_id=3, name="Verdi D.", club="alfa"),
]
ROSSI = MATES[0]


def _injury(name: str, **facts: Any) -> InjuryRow:
    values = {
        "kind": "other",
        "body_part": None,
        "back_from": None,
        "back_until": None,
        "to_be_assessed": False,
    }
    return InjuryRow(**SOURCE.model_dump(), club=facts.pop("club", "alfa"), name=name, **(values | facts))


def _ban(name: str, status: str = "banned", round: int | None = 12, club: str = "alfa") -> SuspensionRow:
    return SuspensionRow(**BANS.model_dump(), club=club, name=name, status=status, round=round)


@pytest.mark.parametrize(
    ("kind", "part", "said"),
    [
        ("muscle", "thigh", "thigh muscle injury"),
        ("muscle", None, "muscle injury"),
        ("knock", "ankle", "ankle knock"),
        ("fracture", "other", "fracture"),
        ("ligament", "knee", "knee ligament injury"),
        ("surgery", "knee", "knee surgery"),
        ("illness", None, "illness"),
        ("national team", "calf", "calf injury with his national team"),
        ("other", "back", "back injury"),
        ("other", None, "out, detail on the page"),
    ],
)
def test_the_reason(kind: str, part: str | None, said: str) -> None:
    assert reason_said(_injury("Rossi", kind=kind, body_part=part)) == said


@pytest.mark.parametrize(
    ("back_from", "back_until", "assess", "said"),
    [
        (dt.date(2026, 11, 21), dt.date(2026, 11, 30), False, "back from late November"),
        (dt.date(2026, 12, 16), dt.date(2026, 12, 31), False, "back from the second half of December"),
        (dt.date(2026, 12, 11), dt.date(2026, 12, 20), False, "back from mid December"),
        (dt.date(2026, 12, 1), dt.date(2026, 12, 10), False, "back from early December"),
        (dt.date(2027, 2, 1), dt.date(2027, 2, 28), False, "back from February"),
        (dt.date(2026, 12, 7), dt.date(2026, 12, 7), False, "back around 7 December"),
        (dt.date(2026, 12, 5), dt.date(2026, 12, 12), False, "back from 5 December"),
        (None, None, True, "return to be assessed"),
        (None, None, False, None),
    ],
)
def test_when_he_s_back(
    back_from: dt.date | None, back_until: dt.date | None, assess: bool, said: str | None
) -> None:
    row = _injury("Rossi", back_from=back_from, back_until=back_until, to_be_assessed=assess)
    assert back_said(row) == said


def test_a_player_s_news() -> None:
    """His rows are found by name, or by surname as the outlets' are; another club's player of the same name
    isn't him. A ban counts for the round it names, or for every round when it names none."""
    injuries = [
        _injury(
            "Rossi M.",
            kind="muscle",
            body_part="thigh",
            back_from=dt.date(2026, 11, 21),
            back_until=dt.date(2026, 11, 30),
        ),
        _injury("Rossi", club="beta", kind="fracture"),
    ]
    news = news_of(ROSSI, 12, injuries, [], MATES)
    assert news is not None
    assert news.out is not None
    assert (news.out.reason, news.out.back, news.one_booking) == (
        "thigh muscle injury",
        "back from late November",
        False,
    )
    assert news.sources == (SOURCE,)

    banned = news_of(ROSSI, 12, injuries, [_ban("Rossi Marco"), _ban("Rossi Marco", round=13)], MATES)
    assert banned is not None
    assert banned.out is not None
    assert (banned.out.reason, banned.out.back) == (
        "banned for rounds 12 and 13; thigh muscle injury",
        "back from late November",
    )
    later = news_of(ROSSI, 11, [], [_ban("Rossi Marco")], MATES)  # banned for round 12, not round 11
    assert later is None
    whenever = news_of(ROSSI, 11, [], [_ban("Rossi Marco", round=None)], MATES)
    assert whenever is not None
    assert whenever.out is not None
    assert whenever.out.reason == "banned"
    warned = news_of(ROSSI, 12, [], [_ban("Rossi", status="one booking", round=None)], MATES)
    assert warned is not None
    assert (warned.out, warned.one_booking) == (None, True)
    assert news_of(MATES[1], 12, injuries, [_ban("Rossi", status="one booking", round=None)], MATES) is None


def test_by_surname_as_a_last_resort() -> None:
    """A name the page writes with another initial is the club's one player of that surname, as an outlet's
    is."""
    news = news_of(MATES[2], 12, [_injury("Verdi J.", kind="knock")], [], MATES)
    assert news is not None
    assert news.out is not None
    assert news.out.reason == "knock"


def test_the_newest_read() -> None:
    """Only the page's newest read counts: a player it no longer lists is back, and a club it lists with
    nobody gives no row at all."""
    old = _injury("Rossi", kind="knock")
    later = SOURCE.captured_at + dt.timedelta(hours=12)
    new = _injury("Neri", club="beta", kind="illness").model_copy(
        update={"captured_at": later, "content_sha256": "1" * 64}
    )
    assert current([old, new]) == [new]
    assert current([old]) == [old]
    assert current([]) == []


def _present(
    *views: tuple[str, Status, float | None], official: OfficialStatus | None = None
) -> Availability:
    outlets = [outlet_view(name, status, share, SOURCE) for name, status, share in views]
    return combine(outlets, OfficialView(status=official, source=SOURCE) if official else None)


def test_a_disagreement() -> None:
    """The pages have him out while an outlet has him starting, as a starter or at an even chance or more, or
    the official lineup does: said, naming them. An outlet that has him out, or doubtful, doesn't disagree."""
    out = news_of(ROSSI, 12, [_injury("Rossi", kind="muscle", body_part="calf")], [], MATES)
    banned = news_of(ROSSI, 12, [], [_ban("Rossi")], MATES)
    assert out is not None
    assert banned is not None
    both = _present(("Sky", "starter", None), ("Gazzetta", "percentage", 55), ("SOS Fanta", "bench", None))
    assert (
        page_disagreement(out, both)
        == "Gazzetta and Sky have him starting; Fantacalcio.it's injury page has him out."
    )
    assert page_disagreement(banned, _present(("Sky", "percentage", 60))) == (
        "Sky has him starting; Fantacalcio.it's bans page has him banned."
    )
    official = _present(("Sky", "unavailable", None), official="starter")
    assert page_disagreement(out, official) == (
        "The official lineup has him starting; Fantacalcio.it's injury page has him out."
    )
    assert (
        page_disagreement(out, _present(("Sky", "unavailable", None), ("Gazzetta", "percentage", 45))) is None
    )
    assert page_disagreement(out, None) is None
    assert page_disagreement(out, _present(("Gazzetta", "percentage", 50))) == (
        "Gazzetta has him starting; Fantacalcio.it's injury page has him out."
    )


def test_the_pages_are_labelled() -> None:
    """Both pages, at the bottom of an answer."""
    assert describe(SOURCE.source_url) == "Fantacalcio.it, injuries"
    assert describe(BANS.source_url) == "Fantacalcio.it, bans"
