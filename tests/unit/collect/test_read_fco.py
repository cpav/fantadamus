"""mvp-collect task 3.1: Fantacalcio-Online's round page read into facts (design C3; R3.1, R3.5, R4.2)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import replace

import pytest

from fantadamus.domains.facts import payload_hash
from fantadamus.web.readers import UnreadablePageError
from fantadamus.web.readers.fco import _updated_at, read_round
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


def test_fewer_than_three_goals_is_read_back() -> None:
    """The page names the likelier side: "meno di 3 55%" means a 45% chance of 3 or more goals."""
    facts = read_round(fco_round_page(FcoMatch("Alfa", "Beta", goals="meno di 3", over3="55%")), round=10)
    assert facts.odds[0].payload.over_2_5_percent == 45
    assert not facts.problems


def test_a_goals_line_that_does_not_read_is_named() -> None:
    """A new wording mustn't look like a page without the figure: the odds stay, and the problem is named."""
    facts = read_round(fco_round_page(FcoMatch("Alfa", "Beta", goals="2 o più")), round=10)
    assert facts.odds[0].payload.over_2_5_percent is None
    assert facts.odds[0].payload.home_win == 2.1
    assert facts.problems == ["Alfa v Beta: the goals line doesn't read"]


def test_page_average_skipped() -> None:
    facts = read_round(PAGE, round=10)
    assert sorted(view.outlet for view in facts.outlets) == sorted(
        OUTLETS * 2
    )  # four outlets per match, no average


def test_official_lineup_when_confirmed() -> None:
    [official] = read_round(PAGE, round=10).officials
    assert (official.home, official.away) == ("Gamma", "Delta")
    assert {"UNO G", "DUE G", "UNDICI G"} <= set(official.home_team.starters)
    assert "DODICI G" in official.home_team.bench
    assert len(official.away_team.starters) == 11


def _written(names: Iterable[str]) -> list[str]:
    """The names as the page writes them, sorted: `Alfa Dodici` is `DODICI A`."""
    return sorted(f"{name.split()[1].upper()} {name[0]}" for name in names)


ALFA, BETA = squad("Alfa"), squad("Beta")


def test_official_lineup_marks_in_either_table() -> None:
    """The page marks the real starters: here a probable starter is left out and a bench player comes in."""
    marked = (*ALFA[:10], ALFA[11], *BETA[:11])
    [official] = read_round(fco_round_page(FcoMatch("Alfa", "Beta", marked=marked)), round=10).officials
    assert official.home_team.starters == _written((*ALFA[:10], ALFA[11]))
    assert official.home_team.bench == _written((ALFA[10], ALFA[12]))  # the rest of both tables
    assert official.home_team.unnamed_starters == 0
    assert official.away_team.starters == _written(BETA[:11])


def test_ten_marks_leave_one_starter_unnamed() -> None:
    """Some teams have 10 marks, because the page doesn't list the eleventh starter."""
    marked = (*ALFA[:11], *BETA[:10])
    [official] = read_round(fco_round_page(FcoMatch("Alfa", "Beta", marked=marked)), round=10).officials
    assert official.home_team.unnamed_starters == 0
    assert official.away_team.starters == _written(BETA[:10])
    assert official.away_team.unnamed_starters == 1


@pytest.mark.parametrize("marked", [(*ALFA[:11], *BETA[:9]), tuple(ALFA[:11]), ()])
def test_no_official_lineup_until_both_teams_have_theirs(marked: tuple[str, ...]) -> None:
    facts = read_round(fco_round_page(FcoMatch("Alfa", "Beta", marked=marked)), round=10)
    assert facts.officials == []
    assert facts.problems == []  # not a fault: it's just not out yet


def test_too_many_marks_are_named_as_a_problem() -> None:
    marked = (*ALFA[:12], *BETA[:11])
    facts = read_round(fco_round_page(FcoMatch("Alfa", "Beta", marked=marked)), round=10)
    assert facts.officials == []
    assert facts.problems == ["Alfa v Beta, official lineup: Value error, needs 11 starters, got 12"]


