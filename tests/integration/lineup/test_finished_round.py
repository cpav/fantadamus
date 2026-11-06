"""mvp-lineup task 7.1: the finished round's page, read once, as its own page kind (design C10; R7.2)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.domains.freshness import FACTS_WINDOW
from fantadamus.lake.calibration_store import CalibrationStore
from fantadamus.web.fetch import Response
from tests.collect_harness import HTML, ROUND_ROUTE, STATS_ROUTE
from tests.collect_pages import FcoMatch, fco_round_page
from tests.lineup_harness import Round, a_round, stats_after, the_next_round
from tests.xy_harness import NOW
from tests.xy_harness import ask as compare

pytestmark = pytest.mark.anyio

ROUND_10 = "/probabili-formazioni/10-giornata"
AFTER = dt.datetime(
    2026, 11, 1, 5, 0, tzinfo=dt.UTC
)  # 12 hours after Gamma v Delta, 17:00 UTC, the round's last match


def _marks() -> tuple[FcoMatch, FcoMatch]:
    return (
        FcoMatch("Alfa", "Beta", confirmed=True),
        FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00", confirmed=True),
    )


async def _played(here: Round, *, finished_page: bool = True) -> None:
    """The round has been played: the current page shows the next round, and the statistics have moved on."""
    await here.ask()
    if finished_page:
        here.routes[f"{here.base}{ROUND_10}"] = Response(200, HTML, fco_round_page(*_marks()).encode())
    here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, the_next_round().encode())
    here.routes[f"{here.base}{STATS_ROUTE}"] = Response(200, HTML, stats_after().encode())
    here.clock.now = AFTER


def _reads(here: Round, route: str) -> int:
    return [url for url, _, _ in here.web.calls].count(f"{here.base}{route}")


async def test_read_once(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await _played(here)
        await here.ask()
        here.clock.now = AFTER + dt.timedelta(hours=1)
        await here.ask()
    assert _reads(here, ROUND_10) == 1


async def test_nothing_is_read_before_the_round_has_finished(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await _played(here)
        here.clock.now = AFTER - dt.timedelta(minutes=1)
        await here.ask()
    assert _reads(here, ROUND_10) == 0


async def test_current_round_reads_not_delayed(tmp_path: Path) -> None:
    """Its reads are logged as a kind of their own, so they don't count as attempts at the current round's
    page."""
    async with a_round(tmp_path) as here:
        await _played(here)
        current_before = _reads(here, ROUND_ROUTE)
        await here.ask()
    assert _reads(here, ROUND_10) == 1
    assert _reads(here, ROUND_ROUTE) == current_before + 1  # the answer still read the next round's page
    [finished] = [
        page for run in here.collect_log.runs() for page in run.pages if page.page == "finished_round"
    ]
    assert finished.url.endswith(ROUND_10)
    assert here.collect_log.last_attempt(AFTER, "finished_round") == AFTER


async def test_failed_read_tried_again(tmp_path: Path) -> None:
    """A page that can't be read doesn't stop the answer, and it's tried again, no more often than every 15
    minutes."""
    async with a_round(tmp_path) as here:
        await _played(here, finished_page=False)
        first = await here.ask()
        assert first["status"] == "lineup", first
        assert _reads(here, ROUND_10) == 1
        assert here.scores.get(10) is None

        here.clock.now = AFTER + dt.timedelta(minutes=5)
        await here.ask()
        assert _reads(here, ROUND_10) == 1  # too soon

        here.routes[f"{here.base}{ROUND_10}"] = Response(200, HTML, fco_round_page(*_marks()).encode())
        here.clock.now = AFTER + dt.timedelta(minutes=16)
        await here.ask()
        assert _reads(here, ROUND_10) == 2
        assert here.scores.get(10) is not None


async def test_skipped_in_the_last_hour_before_a_deadline(tmp_path: Path) -> None:
    """Speed matters most then, and it can wait for the next run."""
    async with a_round(tmp_path) as here:
        await _played(here)
        here.clock.now = dt.datetime(2026, 11, 7, 13, 30, tzinfo=dt.UTC)  # the next round starts at 14:00 UTC
        await here.ask()  # its own read of the current page is what shows that
        assert _reads(here, ROUND_10) == 0
        assert here.scores.get(10) is None


async def test_a_failure_never_stops_the_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(*_: object) -> None:
        raise OSError("disk full")

    async with a_round(tmp_path) as here:
        await _played(here)
        monkeypatch.setattr(CalibrationStore, "set", broken)
        result = await here.ask()
        monkeypatch.undo()
        assert result["status"] == "lineup", result
        assert result["lineup"]["last_round"] is None
        assert "Couldn't score a finished round" in caplog.text

        here.clock.now += dt.timedelta(minutes=16)
        again = await here.ask()
    assert "Round 10's forecasts" in again["lineup"]["last_round"]


async def test_the_answer_is_the_same_either_way(tmp_path: Path) -> None:
    """Scoring reads a finished round's page into the lake: that can't change an answer about the next one."""
    async with a_round(tmp_path / "scored") as here:
        await _played(here)
        scored = (await here.ask())["lineup"]
    assert "Round 10's forecasts" in scored.pop("last_round")
    async with a_round(tmp_path / "not") as here:
        await _played(here, finished_page=False)
        plain = (await here.ask())["lineup"]
    assert plain.pop("last_round") is None
    assert scored == plain


async def test_a_comparison_scores_it_too(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await _played(here)
        assert here.scores.get(10) is None
        await compare(here.client)
        assert here.scores.get(10) is not None
    assert _reads(here, ROUND_10) == 1


async def test_a_replay_scores_nothing(tmp_path: Path) -> None:
    """A question about an earlier moment reads nothing, whatever kind it is."""
    async with a_round(tmp_path) as here:
        await _played(here)
        await here.ask(as_of=AFTER.isoformat())
        await compare(here.client, as_of=AFTER.isoformat())
        assert here.scores.get(10) is None
    assert _reads(here, ROUND_10) == 0


async def test_both_kinds_of_answer_log_the_chance_of_a_rating(tmp_path: Path) -> None:
    """The chance of coming on and the chance of a rating differ (R8.3): calibration needs the second."""
    async with a_round(tmp_path) as here:
        await here.ask()
        await compare(here.client)
        decisions = here.log.read()
    assert {decision.kind for decision in decisions} == {"lineup", "compare"}
    for decision in decisions:
        for player in decision.players:
            assert player.p_rating == pytest.approx(player.p_start + player.p_cameo)


async def test_a_page_updated_before_the_mark_still_counts(tmp_path: Path) -> None:
    """The statistics page can update inside the 12 hours. A read after them finds it unchanged and stores
    nothing, and it shows what the last read stored: that's the read after the round."""
    async with a_round(tmp_path) as here:
        await _played(here)
        here.clock.now = AFTER - dt.timedelta(hours=1)
        await here.ask()
        assert here.scores.get(10) is None

        # The round's page saying nothing about the statistics, and a read that failed, aren't that read.
        await here.client.call_tool("collect", {"fact": "probable_lineups"})
        here.clock.now = AFTER + dt.timedelta(minutes=30)
        await here.client.call_tool("collect", {"fact": "probable_lineups"})
        await here.ask()
        assert here.scores.get(10) is None
        stats = here.routes[f"{here.base}{STATS_ROUTE}"]
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(500, {}, b"")
        here.clock.now = AFTER + dt.timedelta(hours=24)
        await here.ask()
        assert here.scores.get(10) is None

        here.routes[f"{here.base}{STATS_ROUTE}"] = stats
        here.clock.now = AFTER + dt.timedelta(hours=49)
        await here.ask()
        report = here.scores.get(10)
    assert report is not None
    rated = next(chance for chance in report.model.scored if chance.chance == "Getting a rating")
    assert rated.count == 56
    assert sum(bucket.happened * bucket.count for bucket in rated.buckets) == pytest.approx(44, abs=0.01)


