"""mvp-collect task 1.3: an outlet's own percentage is its view; each outlet counts once (design C5; R4)."""

from __future__ import annotations

import datetime as dt

import pytest

from fantadamus.domains.availability import gold
from fantadamus.domains.availability.consensus import combine, outlet_view
from fantadamus.domains.availability.silver import LineupViewRow, OutletViewRow
from fantadamus.domains.facts import Source
from fantadamus.domains.players.resolve import KnownPlayer

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
        NOVE, **match, views=[status_row], outlet_views=percent_rows, officials=[], players=[NOVE], as_of=LATE
    )
    assert found is not None
    assert [(view.outlet, view.status, view.p_start) for view in found.outlets] == [
        ("fantacalcio.it", "percentage", 0.62)
    ]
    earlier = gold.availability(
        NOVE,
        **match,
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
        **match,
        views=[],
        outlet_views=percent_rows,
        officials=[],
        players=[NOVE, quattordici],
        as_of=LATE,
    )
    assert out is not None
    assert (out.p_start, out.p_cameo) == (0.0, 0.0)