def test_dash_means_not_listed() -> None:
    dashes = dict.fromkeys(squad("Alfa")[:2], (90, None, 90, 90))  # Gazzetta doesn't list two starters
    facts = read_round(fco_round_page(FcoMatch("Alfa", "Beta", percents=dashes)), round=10)
    gazzetta = next(view for view in facts.outlets if view.outlet == "Gazzetta")
    names = {player.name for player in gazzetta.home_team.players}
    assert {"UNO A", "DUE A"}.isdisjoint(names)
    assert "TRE A" in names
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


def test_lineups_not_published_yet() -> None:
    """Early in the week the round page lists the matches before their lineups and odds: the fixtures still
    count, and a match without lineups is simply left out of the outlet views (found on the live page)."""
    early = FcoMatch("Alfa", "Beta", odds=None, lineups=False)
    facts = read_round(fco_round_page(early, FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00")))
    assert [(match.home, match.away) for match in facts.fixtures.matches] == [
        ("Alfa", "Beta"),
        ("Gamma", "Delta"),
    ]
    assert {(view.home, view.away) for view in facts.outlets} == {("Gamma", "Delta")}
    assert [odds.payload.home for odds in facts.odds] == ["Gamma"]
    assert facts.problems == []


def test_order_on_the_page_does_not_matter() -> None:
    """Found in the real round: the page lists matches that kick off together in either order from one load to
    the next. The same facts in another order must read the same, or each read would store them again."""
    alfa, gamma = FcoMatch("Alfa", "Beta"), FcoMatch("Gamma", "Delta", confirmed=True)  # same kickoff
    first = read_round(fco_round_page(alfa, gamma))
    shuffled = read_round(fco_round_page(replace(gamma, reversed=True), replace(alfa, reversed=True)))
    assert first.fixtures == shuffled.fixtures
    assert sorted(map(payload_hash, first.outlets)) == sorted(map(payload_hash, shuffled.outlets))
    assert list(map(payload_hash, first.officials)) == list(map(payload_hash, shuffled.officials))


def test_outlet_not_published_yet() -> None:
    """Found on the live page (2026-11-03): an outlet that hasn't published shows a note in its column's title
    and dashes in every cell. Its column still counts as that outlet, and it gives no view of the match."""
    facts = read_round(fco_round_page(FcoMatch("Alfa", "Beta", pending=("Sky",)), FcoMatch("Gamma", "Delta")))
    alfa = sorted(view.outlet for view in facts.outlets if view.home == "Alfa")
    assert alfa == ["Fantacalcio.it", "Gazzetta", "SOS Fanta"]
    assert len([view for view in facts.outlets if view.home == "Gamma"]) == 4
    assert facts.problems == []


def test_a_match_the_contract_refuses_is_an_unreadable_page() -> None:
    """Found by the code review: a club playing itself isn't a crash, it's a page that doesn't read."""
    with pytest.raises(UnreadablePageError, match="plays itself"):
        read_round(fco_round_page(FcoMatch("Alfa", "Alfa")))


def test_odds_updated_after_kickoff_keep_their_year() -> None:
    """A finished round's page can show odds updated once the match began."""
    kickoff = dt.datetime(2026, 11, 8, 19, 45, tzinfo=dt.UTC)
    assert _updated_at("quote aggiornate il 8 novembre alle 22:00", kickoff) == dt.datetime(
        2026, 11, 8, 21, 0, tzinfo=dt.UTC
    )
    january = dt.datetime(2027, 1, 3, 19, 45, tzinfo=dt.UTC)
    assert _updated_at("quote aggiornate il 30 dicembre alle 18:00", january) == dt.datetime(
        2026, 12, 30, 17, 0, tzinfo=dt.UTC
    )
