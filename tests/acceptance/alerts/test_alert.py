"""AT-1 of mvp-alerts: a scheduled run that stores an official lineup inside the window, benching a starter of
the call, sends one alert naming him and his cover (R1, R2, R3)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from tests.alerts_harness import (
    IN_WINDOW,
    Shown,
    alerts,
    alfa_starter,
    check,
    collect_officials,
    collect_round,
    told_after_officials,
)
from tests.lineup_harness import MATCHES, a_round

pytestmark = pytest.mark.anyio


async def test_at1_an_official_lineup_benches_a_starter(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        told = await told_after_officials(here)
        benched = alfa_starter(told)
        report = collect_officials(here, IN_WINDOW, benched=[benched["name"]])
        shown = Shown()
        checked = check(here, report, shown)
        [line] = alerts(here).read()
        stored = here.squads.get("user-1")
    assert stored is not None
    names = {player.player_id: player.name for player in stored.players}
    assert checked.outcome == "sent", checked
    [(title, subtitle, text)] = shown.sent
    assert (title, subtitle) == ("Fantadamus · Round 10", "Official lineup out")
    swap = next(
        change for change in line.changes if change.kind == "swap" and change.before == benched["player_id"]
    )
    assert swap.now is not None
    cover = names[swap.now]
    assert (
        f"Start {cover} instead of {benched['name']}: the official lineup has {benched['name']} on the bench."
        in text
    )
    assert line.kind == "alert"
    assert line.delivered is True
    assert line.text == text
    assert benched["player_id"] not in line.call.starters


async def test_at1_a_notification_the_mac_refuses_is_logged(tmp_path: Path) -> None:
    """Logged with its reason, not retried: its call is the baseline all the same."""
    async with a_round(tmp_path) as here:
        benched = alfa_starter(await told_after_officials(here))["name"]
        report = collect_officials(here, IN_WINDOW, benched=[benched])
        refused = Shown(refuse="not a Mac")
        checked, again = check(here, report, refused), check(here, report, refused)
        [line] = alerts(here).read()
    assert (checked.outcome, again.outcome) == ("not shown", "unchanged")
    assert "not a Mac" in checked.message
    assert (line.kind, line.delivered, line.reason) == ("alert", False, "not a Mac")


async def test_at1_no_alert_when_the_facts_dont_give_a_lineup(tmp_path: Path) -> None:
    """The round page without its teams' tables: no chance of starting for anyone, so no lineup to compare."""
    unpublished = tuple(dataclasses.replace(match, lineups=False) for match in MATCHES)
    async with a_round(tmp_path, matches=unpublished) as here:
        report = collect_round(here, IN_WINDOW, unpublished, "fixtures")
        news = report.model_copy(
            update={
                "pages": [page.model_copy(update={"stored": {"outlet_views": 1}}) for page in report.pages]
            }
        )
        shown = Shown()
        checked = check(here, news, shown)
    assert checked.outcome == "no lineup", checked
    assert checked.message == "Round 10's lineup can't be worked out from the stored facts."
    assert shown.sent == []
