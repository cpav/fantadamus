"""AT-7: the market's match-level chances scored beside the players' in a round's report, by hand; old reports
still read (mvp-recalibrate R7.1; design C7)."""

from __future__ import annotations

import datetime as dt

import pytest

from fantadamus.domains.calibration import (
    AWAY_WIN,
    BOTH_SCORE,
    DRAW,
    HOME_WIN,
    SIDE_CLEAN_SHEET,
    THREE_OR_MORE,
    RoundReport,
    Scored,
    SetReport,
    Tally,
    add_market,
    render,
)
from fantadamus.domains.cards import MatchNumbers, match_numbers
from fantadamus.domains.odds.gold import team_xg
from tests.cards_data import AT, odds_row, table_row


def _numbers(*, p_over: float | None = 0.55, odds: bool = True) -> MatchNumbers:
    """Alfa v Beta as the card prices it: from one page's odds or, without them, from the table."""
    rows = [odds_row(0.5, 0.27, 0.23, p_over=p_over)] if odds else []
    table = [table_row("alfa", 9, 17, 8), table_row("beta", 9, 11, 13)]
    xg = team_xg(rows, table, home="alfa", away="beta", as_of=AT)
    assert xg is not None
    return match_numbers(xg, "alfa", "beta", {})


def _brier(pairs: list[tuple[float, bool]]) -> float:
    return sum((chance - happened) ** 2 for chance, happened in pairs) / len(pairs)


def _check(scored: Scored, pairs: list[tuple[float, bool]]) -> None:
    assert scored.count == len(pairs)
    assert scored.brier == pytest.approx(_brier(pairs))
    assert sum(bucket.happened * bucket.count for bucket in scored.buckets) == pytest.approx(
        sum(happened for _, happened in pairs)
    )


def test_at7_the_market_set_by_hand() -> None:
    """2-1, 1-0, 0-0, 0-1, 1-2 and 1-1 at the odds' chances; the 1-1's odds didn't price the goals; a match
    without odds, one priced from the table instead, and one whose score isn't known are named, not scored."""
    priced, unpriced = _numbers(), _numbers(p_over=None)
    assert unpriced.p_three_or_more is None
    tally = Tally()
    add_market(tally, priced, (2, 1))
    add_market(tally, priced, (1, 0))
    add_market(tally, priced, (0, 0))
    add_market(tally, priced, (0, 1))
    add_market(tally, priced, (1, 2))
    add_market(tally, unpriced, (1, 1))
    add_market(tally, None, (3, 0))
    add_market(tally, _numbers(odds=False), (1, 0))  # team form isn't the market
    add_market(tally, priced, "its keepers' goals against aren't known")
    report = tally.report()
    scored = {chance.chance: chance for chance in report.scored}
    games = [(priced, 2, 1), (priced, 1, 0), (priced, 0, 0), (priced, 0, 1), (priced, 1, 2), (unpriced, 1, 1)]
    _check(scored[HOME_WIN], [(numbers.home.p_win, home > away) for numbers, home, away in games])
    _check(scored[DRAW], [(numbers.p_draw, home == away) for numbers, home, away in games])
    _check(scored[AWAY_WIN], [(numbers.away.p_win, away > home) for numbers, home, away in games])
    _check(
        scored[SIDE_CLEAN_SHEET],
        [
            pair
            for numbers, home, away in games
            for pair in ((numbers.home.p_clean_sheet, away == 0), (numbers.away.p_clean_sheet, home == 0))
        ],
    )
    over, both = priced.p_three_or_more, priced.p_both_score
    assert over is not None
    assert both is not None
    _check(scored[THREE_OR_MORE], [(over, happened) for happened in (True, False, False, False, True)])
    _check(scored[BOTH_SCORE], [(both, happened) for happened in (True, False, False, False, True)])
    assert list(scored) == [HOME_WIN, DRAW, AWAY_WIN, SIDE_CLEAN_SHEET, THREE_OR_MORE, BOTH_SCORE]
    assert {entry.reason: entry.count for entry in report.unscored} == {
        "The match: no odds held before its kickoff": 2,
        "The match: its keepers' goals against aren't known": 1,
        "The goals: the odds didn't price them": 1,
    }


def test_at7_old_reports_still_read() -> None:
    empty = SetReport(scored=[], unscored=[])
    report = RoundReport(
        round=10, scored_at=dt.datetime(2026, 11, 1, 5, tzinfo=dt.UTC), told=empty, model=empty
    )
    older = report.model_dump(mode="json")
    del older["market"]
    again = RoundReport.model_validate(older)
    assert again.market is None
    assert "The market on every match" not in render(again)

    tally = Tally()
    add_market(tally, _numbers(), (2, 1))
    shown = render(report.model_copy(update={"market": tally.report()}))
    assert "The market on every match" in shown.splitlines()
    assert f"  {HOME_WIN}: Brier" in shown
