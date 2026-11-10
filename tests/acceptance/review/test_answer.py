"""AT-7 of mvp-review: the review through `review_round`, in its format, within 3 seconds and 15 KB, from no
new page (design C8; R2.4, R5.1 to R5.3)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from scripts.checks._common import run_command

from tests.integration.review.test_tool import review
from tests.lineup_harness import a_round, finished, stats_after_rated

pytestmark = pytest.mark.anyio


def _key(name: str) -> str:
    return name.replace(" ", "_")


async def test_at7_the_review(tmp_path: Path) -> None:
    """One defender swapped: the real result is his 7.5 against the advised one's 5.5, judged by its cost; the
    real score, the user's own total beside it, and the record."""
    async with a_round(tmp_path) as here:
        advised = (await here.ask())["lineup"]
        out = next(player["name"] for player in advised["starters"] if player["role"] == "D")
        into = next(player["name"] for player in advised["bench"] if player["role"] == "D")
        eleven = [into if player["name"] == out else player["name"] for player in advised["starters"]]
        bench = [out if player["name"] == into else player["name"] for player in advised["bench"]]
        finished(here, stats_after_rated(ratings={_key(out): 5.5, _key(into): 7.5}))
        result = await review(here, starters=eleven, bench=bench, app_total=50.0)
    assert result["status"] == "review", result
    found = result["review"]
    assert [(choice["kind"], choice["fielded"], choice["advised"]) for choice in found["choices"]] == [
        ("player", [into], [out])
    ]
    swap = found["choices"][0]
    assert swap["real_gain"] == 2.0
    assert swap["judged"] in ("cost", "even", "gain")
    assert found["real"] is not None
    assert found["position"] in ("below", "inside", "above")
    assert (found["app_total"], found["app_differs"]) == (50.0, True)
    assert found["real"] - found["advice_real"] == pytest.approx(2.0)
    assert found["record"]["rounds"] == 1
    assert found["record"]["verdict"] == "too early"
    assert not found["replayed"]
    assert list((tmp_path / "lake" / "reviews").glob("*.jsonl"))  # logged, privately beside the lake


async def test_at7_the_advice_replayed_when_none_was_asked(tmp_path: Path) -> None:
    """The collector read the round before the lock, as it does on its schedule, and nobody asked: the
    advice is replayed as of that read, since at the lock itself the lineups and odds were past their
    freshness targets."""
    async with a_round(tmp_path) as here:
        collector = here.calibrator.collector
        assert collector is not None
        here.collect_log.append(collector.collect())
        finished(here)
        result = await review(here, as_advised=True)
    assert result["status"] == "review", result
    assert result["review"]["replayed"]


async def test_at7_in_budget(tmp_path: Path) -> None:
    """In a process of its own for the time, as the lineup's budget is measured: see
    `tests/lineup_speed.py`."""
    timed = run_command([sys.executable, "-m", "tests.lineup_speed", "--review"])
    assert timed.returncode == 0, timed.stderr
    assert float(timed.stdout) < 3.0
    async with a_round(tmp_path) as here:
        await here.ask()
        finished(here)
        result = await review(here, as_advised=True)
        pages = [url for url, _, _ in here.web.calls]
    assert len(json.dumps(result).encode()) < 15_000
    assert set(pages) <= set(here.routes)  # only the pages the round already reads
