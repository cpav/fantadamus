"""`fantadamus recalibrate` on a round the tools scored: the proposal from its set, the lake's latest
statistics read and the table (mvp-recalibrate R8.1; design C8)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.cli import __main__ as cli
from fantadamus.web.fetch import Response
from tests.collect_harness import HTML, ROUND_ROUTE, STATS_ROUTE
from tests.collect_pages import FcoMatch, fco_round_page
from tests.lineup_harness import MATCHES, a_round, stats_after, the_next_round

pytestmark = pytest.mark.anyio

ROUND_10 = "/probabili-formazioni/10-giornata"
AFTER = dt.datetime(2026, 11, 1, 5, 0, tzinfo=dt.UTC)


async def test_recalibrate_on_invented_rounds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    finished = fco_round_page(*(FcoMatch(m.home, m.away, kickoff=m.kickoff, confirmed=True) for m in MATCHES))
    async with a_round(tmp_path) as here:
        await here.ask()
        here.routes[f"{here.base}{ROUND_10}"] = Response(200, HTML, finished.encode())
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, the_next_round().encode())
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(200, HTML, stats_after().encode())
        here.clock.now = AFTER
        await here.ask()
        assert here.scores.calibration_set(10) is not None
        monkeypatch.setattr(cli, "_scores", lambda _: here.scores)
        capsys.readouterr()
        assert cli.main(["recalibrate", "--lake", str(here.store.root)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].endswith("on round 10")
    assert "START_MAP: not proposed: below its minimum sample: 56 of 300" in lines
    assert any(line.startswith("  held out half 1 of round 10's matches: Brier") for line in lines)
    assert "  evidence: 56 players whose start is known (its minimum: 300)" in lines
    kept = here.scores.proposal()
    assert kept is not None
    assert kept.read_at is not None
    assert kept.read_at >= AFTER - dt.timedelta(hours=12)  # the read after the round, the latest
    assert kept.season[0].name == "PENALTY_RATE"
    assert "PENALTY_CONVERSION: no penalty taken" in kept.not_counted  # the invented players took none
    assert kept.season[0].rate is not None
    assert kept.season[0].rate.count == 4 * 8  # the harness's table: four clubs, eight matches each
