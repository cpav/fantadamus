"""AT-4 of mvp-cards: each side's likely eleven with its confidence, the disputed places with their contenders
and the outlets that differ, who's out, and the official lineups once stored (design C3; R3)."""

from __future__ import annotations

import datetime as dt

from fantadamus.domains.cards import Listed, lineups
from tests.cards_data import KICKOFF, listed

SQUAD = [
    listed("Alfa Uno", "P"),
    listed(
        "Alfa Dodici", "P", (40, 40, 40, 40)
    ),  # a keeper above the 11th outfielder still isn't a 2nd keeper
    listed("Alfa Due", "D"),
    listed("Alfa Tre", "D"),
    listed("Alfa Quattro", "D"),
    listed("Alfa Cinque", "D", (80, 80, 85, 80)),
    listed("Alfa Sei", "C"),
    listed("Alfa Sette", "C"),
    listed("Alfa Otto", "C", (70, 70, 75, 70)),
    listed("Alfa Nove", "A"),
    listed("Alfa Dieci", "A"),
    listed("Alfa Undici", "A", (35, 35, 35, 35)),
    listed("Alfa Tredici", "A", (10, 30, 5, 30)),
    listed("Beta Nove", "A", club="beta"),
]


def _names(found: list[Listed]) -> list[str]:
    return [part.player.name for part in found]


def test_at4_a_likely_eleven() -> None:
    """The eleven likeliest, one keeper, in role order and likeliest first, each with his chance and how sure
    it is; another club's players don't count."""
    found = lineups("alfa", SQUAD, KICKOFF)
    assert [(player.name, player.role) for player in found.eleven] == [
        ("Alfa Uno", "P"),
        ("Alfa Due", "D"),
        ("Alfa Quattro", "D"),
        ("Alfa Tre", "D"),
        ("Alfa Cinque", "D"),
        ("Alfa Sei", "C"),
        ("Alfa Sette", "C"),
        ("Alfa Otto", "C"),
        ("Alfa Dieci", "A"),
        ("Alfa Nove", "A"),
        ("Alfa Undici", "A"),
    ]
    first = found.eleven[0]
    assert first.p_start == 0.9125
    assert (first.confidence.label, first.confidence.sources) == ("agree", 4)
    assert not found.official
    assert found.official_due == KICKOFF - dt.timedelta(hours=1)
    assert found.disputed == []
    assert found.out == []


def test_at4_a_ballottaggio_is_one_place() -> None:
    """Two players an outlet sets against each other are one place, best first, whichever side named whom."""
    contest = [
        *SQUAD[:9],
        listed("Alfa Nove", "A", (90, 60, 90, 90), rivals={"Gazzetta": ["Alfa Undici"]}),
        listed("Alfa Undici", "A", (35, 40, 35, 35), rivals={"Gazzetta": ["NOVE A"]}),
        SQUAD[10],
    ]
    found = lineups("alfa", contest, KICKOFF)
    assert [
        [(contender.name, contender.p_start) for contender in place.contenders] for place in found.disputed
    ] == [[("Alfa Nove", 0.825), ("Alfa Undici", 0.3625)]]
    assert found.disputed[0].role == "A"


def test_at4_two_places_and_a_rival_written_another_way() -> None:
    """Two ballottaggi on one side are two places, however their contenders' chances interleave; and a rival
    the outlet writes with the wrong initial is still found by his surname, though only one side names him."""
    contest = [
        *SQUAD[:5],
        listed("Alfa Sei", "C", (80, 80, 80, 80), rivals={"Gazzetta": ["Alfa Otto"]}),
        listed("Alfa Sette", "C", (60, 60, 60, 60), rivals={"Sky": ["Alfa Dodici"]}),
        listed("Alfa Otto", "C", (30, 30, 30, 30), rivals={"Gazzetta": ["Alfa Sei"]}),
        listed("Alfa Dodici", "C", (50, 50, 50, 50), rivals={"Sky": ["Alfa Sette"]}),
        listed("Alfa Nove", "A", (90, 90, 90, 90), rivals={"SOS Fanta": ["UNDICI B"]}),
        SQUAD[10],
        listed("Alfa Undici", "A", (20, 20, 20, 20)),
    ]
    found = lineups("alfa", contest, KICKOFF)
    assert [[contender.name for contender in place.contenders] for place in found.disputed] == [
        ["Alfa Sei", "Alfa Otto"],
        ["Alfa Sette", "Alfa Dodici"],
        ["Alfa Nove", "Alfa Undici"],
    ]


def test_at4_an_outlet_that_disagrees() -> None:
    """A disputed player is a place of his own, naming the outlets on the smaller side of the consensus; an
    even split names none."""
    lone = [*SQUAD[:2], listed("Alfa Due", "D", (90, 90, 90, 30)), *SQUAD[3:]]
    place = lineups("alfa", lone, KICKOFF).disputed
    assert [(c.name, c.dissent) for p in place for c in p.contenders] == [("Alfa Due", ["Sky"])]
    split = [*SQUAD[:2], listed("Alfa Due", "D", (90, 30, 90, 30)), *SQUAD[3:]]
    place = lineups("alfa", split, KICKOFF).disputed
    assert [(c.name, c.dissent) for p in place for c in p.contenders] == [("Alfa Due", [])]
    spread = [*SQUAD[:2], listed("Alfa Due", "D", (90, 60, 60, 30)), *SQUAD[3:]]  # two views on the consensus
    place = lineups("alfa", spread, KICKOFF).disputed
    assert [(c.name, c.dissent) for p in place for c in p.contenders] == [("Alfa Due", [])]


def test_at4_the_unavailable() -> None:
    """Out, with how many outlets say so, and not in the eleven."""
    hurt = [*SQUAD[:9], listed("Alfa Nove", "A", (None, None, None, 30)), *SQUAD[10:]]
    found = lineups("alfa", hurt, KICKOFF)
    assert [(out.name, out.role, out.outlets) for out in found.out] == [("Alfa Nove", "A", 3)]
    assert "Alfa Nove" not in [player.name for player in found.eleven]


def test_at4_the_official_lineups() -> None:
    """Once the official sheet is stored it's the eleven, whatever the outlets said, with nothing left
    disputed or due."""
    starters = {"Alfa Uno", "Alfa Due", "Alfa Tre", "Alfa Quattro", "Alfa Sei", "Alfa Sette", "Alfa Otto"}
    starters |= {"Alfa Nove", "Alfa Dieci", "Alfa Undici", "Alfa Tredici"}
    with_a_dispute = [*SQUAD[:2], listed("Alfa Due", "D", (90, 90, 90, 30)), *SQUAD[3:]]
    sheet = [
        listed(
            part.player.name,
            part.role,
            [view.p_start * 100 for view in part.present.outlets],
            club=part.player.club,
            official="starter" if part.player.name in starters else "bench",
        )
        for part in with_a_dispute
    ]
    found = lineups("alfa", sheet, KICKOFF)
    assert {player.name for player in found.eleven} == starters
    assert {player.confidence.label for player in found.eleven} == {"official"}
    assert found.official
    assert found.official_due is None
    assert found.disputed == []
