"""The starting map through the tools: the identity changes no answer, and a calibration set keeps the raw
chance, so that a later fit doesn't compound on the map (mvp-recalibrate R2.2; design C3)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from fantadamus.domains.availability import consensus
from fantadamus.engine.recalibrate import StartMap, mapped
from fantadamus.web.fetch import Response
from tests.collect_harness import HTML, ROUND_ROUTE, STATS_ROUTE
from tests.collect_pages import FcoMatch, fco_round_page
from tests.lineup_harness import MATCHES, a_round, player_id, stats_after, the_next_round

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("start_values")]  # worked out on the starting values

A_MAP: StartMap = ((0.0, 0.0), (0.9, 0.6), (1.0, 1.0))
STARTER = (0.9 + 0.9 + 0.95 + 0.9) / 4  # the outlets' default for a listed starter
ROUND_10 = "/probabili-formazioni/10-giornata"
AFTER = dt.datetime(2026, 11, 1, 5, 0, tzinfo=dt.UTC)


async def _answer(tmp_path: Path) -> dict[str, Any]:
    async with a_round(tmp_path) as here:
        return await here.ask()


async def test_the_identity_changes_no_answer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    identity = await _answer(tmp_path / "identity")
    monkeypatch.setattr(consensus, "START_MAP", A_MAP)
    moved = await _answer(tmp_path / "moved")
    assert moved != identity  # a map does reach the answer
    monkeypatch.setattr(consensus, "mapped", lambda chance, _: chance)  # no map at all
    assert await _answer(tmp_path / "none") == identity


async def test_the_set_keeps_the_raw_chance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(consensus, "START_MAP", A_MAP)
    finished = fco_round_page(*(FcoMatch(m.home, m.away, kickoff=m.kickoff, confirmed=True) for m in MATCHES))
    async with a_round(tmp_path) as here:
        await here.ask()
        here.routes[f"{here.base}{ROUND_10}"] = Response(200, HTML, finished.encode())
        here.routes[f"{here.base}{ROUND_ROUTE}"] = Response(200, HTML, the_next_round().encode())
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(200, HTML, stats_after().encode())
        here.clock.now = AFTER
        await here.ask()
        kept = here.scores.calibration_set(10)
    assert kept is not None
    row = next(row for row in kept.rows if row.player_id == player_id("Alfa", "Nove"))
    assert row.consensus == pytest.approx(STARTER)  # what the outlets said
    assert row.p_start == pytest.approx(mapped(STARTER, A_MAP))  # what the model used
    assert row.p_start < row.consensus
