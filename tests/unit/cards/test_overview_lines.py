"""mvp-cards task 6.1: a round overview's line, by hand, from the same numbers as the match's card (design C6;
R5.1)."""

from __future__ import annotations

from fantadamus.domains.cards import match_numbers, round_lines
from fantadamus.domains.fixtures.silver import FixtureRow
from fantadamus.domains.odds.gold import TeamXg, team_xg
from fantadamus.engine import odds
from tests.cards_data import ALFA, AT, BETA, KICKOFF, odds_row, source

NAMES = {"alfa": "Alfa", "beta": "Beta"}
MATCH = FixtureRow(**source().model_dump(), round=12, home="alfa", away="beta", kickoff_at=KICKOFF)


def _xg(home: float, away: float) -> TeamXg:
    market = odds.model(home, away)
    return TeamXg(
        home_xg=home,
        away_xg=away,
        p_home_win=market.p_home,
        p_draw=market.p_draw,
        p_away_win=market.p_away,
        from_odds=True,
        totals=True,
        sources=[source()],
    )


def test_a_line_by_hand() -> None:
    """The favourite and its chance, the draw, both sides' goals and clean sheets and three goals or more: the
    card's numbers for the match, nothing else."""
    xg = team_xg([odds_row(0.50, 0.27, 0.23, p_over=0.52)], [ALFA, BETA], home="alfa", away="beta", as_of=AT)
    assert xg is not None
    numbers = match_numbers(xg, "alfa", "beta", {})
    (line,) = round_lines([(MATCH, xg)], NAMES)
    assert line.model_dump() == {
        "home": "Alfa",
        "away": "Beta",
        "kickoff": KICKOFF,
        "favourite": "Alfa",
        "p_favourite": numbers.home.p_win,
        "p_draw": numbers.p_draw,
        "home_goals": numbers.home.expected_goals,
        "away_goals": numbers.away.expected_goals,
        "home_clean_sheet": numbers.home.p_clean_sheet,
        "away_clean_sheet": numbers.away.p_clean_sheet,
        "p_three_or_more": numbers.p_three_or_more,
        "from_odds": True,
    }


def test_the_away_side_and_an_even_match() -> None:
    """The away side favoured names it; an even match names no favourite."""
    (away,) = round_lines([(MATCH, _xg(0.9, 1.8))], NAMES)
    assert (away.favourite, away.p_favourite) == ("Beta", odds.model(0.9, 1.8).p_away)
    (even,) = round_lines([(MATCH, _xg(1.3, 1.3))], NAMES)
    assert even.favourite is None
    assert even.p_favourite == odds.model(1.3, 1.3).p_home


def test_a_fixture_without_numbers() -> None:
    """Neither odds nor a table: only its kickoff."""
    (line,) = round_lines([(MATCH, None)], NAMES)
    assert (line.home, line.away, line.kickoff, line.favourite, line.home_goals) == (
        "Alfa",
        "Beta",
        KICKOFF,
        None,
        None,
    )
    assert not line.from_odds
