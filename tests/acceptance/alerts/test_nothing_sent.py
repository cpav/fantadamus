"""AT-2 of mvp-alerts: nothing sent outside the window, after the deadline, without a squad, with no
baseline, when only the chances moved, when nothing new was stored, or when the squad was saved after the
baseline (R1.2, R1.3, R2.3)."""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path

import pytest

from fantadamus.cli.notify import CONFIG_VAR, alerts_enabled
from fantadamus.engine.constants import ALERT_WINDOW_HOURS
from fantadamus.web.collector import CollectReport
from tests.alerts_harness import DEADLINE, IN_WINDOW, Shown, alerts, check, collect_officials, collect_round
from tests.lineup_harness import MATCHES, a_round

pytestmark = pytest.mark.anyio

BENCHED = ["Alfa Sei"]  # in the harness's advised eleven


async def test_at2_outside_the_window(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await here.ask()
        report = collect_officials(here, DEADLINE - dt.timedelta(hours=25), benched=BENCHED)
        shown = Shown()
        assert check(here, report, shown).outcome == "outside the window"
        assert (shown.sent, alerts(here).read()) == ([], [])


async def test_at2_after_the_deadline(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await here.ask()
        report = collect_officials(here, DEADLINE + dt.timedelta(minutes=5), benched=BENCHED)
        shown = Shown()
        assert check(here, report, shown).outcome == "outside the window"
        assert shown.sent == []


async def test_at2_without_a_squad(tmp_path: Path) -> None:
    async with a_round(tmp_path, squad=False) as here:
        report = collect_officials(here, IN_WINDOW, benched=BENCHED)
        shown = Shown()
        assert check(here, report, shown).outcome == "no league"
        assert check(here, report, shown, user="someone-else").outcome == "no league"
        assert shown.sent == []


async def test_at2_without_a_baseline(tmp_path: Path) -> None:
    """No lineup told this round: the first call is kept, and the next check on the same facts finds it
    unchanged."""
    async with a_round(tmp_path) as here:
        report = collect_officials(here, IN_WINDOW, benched=BENCHED)
        shown = Shown()
        assert check(here, report, shown).outcome == "baseline"
        assert check(here, report, shown).outcome == "unchanged"
        [line] = alerts(here).read()
    assert (line.kind, line.reason) == ("baseline", "no lineup was told this round")
    assert shown.sent == []


async def test_at2_chances_alone(tmp_path: Path) -> None:
    """One outlet gives a midfielder off the bench two points more: his chance moves, the call doesn't."""
    async with a_round(tmp_path) as here:
        await here.ask()
        likelier = dataclasses.replace(MATCHES[1], percents={"Gamma Dodici": (12, 30, 5, 30)})
        report = collect_round(here, IN_WINDOW, (MATCHES[0], likelier), "probable_lineups")
        shown = Shown()
        assert check(here, report, shown).outcome == "unchanged"
        assert (shown.sent, alerts(here).read()) == ([], [])


async def test_at2_nothing_new_stored(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await here.ask()
        report = collect_officials(here, IN_WINDOW, benched=BENCHED)
        shown = Shown()
        nothing = report.model_copy(
            update={"pages": [page.model_copy(update={"stored": {}}) for page in report.pages]}
        )
        empty = CollectReport(started_at=IN_WINDOW, finished_at=IN_WINDOW, round=None, pages=[])
        assert check(here, nothing, shown).outcome == "nothing new"
        assert check(here, empty, shown).outcome == "nothing new"
        assert check(here, None, shown).outcome == "nothing new"
        assert shown.sent == []


async def test_at2_a_squad_saved_after_the_baseline(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await here.ask()
        here.clock.now = IN_WINDOW - dt.timedelta(hours=2)
        await here.set_squad()
        report = collect_officials(here, IN_WINDOW, benched=BENCHED)
        shown = Shown()
        assert check(here, report, shown).outcome == "baseline"
        [line] = alerts(here).read()
    assert line.reason == "the squad or the rules were saved since"
    assert shown.sent == []


async def test_at2_the_window_edges(tmp_path: Path) -> None:
    """A minute before the window opens, nothing; as it opens, the check runs."""
    async with a_round(tmp_path) as here:
        await here.ask()
        opens = DEADLINE - dt.timedelta(hours=ALERT_WINDOW_HOURS)
        report = collect_officials(here, opens - dt.timedelta(minutes=1), benched=BENCHED)
        shown = Shown()
        assert check(here, report, shown).outcome == "outside the window"
        here.clock.now = opens
        assert check(here, report, shown).outcome == "sent"


async def test_at2_the_switch_off(tmp_path: Path) -> None:
    """`[alerts] enabled = false` in the private configuration: nothing checked, nothing sent."""
    config = tmp_path / "private.toml"
    config.write_text("[alerts]\nenabled = false\n", encoding="utf-8")
    enabled, _ = alerts_enabled({CONFIG_VAR: str(config)})
    async with a_round(tmp_path) as here:
        await here.ask()
        report = collect_officials(here, IN_WINDOW, benched=BENCHED)
        shown = Shown()
        checked = check(here, report, shown, enabled=enabled)
        assert (checked.outcome, shown.sent, alerts(here).read()) == ("off", [], [])
