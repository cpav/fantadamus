"""AT-3 of mvp-alerts: the same change isn't sent twice; a change back is sent (R3.3)."""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path

import pytest

from tests.alerts_harness import (
    IN_WINDOW,
    Shown,
    alerts,
    alfa_starter,
    check,
    collect_officials,
    told_after_officials,
)
from tests.lineup_harness import a_round

pytestmark = pytest.mark.anyio
QUARTER = dt.timedelta(minutes=15)


async def test_at3_not_sent_twice(tmp_path: Path) -> None:
    """Checked again on the same facts, then after a run that found the page unchanged: one alert."""
    async with a_round(tmp_path) as here:
        benched = alfa_starter(await told_after_officials(here))["name"]
        shown = Shown()
        report = collect_officials(here, IN_WINDOW - QUARTER, [benched])
        first, same = check(here, report, shown), check(here, report, shown)
        unchanged_page = check(here, collect_officials(here, IN_WINDOW, [benched]), shown)
    assert (first.outcome, same.outcome, unchanged_page.outcome) == ("sent", "unchanged", "nothing new")
    assert len(shown.sent) == 1


async def test_at3_a_change_back_is_sent(tmp_path: Path) -> None:
    """The first official lineup benches him, a corrected one starts him: two alerts, the second undoing the
    first."""
    async with a_round(tmp_path) as here:
        benched = alfa_starter(await told_after_officials(here))["name"]
        shown = Shown()
        first = check(here, collect_officials(here, IN_WINDOW - QUARTER, [benched]), shown)
        back = check(here, collect_officials(here, IN_WINDOW), shown)
        lines = alerts(here).read()
    assert (first.outcome, back.outcome) == ("sent", "sent")
    assert [line.kind for line in lines] == ["alert", "alert"]
    assert lines[1].changes[0].now == lines[0].changes[0].before
    assert shown.sent[1][2].startswith(f"Start {benched} instead of ")
    assert f"the official lineup starts {benched}" in shown.sent[1][2]


async def test_at3_only_this_round_this_user_and_this_team(tmp_path: Path) -> None:
    """Calls logged for another round, another user or a league-mate's team aren't the baseline."""
    async with a_round(tmp_path) as here:
        benched = alfa_starter(await told_after_officials(here))["name"]
        report = collect_officials(here, IN_WINDOW, [benched])
        shown = Shown()
        assert check(here, report, shown).outcome == "sent"
        [line] = alerts(here).read()
        log = alerts(here)
        for other in ({"round": 9}, {"user": "someone-else"}, {"team": "A league-mate"}):
            later = dataclasses.replace(line.call, starters=frozenset(), at=IN_WINDOW + QUARTER)
            log.append(line.model_copy(update={"logged_at": IN_WINDOW + QUARTER, "call": later} | other))
        here.clock.now = IN_WINDOW + 2 * QUARTER
        told_call = check(here, report, shown)
    assert told_call.outcome == "unchanged"
    assert len(shown.sent) == 1
