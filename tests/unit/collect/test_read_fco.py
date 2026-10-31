"""mvp-collect task 3.1: Fantacalcio-Online's round page read into facts (design C3; R3.1, R3.5, R4.2)."""

from __future__ import annotations

import datetime as dt

import pytest

from fantadamus.web.readers import UnreadablePageError
from fantadamus.web.readers.fco import read_round
from tests.collect_pages import OUTLETS, FcoMatch, fco_round_page, squad

PAGE = fco_round_page(
    FcoMatch("Alfa", "Beta", percents={"Alfa Nove": (90, 90, 55, 90)}),
    FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00", confirmed=True),
)


def test_round_page_facts() -> None:
    facts = read_round(PAGE, round=10)
    assert facts.fixtures.round == 10
    assert [(m.home, m.away, m.kickoff_at) for m in facts.fixtures.matches] == [
        ("Alfa", "Beta", dt.datetime(2026, 10, 31, 14, 0, tzinfo=dt.UTC)),
        ("Gamma", "Delta", dt.datetime(2026, 10, 31, 17, 0, tzinfo=dt.UTC)),
    ]
    first = facts.odds[0]
    odds = first.payload
    assert (odds.home, odds.bookmaker, odds.home_win, odds.draw, odds.away_win) == (
        "Alfa",
        "Fantacalcio-Online",
        2.1,
        3.3,
        3.6,
    )
    assert (odds.over_2_5, odds.over_2_5_percent) == (None, 53)
    assert first.published_at == dt.datetime(2026, 10, 30, 17, 13, tzinfo=dt.UTC)
    by_outlet = {view.outlet: view for view in facts.outlets if view.home == "Alfa"}
    nove = {
        name: next(p.percent for p in view.home_team.players if p.name == "NOVE A")
        for name, view in by_outlet.items()
    }
    assert nove == {"Fantacalcio.it": 90, "Gazzetta": 90, "SOS Fanta": 55, "Sky": 90}
    gazzetta = by_outlet["Gazzetta"]
    assert len(gazzetta.home_team.players) == 13
    assert {p.role for p in gazzetta.home_team.players} == {"A"}
    assert gazzetta.home_team.unavailable == ["QUATTORDICI A"]
    assert gazzetta.away_team.unavailable == ["QUATTORDICI B"]


def test_page_average_skipped() -> None:
    facts = read_round(PAGE, round=10)
    assert sorted(view.outlet for view in facts.outlets) == sorted(
        OUTLETS * 2
    )  # four outlets per match, no average


def test_official_lineup_when_confirmed() -> None:
    [official] = read_round(PAGE, round=10).officials
    assert (official.home, official.away) == ("Gamma", "Delta")
    assert official.home_team.starters[:2] == ["UNO G", "DUE G"]
    assert len(official.away_team.starters) == 11


def test_dash_means_not_listed() -> None:
    dashes = dict.fromkeys(squad("Alfa")[:2], (90, None, 90, 90))  # Gazzetta doesn't list two starters
    facts = read_round(fco_round_page(FcoMatch("Alfa", "Beta", percents=dashes)), round=10)
    gazzetta = next(view for view in facts.outlets if view.outlet == "Gazzetta")
    assert [player.name for player in gazzetta.home_team.players][:2] == ["TRE A", "QUATTRO A"]
    assert len(gazzetta.home_team.players) == 11
    assert facts.problems == []


def test_outlet_short_of_eleven_left_out() -> None:
    dashes = dict.fromkeys(squad("Alfa")[:3], (90, None, 90, 90))
    facts = read_round(fco_round_page(FcoMatch("Alfa", "Beta", percents=dashes)), round=10)
    assert sorted(view.outlet for view in facts.outlets) == ["Fantacalcio.it", "SOS Fanta", "Sky"]
    assert facts.problems == ["Alfa v Beta, Gazzetta: Value error, needs at least 11 players, got 10"]


def test_no_odds_yet() -> None:
    page = fco_round_page(FcoMatch("Alfa", "Beta", odds=None), FcoMatch("Gamma", "Delta"))
    facts = read_round(page, round=10)
    assert [(odds.payload.home, odds.payload.away) for odds in facts.odds] == [("Gamma", "Delta")]
    assert len(facts.outlets) == 8  # the lineups still count


def test_round_from_the_page() -> None:
    assert read_round(fco_round_page(FcoMatch("Alfa", "Beta"), round=11)).fixtures.round == 11
    with pytest.raises(UnreadablePageError, match="round"):
        read_round(fco_round_page(FcoMatch("Alfa", "Beta"), round=None))
