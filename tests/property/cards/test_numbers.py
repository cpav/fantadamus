"""P1 and P3 of mvp-cards: a match's chances add up, and the table's record and form never move a number
(design C2; R2.1, R2.2, R2.4)."""

from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.cards import match_numbers
from fantadamus.domains.odds.gold import TeamXg, team_xg
from fantadamus.engine import odds
from fantadamus.engine.constants import XG_RANGE
from tests.cards_data import AT, odds_row, source, table_row

GOALS = st.floats(min_value=XG_RANGE[0], max_value=XG_RANGE[1], allow_nan=False)


def _xg(home: float, away: float, *, from_odds: bool, totals: bool) -> TeamXg:
    market = odds.model(home, away)
    return TeamXg(
        home_xg=home,
        away_xg=away,
        p_home_win=market.p_home,
        p_draw=market.p_draw,
        p_away_win=market.p_away,
        from_odds=from_odds,
        totals=totals,
        sources=[source()],
    )


@given(GOALS, GOALS, st.booleans(), st.booleans())
def test_p1_chances_add_up(home: float, away: float, from_odds: bool, totals: bool) -> None:
    found = match_numbers(_xg(home, away, from_odds=from_odds, totals=totals), "alfa", "beta", {})
    chances = [found.home.p_win, found.p_draw, found.away.p_win]
    assert math.fsum(chances) == pytest.approx(1.0)
    assert found.home.p_clean_sheet == math.exp(-away)
    assert found.away.p_clean_sheet == math.exp(-home)
    for chance in [*chances, found.home.p_clean_sheet, found.away.p_clean_sheet]:
        assert 0 <= chance <= 1
    for goals in (found.p_three_or_more, found.p_both_score):
        assert goals is None or 0 <= goals <= 1


RECORDS = st.integers(min_value=0, max_value=9).flatmap(
    lambda wins: st.integers(min_value=0, max_value=9 - wins).map(
        lambda draws: (wins, draws, 9 - wins - draws)
    )
)


@given(RECORDS, RECORDS, st.text(alphabet="WDL", max_size=5), st.booleans())
def test_p3_the_record_moves_no_number(
    home: tuple[int, int, int], away: tuple[int, int, int], form: str, with_odds: bool
) -> None:
    """Whatever the record and form, with odds or with team form standing in, every chance and expected goal
    is the same as without them."""
    plain = [table_row("alfa", 9, 17, 8), table_row("beta", 9, 11, 13)]
    recorded = [
        table_row("alfa", 9, 17, 8, wins=home[0], draws=home[1], losses=home[2], form=form),
        table_row("beta", 9, 11, 13, wins=away[0], draws=away[1], losses=away[2], form=form),
    ]
    pages = [odds_row(0.50, 0.27, 0.23, p_over=0.52)] if with_odds else []
    before = team_xg(pages, plain, home="alfa", away="beta", as_of=AT)
    after = team_xg(pages, recorded, home="alfa", away="beta", as_of=AT)
    assert before is not None
    assert after is not None
    numbers = match_numbers(before, "alfa", "beta", {row.club: row for row in plain})
    again = match_numbers(after, "alfa", "beta", {row.club: row for row in recorded})
    assert numbers.model_dump(exclude={"home": {"season"}, "away": {"season"}}) == again.model_dump(
        exclude={"home": {"season"}, "away": {"season"}}
    )
