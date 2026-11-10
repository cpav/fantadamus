"""AT-2 and AT-3 of mvp-cards: the match in numbers, by hand, and the season so far, shown and never used in a
number (design C2; R2)."""

from __future__ import annotations

import math

import pytest

from fantadamus.domains.cards import match_numbers
from fantadamus.domains.odds.gold import team_xg
from fantadamus.engine import odds
from tests.cards_data import ALFA, AT, BETA, odds_row, table_row

TABLE = {"alfa": ALFA, "beta": BETA}


def test_at2_the_numbers_by_hand() -> None:
    """One page with over/under: the chances are the fitted market's, each clean sheet is e^-xG of the other
    side's expected goals, and three goals or more and both teams to score come from the same fit."""
    xg = team_xg([odds_row(0.50, 0.27, 0.23, p_over=0.52)], [ALFA, BETA], home="alfa", away="beta", as_of=AT)
    assert xg is not None
    found = match_numbers(xg, "alfa", "beta", TABLE)
    market = odds.model(xg.home_xg, xg.away_xg)
    assert (found.home.club, found.away.club) == ("alfa", "beta")
    assert (found.home.p_win, found.p_draw, found.away.p_win) == (market.p_home, market.p_draw, market.p_away)
    assert found.home.p_win == pytest.approx(0.50, abs=0.01)  # the fit gives back what the page said
    assert (found.home.expected_goals, found.away.expected_goals) == (xg.home_xg, xg.away_xg)
    assert found.home.p_clean_sheet == pytest.approx(math.exp(-xg.away_xg))
    assert found.away.p_clean_sheet == pytest.approx(math.exp(-xg.home_xg))
    assert found.p_three_or_more == market.p_over
    assert found.p_three_or_more == pytest.approx(0.52, abs=0.01)
    assert found.p_both_score == market.p_btts
    assert (found.from_odds, found.spread) == (True, None)  # one page: nothing to be apart from


def test_at2_several_odds_pages() -> None:
    """Two pages four points apart on the home win: the card says so."""
    pages = [
        odds_row(0.50, 0.27, 0.23, p_over=0.52, url="https://example.org/one"),
        odds_row(0.46, 0.29, 0.25, p_over=0.50, url="https://example.org/two"),
    ]
    xg = team_xg(pages, [ALFA, BETA], home="alfa", away="beta", as_of=AT)
    assert xg is not None
    assert match_numbers(xg, "alfa", "beta", TABLE).spread == pytest.approx(0.04)


def test_at2_without_odds() -> None:
    """Team form gives the expected goals, and the chances only odds can price are left out."""
    xg = team_xg([], [ALFA, BETA], home="alfa", away="beta", as_of=AT)
    assert xg is not None
    found = match_numbers(xg, "alfa", "beta", TABLE)
    assert not found.from_odds
    assert (found.p_three_or_more, found.p_both_score, found.spread) == (None, None, None)
    assert found.home.p_clean_sheet == pytest.approx(math.exp(-xg.away_xg))
    without_totals = team_xg([odds_row(0.50, 0.27, 0.23)], [ALFA, BETA], home="alfa", away="beta", as_of=AT)
    assert without_totals is not None
    only_1x2 = match_numbers(without_totals, "alfa", "beta", TABLE)
    assert only_1x2.from_odds
    assert (only_1x2.p_three_or_more, only_1x2.p_both_score) == (None, None)  # 1X2 alone doesn't price goals


def test_at3_the_season_so_far() -> None:
    """Goals for and against per match, the record and the last five, from the table; a table without the
    record gives the goals only, and a club with no table row gives nothing."""
    xg = team_xg([odds_row(0.50, 0.27, 0.23, p_over=0.52)], [ALFA, BETA], home="alfa", away="beta", as_of=AT)
    assert xg is not None
    found = match_numbers(xg, "alfa", "beta", {"alfa": ALFA, "beta": table_row("beta", 9, 11, 13)})
    assert found.home.season is not None
    assert found.home.season.model_dump() == {
        "played": 9,
        "goals_for_per_match": pytest.approx(17 / 9),
        "goals_against_per_match": pytest.approx(8 / 9),
        "wins": 6,
        "draws": 2,
        "losses": 1,
        "form": "WWDLW",
    }
    assert found.away.season is not None
    assert (found.away.season.wins, found.away.season.form) == (None, None)
    assert match_numbers(xg, "alfa", "beta", {"alfa": ALFA}).away.season is None
    assert (
        match_numbers(xg, "alfa", "beta", {"alfa": table_row("alfa", 0, 0, 0)}).home.season is None
    )  # no match played yet