async def test_a_page_that_hasnt_moved_isnt_the_read_after(tmp_path: Path) -> None:
    """If the page still shows the figures from before the round, it hasn't updated yet: this waits, rather
    than saying nobody got a rating."""
    async with a_round(tmp_path) as here:
        await here.ask()
        here.routes[f"{here.base}{ROUND_10}"] = Response(200, HTML, fco_round_page(*_marks()).encode())
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, the_next_round().encode())
        here.clock.now = AFTER
        await here.ask()
        assert here.scores.get(10) is None
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(200, HTML, stats_after().encode())
        here.clock.now += dt.timedelta(hours=25)
        await here.ask()
        report = here.scores.get(10)
    assert report is not None
    rated = next(chance for chance in report.model.scored if chance.chance == "Getting a rating")
    assert sum(bucket.happened * bucket.count for bucket in rated.buckets) == pytest.approx(44, abs=0.01)


async def test_a_page_stored_again_isnt_the_read_after(tmp_path: Path) -> None:
    """A page unchanged since before the round can be stored again once its last read leaves the window. That
    says nothing has moved, so scoring still waits, rather than saying nobody got a rating."""
    async with a_round(tmp_path) as here:
        await here.ask()
        here.routes[f"{here.base}{ROUND_10}"] = Response(200, HTML, fco_round_page(*_marks()).encode())
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(
            200,
            HTML,
            fco_round_page(FcoMatch("Alfa", "Gamma", kickoff="30/12/2026 15:00"), round=11).encode(),
        )
        here.clock.now = NOW + FACTS_WINDOW + dt.timedelta(days=1)
        await here.ask()
        assert here.scores.get(10) is None
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(200, HTML, stats_after().encode())
        here.clock.now += dt.timedelta(hours=25)
        await here.ask()
        report = here.scores.get(10)
    assert report is not None
    rated = next(chance for chance in report.model.scored if chance.chance == "Getting a rating")
    assert sum(bucket.happened * bucket.count for bucket in rated.buckets) == pytest.approx(44, abs=0.01)
