"""mvp-collect task 5: the ranked source wins a fact with one true value, disagreements are listed, and every
published probability carries a confidence (design C12; R5.1 to R5.3)."""

from __future__ import annotations

import datetime as dt

from fantadamus.domains.availability.consensus import OfficialView, OutletView, combine, outlet_view
from fantadamus.domains.facts import Source
from fantadamus.domains.fixtures import gold as fixtures
from fantadamus.domains.fixtures.silver import FixtureRow
from fantadamus.domains.odds.gold import TeamXg
from fantadamus.domains.season import gold as season
from fantadamus.domains.season.silver import TeamSeasonRow
from fantadamus.domains.sources import Confidence, disagreement, of_odds, of_outlets, weaker

READ = dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.UTC)
FCIT = "https://www.fantacalcio.it/serie-a/calendario"
FCO = "https://www.fantacalcio-online.com/it/serie-a/2026-2027/probabili-formazioni/ultima-giornata"
WIKI = "https://it.wikipedia.org/wiki/Serie_A_2026-2027"
OTHER = "https://www.example.org/calendario"


def _source(url: str, hours: int = 0) -> Source:
    return Source(source_url=url, captured_at=READ + dt.timedelta(hours=hours), content_sha256=url[-1] * 64)


def _match(url: str, hours: int, kickoff: str) -> FixtureRow:
    return FixtureRow(
        **_source(url, hours).model_dump(),
        round=10,
        home="alfa",
        away="beta",
        kickoff_at=dt.datetime.fromisoformat(kickoff),
    )


def test_ranked_source_wins() -> None:
    rows = [
        _match(FCIT, 0, "2026-10-31T14:00:00+00:00"),
        _match(FCO, 5, "2026-10-31T14:30:00+00:00"),  # newer, but ranked below Fantacalcio.it
        _match(WIKI, 9, "2026-10-31T15:00:00+00:00"),
        _match(OTHER, 10, "2026-10-31T15:30:00+00:00"),
    ]
    later = READ + dt.timedelta(hours=12)
    [match] = fixtures.matches(rows, later)
    assert (match.source_url, match.kickoff_at) == (FCIT, dt.datetime(2026, 10, 31, 14, 0, tzinfo=dt.UTC))
    assert fixtures.matches(rows[1:], later)[0].source_url == FCO
    assert fixtures.matches(rows[2:], later)[0].source_url == WIKI
    assert fixtures.matches(rows, READ - dt.timedelta(hours=1)) == []  # nothing known yet
    moved = _match(FCIT, 11, "2026-10-31T19:45:00+00:00")  # the same source's newer read wins
    assert fixtures.matches([*rows, moved], later)[0].kickoff_at == moved.kickoff_at
    table = [
        TeamSeasonRow(**_source(WIKI, 3).model_dump(), club="alfa", played=9, goals_for=15, goals_against=9),
        TeamSeasonRow(**_source(FCIT, 0).model_dump(), club="alfa", played=8, goals_for=14, goals_against=9),
    ]
    alfa = season.team_season(table, "alfa", later)
    assert alfa is not None
    assert alfa.played == 8


def test_disagreements_listed() -> None:
    def kickoff(row: FixtureRow) -> str:
        return f"{row.kickoff_at:%H:%M}"

    rows = [
        _match(FCIT, 0, "2026-10-31T14:00:00+00:00"),
        _match(FCO, 2, "2026-10-31T13:00:00+00:00"),  # an older read from the same page
        _match(FCO, 5, "2026-10-31T14:30:00+00:00"),
    ]
    later = READ + dt.timedelta(hours=6)
    assert disagreement(rows, later, "Alfa v Beta kickoff", kickoff) == (
        "Alfa v Beta kickoff: Fantacalcio.it 14:00, Fantacalcio-Online 14:30"
    )
    assert disagreement(rows[:1], later, "Alfa v Beta kickoff", kickoff) is None
    agreeing = [rows[0], _match(WIKI, 5, "2026-10-31T14:00:00+00:00")]
    assert disagreement(agreeing, later, "Alfa v Beta kickoff", kickoff) is None
    assert disagreement(rows, READ + dt.timedelta(hours=3), "Alfa v Beta kickoff", kickoff) == (
        "Alfa v Beta kickoff: Fantacalcio.it 14:00, Fantacalcio-Online 13:00"
    )


def _xg(pages: int, spread: float, from_odds: bool = True) -> TeamXg:
    return TeamXg(
        home_xg=1.4,
        away_xg=1.1,
        p_home_win=0.45,
        p_draw=0.27,
        p_away_win=0.28,
        from_odds=from_odds,
        totals=True,
        sources=[_source(f"https://www.example.org/odds/{page}") for page in range(pages)],
        spread=spread,
    )


def test_confidence_labels() -> None:
    def outlets(*percents: float) -> list[OutletView]:
        return [
            outlet_view(f"Outlet {n}", "percentage", percent, _source(OTHER))
            for n, percent in enumerate(percents)
        ]

    disputed = of_outlets(combine(outlets(90, 90, 55, 90)))
    assert disputed == Confidence(sources=4, spread=0.35, label="disputed")
    assert of_outlets(combine(outlets(90, 85))).label == "agree"
    assert of_outlets(combine(outlets(90))) == Confidence(sources=1, spread=0.0, label="one source")
    official = combine(outlets(90, 55), OfficialView(status="starter", source=_source(FCO)))
    assert of_outlets(official) == Confidence(sources=1, spread=0.0, label="official")

    assert of_odds(_xg(pages=2, spread=0.04)) == Confidence(sources=2, spread=0.04, label="agree")
    assert of_odds(_xg(pages=2, spread=0.12)).label == "disputed"
    assert of_odds(_xg(pages=1, spread=0.0)).label == "one source"
    assert of_odds(_xg(pages=1, spread=0.0, from_odds=False)).label == "one source"  # team form stood in

    agree = Confidence(sources=3, spread=0.1, label="agree")
    assert weaker(agree, disputed) == disputed
    assert weaker(Confidence(sources=1, spread=0.0, label="official"), agree) == agree
    assert weaker(agree, Confidence(sources=1, spread=0.0, label="one source")).label == "one source"
