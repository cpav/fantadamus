"""mvp-collect task 1.3: an outlet's own percentage is its view; each outlet counts once (design C5; R4)."""

from __future__ import annotations

import datetime as dt

import pytest

from fantadamus.domains.availability import gold
from fantadamus.domains.availability.consensus import combine, outlet_view
from fantadamus.domains.availability.silver import LineupViewRow, OutletViewRow
from fantadamus.domains.facts import Source
from fantadamus.domains.players.resolve import KnownPlayer

pytestmark = pytest.mark.usefixtures("start_values")  # worked out by hand on the starting values

NOVE = KnownPlayer(player_id=9, name="Alfa Nove", club="alfa")
EARLY = dt.datetime(2026, 10, 30, 9, 0, tzinfo=dt.UTC)
LATE = EARLY + dt.timedelta(hours=2)


def _source(at: dt.datetime, sha: str) -> Source:
    return Source(source_url="https://example.org/p", captured_at=at, content_sha256=sha * 64)


def test_percentages_are_views() -> None:
    views = [
        outlet_view(name, "percentage", percent, _source(EARLY, "a"))
        for name, percent in (("Uno", 90), ("Due", 90), ("Tre", 55), ("Quattro", 90))
    ]
    assert views[2].p_start == 0.55
    result = combine(views)
    assert result.p_start == pytest.approx(0.8125)
    assert (result.spread, result.disputed) == (0.35, True)
    assert result.p_cameo == pytest.approx(0.5 * (1 - 0.8125))


def test_same_outlet_counts_once() -> None:
    match = {"home": "alfa", "away": "beta"}
    status_row = LineupViewRow(
        **_source(EARLY, "a").model_dump(),
        **match,
        outlet="Fantacalcio.it",
        club="alfa",
        name="Alfa Nove",
        status="starter",
        share=None,
    )
    percent_rows = [
        OutletViewRow(
            **_source(LATE, "b").model_dump(),
            **match,
            outlet="fantacalcio.it",
            club="alfa",
            name="Alfa Nove",
            role="A",
            percent=62,
            unavailable=False,
        ),
        OutletViewRow(
            **_source(LATE, "b").model_dump(),
            **match,
            outlet="fantacalcio.it",
            club="alfa",
            name="Alfa Quattordici",
            role=None,
            percent=None,
            unavailable=True,
        ),
    ]
    found = gold.availability(
        NOVE,
        home=match["home"],
        away=match["away"],
        views=[status_row],
        outlet_views=percent_rows,
        officials=[],
        players=[NOVE],
        as_of=LATE,
    )
    assert found is not None
    assert [(view.outlet, view.status, view.p_start) for view in found.outlets] == [
        ("fantacalcio.it", "percentage", 0.62)
    ]
    earlier = gold.availability(
        NOVE,
        home=match["home"],
        away=match["away"],
        views=[status_row],
        outlet_views=percent_rows,
        officials=[],
        players=[NOVE],
        as_of=EARLY,
    )
    assert earlier is not None
    assert [(view.status, view.p_start) for view in earlier.outlets] == [("starter", 0.9)]
    quattordici = KnownPlayer(player_id=14, name="Alfa Quattordici", club="alfa")
    out = gold.availability(
        quattordici,
        home=match["home"],
        away=match["away"],
        views=[],
        outlet_views=percent_rows,
        officials=[],
        players=[NOVE, quattordici],
        as_of=LATE,
    )
    assert out is not None
    assert (out.p_start, out.p_cameo) == (0.0, 0.0)


def _sheet_row(name: str, role: str, percent: float | None, club: str = "alfa") -> OutletViewRow:
    return OutletViewRow(
        **_source(EARLY, "b").model_dump(),
        home="alfa",
        away="beta",
        outlet="Gazzetta",
        club=club,
        name=name,
        role=role,
        percent=percent,
        unavailable=False,
    )


def test_rivals_from_percentages() -> None:
    """Testing on the real tools: the round page names no ballottaggi, but shows them as two players of one
    role whose percentages make 100, like 55 and 45. The sheets' defaults (90 and 30, 95 and 5) are no
    contest."""
    sheet = [
        _sheet_row("Alfa Uno", "C", 55),
        _sheet_row("Alfa Due", "C", 45),
        _sheet_row("Alfa Tre", "C", 70),  # 70 and 30 could be anyone on the bench, whose default is 30
        _sheet_row("Alfa Quattro", "C", 30),
        _sheet_row("Alfa Cinque", "C", 95),
        _sheet_row("Alfa Sei", "C", 5),
        _sheet_row("Alfa Sette", "D", 45),  # another role
        _sheet_row("Beta Uno", "C", 45, club="beta"),  # another club
        _sheet_row("Alfa Otto", "C", None),  # no percentage
        _sheet_row("Alfa Nove", "A", 50),  # an even contest: not with himself
        _sheet_row("Alfa Dieci", "A", 50),
    ]
    mates = [row.name for row in sheet if row.club == "alfa"]
    players = [KnownPlayer(player_id=n, name=name, club="alfa") for n, name in enumerate(mates, start=1)]
    rivals = {}
    for player in players:
        found = gold.availability(
            player,
            home="alfa",
            away="beta",
            views=[],
            outlet_views=sheet,
            officials=[],
            players=players,
            as_of=LATE,
        )
        assert found is not None
        rivals[player.name] = found.outlets[0].rivals
    assert rivals["Alfa Uno"] == ["Alfa Due"]
    assert rivals["Alfa Due"] == ["Alfa Uno"]
    assert rivals["Alfa Nove"] == ["Alfa Dieci"]
    assert rivals["Alfa Dieci"] == ["Alfa Nove"]
    contested = {"Alfa Uno", "Alfa Due", "Alfa Nove", "Alfa Dieci"}
    assert not [name for name, found in rivals.items() if found and name not in contested]
