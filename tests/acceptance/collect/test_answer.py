"""mvp-collect acceptance tests on the answer: sources compared and confidence (R5)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.lake.duckdb_store import LakeStore
from tests.xy_harness import ask, collect, lineup, odds_for, page, send, set_classic, tools

pytestmark = pytest.mark.anyio

READ = dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.UTC)
CALENDAR = "https://www.fantacalcio.it/serie-a/calendario"
ROUND_PAGE = "https://www.fantacalcio-online.com/it/serie-a/2026-2027/probabili-formazioni/ultima-giornata"


async def test_at7_kickoff_disagreement_shown(tmp_path: Path) -> None:
    """AT-7: when Fantacalcio.it's calendar and Fantacalcio-Online's round page disagree on a kickoff, the
    answer uses Fantacalcio.it's and says so; its probabilities carry their confidence (R5.1, R5.3)."""
    hosts = ("example.org", "fantacalcio.it", "fantacalcio-online.com")
    later = page("fixtures")
    later["matches"][0]["kickoff_at"] = "2026-10-31T15:30:00+01:00"  # the round page has Alfa v Beta later
    async with tools(LakeStore(tmp_path), hosts=hosts) as client:
        await set_classic(client)
        await collect(client, READ, facts=("season",))
        for home, away in (("Alfa", "Beta"), ("Gamma", "Delta")):
            for outlet in ("Uno", "Due"):
                assert not (
                    await send(client, "submit_probable_lineups", lineup(home, away, outlet), READ)
                ).is_error
            assert not (await send(client, "submit_match_odds", odds_for(home, away), READ)).is_error
        assert not (await send(client, "submit_fixtures", page("fixtures"), READ, url=CALENDAR)).is_error
        newer = READ + dt.timedelta(hours=1)
        assert not (await send(client, "submit_fixtures", later, newer, url=ROUND_PAGE)).is_error
        answer = await ask(client)
    assert answer["status"] == "answer", answer
    nove = answer["answer"]["players"][0]
    assert nove["name"] == "Alfa Nove"
    assert dt.datetime.fromisoformat(nove["kickoff"]) == dt.datetime(2026, 10, 31, 14, 0, tzinfo=dt.UTC)
    assert (
        "Sources disagree, the first is used: Alfa v Beta kickoff: Fantacalcio.it Sat 31 Oct 15:00, "
        "Fantacalcio-Online Sat 31 Oct 15:30."
    ) in nove["notes"]
    assert nove["p_start_confidence"] == {"sources": 2, "spread": 0.0, "label": "agree"}
    assert nove["win_confidence"]["label"] == "one source"  # one odds page
    assert nove["p_scores_confidence"]["label"] == "one source"  # the weaker of the two
