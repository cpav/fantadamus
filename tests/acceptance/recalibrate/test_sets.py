"""AT-1: a round's calibration set is kept with its report, rebuilt the same way, and counts what the report
counts, a substitute's rating included (mvp-recalibrate R1.1 to R1.3)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from fantadamus.domains.calibration import (
    CLEAN_SHEET,
    RATING,
    SCORING,
    STARTING,
    CalibrationSet,
    Pair,
    RoundReport,
    SetRow,
)
from fantadamus.web.fetch import Response
from tests.collect_harness import HTML, ROUND_ROUTE, STATS_ROUTE
from tests.collect_pages import FcoMatch, fco_round_page, stats_page
from tests.lineup_harness import MATCHES, Round, a_round, player_id, rows, stats_after, the_next_round
from tests.roles_data import stats_row
from tests.xy_harness import WORDS

pytestmark = pytest.mark.anyio

ROUND_10 = "/probabili-formazioni/10-giornata"
AFTER = dt.datetime(2026, 11, 1, 5, 0, tzinfo=dt.UTC)  # 12 hours after the round's last kickoff
STARTER = (0.9 + 0.9 + 0.95 + 0.9) / 4  # the outlets' default for a listed starter
BENCH = (0.1 + 0.3 + 0.05 + 0.3) / 4  # and for a listed bench player


def _finished(matches: Sequence[FcoMatch] = MATCHES) -> str:
    return fco_round_page(
        *(FcoMatch(match.home, match.away, kickoff=match.kickoff, confirmed=True) for match in matches)
    )


async def _scored(
    here: Round, *, stats: str | None = None, matches: Sequence[FcoMatch] = MATCHES
) -> RoundReport:
    """Round 10 asked about, played, and scored at the next question."""
    await here.ask()
    here.routes[f"{here.base}{ROUND_10}"] = Response(200, HTML, _finished(matches).encode())
    here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, the_next_round().encode())
    here.routes[f"{here.base}{STATS_ROUTE}"] = Response(200, HTML, (stats or stats_after()).encode())
    here.clock.now = AFTER
    await here.ask()
    report = here.scores.get(10)
    assert report is not None
    return report


def _kept(here: Round) -> CalibrationSet:
    kept = here.scores.calibration_set(10)
    assert kept is not None
    return kept


def _row(kept: CalibrationSet, club: str, word: str) -> SetRow:
    return next(row for row in kept.rows if row.player_id == player_id(club, word))


def _pairs(rows: Sequence[SetRow], chance: str) -> list[Pair]:
    """What the report scores, from the set alone: scoring and a clean sheet count only for a starter."""
    found: list[Pair] = []
    for row in rows:
        given, happened = {
            STARTING: (row.p_start, row.outcome.started),
            RATING: (row.p_rating, row.outcome.rated),
            SCORING: (row.p_scores, row.outcome.scored),
            CLEAN_SHEET: (row.p_clean_sheet, row.outcome.clean_sheet),
        }[chance]
        if chance in {SCORING, CLEAN_SHEET} and row.outcome.started is not True:
            continue
        if given is not None and isinstance(happened, bool):
            found.append((given, happened))
    return found


async def test_at1_kept_with_the_report(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        report = await _scored(here)
        kept = _kept(here)
        assert (here.scores.root / "round-10.set.json").is_file()
        assert here.scores.latest() == report  # the set beside it isn't a round's report
    assert kept.round == 10
    assert kept.scored_at == report.scored_at
    assert len(kept.rows) == 56  # every player the page lists, as the report scores them

    starter, bench = _row(kept, "Alfa", "Nove"), _row(kept, "Alfa", "Dodici")
    assert (starter.home, starter.away, starter.club, starter.role) == (
        "alfa",
        "beta",
        "alfa",
        "A",
    )  # clubs by their keys, as stored
    assert starter.consensus == pytest.approx(STARTER)  # the outlets' own, before any map
    assert starter.p_start == pytest.approx(STARTER)  # no map yet: the same
    assert bench.consensus == pytest.approx(BENCH)
    assert starter.p_rating is not None
    assert starter.p_rating > starter.p_start  # a cameo gets a rating too
    assert starter.p_scores is not None
    assert starter.p_scores_cameo is not None
    assert starter.p_clean_sheet is None
    keeper = _row(kept, "Alfa", "Uno")
    assert keeper.role == "P"
    assert keeper.p_clean_sheet is not None
    assert keeper.p_scores is None
    assert (starter.outcome.started, starter.outcome.scored) == (True, True)  # Alfa Nove scored
    assert keeper.outcome.clean_sheet is False  # and Alfa's keeper conceded


async def test_at1_rebuilt_the_same(tmp_path: Path) -> None:
    """`--again` rebuilds the set from the same facts, and a lake that stored the facts in another order keeps
    the same set."""
    async with a_round(tmp_path / "first") as here:
        await _scored(here)
        first = _kept(here)
        here.clock.now += dt.timedelta(minutes=16)
        again = here.calibrator.report(10, again=True)
        assert again is not None
        rebuilt = _kept(here)
    assert rebuilt.scored_at > first.scored_at
    assert rebuilt.rows == first.rows

    other = tuple(reversed(MATCHES))  # both pages list the matches the other way round
    async with a_round(tmp_path / "other", matches=other) as here:
        await _scored(here, matches=other)
        reordered = _kept(here)
    assert reordered.rows == first.rows


async def test_at1_the_counts_match_the_report(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        report = await _scored(here)
        kept = _kept(here)
    for scored in report.model.scored:
        pairs = _pairs(kept.rows, scored.chance)
        assert len(pairs) == scored.count, scored.chance
        assert sum(happened for _, happened in pairs) == pytest.approx(
            sum(bucket.happened * bucket.count for bucket in scored.buckets)
        )
        assert sum(chance for chance, _ in pairs) == pytest.approx(
            sum(bucket.said * bucket.count for bucket in scored.buckets)
        )
    assert {scored.chance for scored in report.model.scored} == {STARTING, RATING, SCORING, CLEAN_SHEET}


async def test_at1_rated_without_starting(tmp_path: Path) -> None:
    """A substitute who got a rating is one who didn't start and has a rated game more. One who came on
    without a rating can't be told from one who didn't come on: the page counts rated games only."""
    changed: dict[str, dict[str, Any]] = {
        f"{club}_{word}": {"rated_appearances": 9}
        for club in ("Alfa", "Beta", "Gamma", "Delta")
        for word in WORDS[:11]
    }
    base = stats_row("Alfa", "C", "C", player_id("Alfa", "Dodici"))["rated_appearances"]
    changed["Alfa_Dodici"] = {"rated_appearances": base + 1}
    async with a_round(tmp_path) as here:
        await _scored(here, stats=stats_page(rows(**changed)))
        kept = _kept(here)
    came_on, sat = _row(kept, "Alfa", "Dodici"), _row(kept, "Alfa", "Tredici")
    assert (came_on.outcome.started, came_on.outcome.rated) == (False, True)
    assert (sat.outcome.started, sat.outcome.rated) == (False, False)
    assert came_on.p_rating is not None
    assert 0 < came_on.p_rating < 1
    out = _row(kept, "Alfa", "Quattordici")  # the page lists him as out
    assert (out.outcome.started, out.outcome.rated) == (False, False)


async def test_at1_starting_from_the_page_alone(tmp_path: Path) -> None:
    """With nothing held before kickoff, the report scores the page's own chances of starting, and the set
    keeps them: the rest isn't known."""
    async with a_round(tmp_path) as here:
        here.routes[f"{here.base}{ROUND_10}"] = Response(200, HTML, _finished().encode())
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, _finished().encode())
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(200, HTML, stats_after().encode())
        here.clock.now = AFTER
        await here.ask()
        kept = _kept(here)
    assert len(kept.rows) == 56
    row = _row(kept, "Alfa", "Nove")
    assert row.consensus == pytest.approx(STARTER)
    assert row.p_start == row.consensus
    assert (row.role, row.p_rating, row.p_scores, row.p_scores_cameo, row.p_clean_sheet) == (None,) * 5
    assert row.outcome.started is True
