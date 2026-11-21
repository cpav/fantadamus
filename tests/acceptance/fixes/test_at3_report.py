"""mvp-fixes AT-3: `fantadamus collect --report` shows a page that failed as failed, with its cause, and says
it will be tried again (R1.5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fantadamus.cli.__main__ import main
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.duckdb_store import LakeStore
from tests.collect_harness import FakeWeb, round_collector, ticking
from tests.xy_harness import NOW

BASE = "https://example.org"
CHAMPIONS = BASE + "/wiki/2026%E2%80%9327_UEFA_Champions_League_league_phase?action=raw"


def test_at3_the_report_says_it_tries_again(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    collector = round_collector(
        LakeStore(tmp_path / "lake"),
        BASE,
        tmp_path / "robots",
        transport=FakeWeb({BASE + "/robots.txt": TimeoutError("timed out")}),
        hosts=["example.org"],
        clock=ticking(NOW),
        other_competitions=[CHAMPIONS],
    )
    CollectLog(tmp_path / "collect").append(collector.collect(facts=["other_fixtures"]))
    assert main(["collect", "--report", "--lake", str(tmp_path / "lake")]) == 0
    printed = capsys.readouterr().out
    assert (
        f"{CHAMPIONS}: failed (robots.txt couldn't be read (timed out)): tried again at the next run"
        in printed
    )
    assert "disallowed" not in printed
