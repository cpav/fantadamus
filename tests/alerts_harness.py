"""A round for the alerts' tests: the lineup harness's round, the advisor the check replays with, a notifier
that records instead of showing, and the round page's official lineups (mvp-alerts). Clubs and players are
invented."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fantadamus.lake.alert_log import AlertLog
from fantadamus.league.rules import RulesStore
from fantadamus.mcp.advisor import load_reading_list
from fantadamus.mcp.alerts import Checked, check_alerts
from fantadamus.mcp.server import make_advisor
from fantadamus.web.collector import CollectReport
from tests.collect_pages import FcoMatch, squad
from tests.lineup_harness import MATCHES, Round
from tests.xy_harness import CLUBS, ROOT

DEADLINE = dt.datetime(2026, 10, 31, 14, 0, tzinfo=dt.UTC)  # Alfa v Beta, 15:00 in Rome
IN_WINDOW = DEADLINE - dt.timedelta(hours=1)


@dataclass
class Shown:
    """Notifications as `notify` would show them; `refuse` makes each fail with that reason."""

    sent: list[tuple[str, str, str]] = field(default_factory=list)
    refuse: str | None = None

    def __call__(self, title: str, subtitle: str, text: str) -> str | None:
        if self.refuse is None:
            self.sent.append((title, subtitle, text))
        return self.refuse


def officials(benched: Sequence[str] = ()) -> tuple[FcoMatch, FcoMatch]:
    """Both matches' official lineups: the probable elevens, but for one player of the first match `benched`,
    whose place goes to his club's forward off the bench, who isn't in the squad."""
    assert len(benched) <= 1
    marked: list[str] = []
    for club in (MATCHES[0].home, MATCHES[0].away):
        eleven = [name for name in squad(club)[:11] if name not in benched]
        marked += [*eleven, *([f"{club} Tredici"] if len(eleven) < 11 else [])]
    return (
        FcoMatch(MATCHES[0].home, MATCHES[0].away, marked=tuple(marked)),
        FcoMatch(MATCHES[1].home, MATCHES[1].away, kickoff=MATCHES[1].kickoff, confirmed=True),
    )


def collect_round(here: Round, at: dt.datetime, matches: Sequence[FcoMatch], fact: str) -> CollectReport:
    """The scheduled run at `at`, reading the round page with those matches for `fact`."""
    here.clock.now = at
    here.round_page(*matches)
    collector = here.calibrator.collector
    assert collector is not None
    return collector.collect(facts=[fact])


def collect_officials(here: Round, at: dt.datetime, benched: Sequence[str] = ()) -> CollectReport:
    """The scheduled run at `at`, reading the round page with those official lineups."""
    return collect_round(here, at, officials(benched), "official_lineups")


async def told_after_officials(here: Round) -> dict[str, Any]:
    """The official lineups out an hour before the window's check, as the outlets had them, and the lineup the
    user was told then."""
    collect_officials(here, IN_WINDOW - dt.timedelta(hours=1))
    lineup: dict[str, Any] = (await here.ask())["lineup"]
    return lineup


def check(
    here: Round,
    report: CollectReport | None,
    shown: Shown,
    *,
    user: str = "user-1",
    enabled: bool = True,
    rounds: int = 500,
) -> Checked:
    advisor = make_advisor(
        here.store,
        rules=RulesStore(here.store.root / "league"),
        log=here.log,
        clubs=CLUBS,
        reading=load_reading_list(ROOT / "config" / "reading_list.toml"),
        user=user,
        clock=here.clock,
        collect_log=here.collect_log,
    )
    return check_alerts(advisor, alerts(here), report, shown, enabled=enabled, rounds=rounds)


def alerts(here: Round) -> AlertLog:
    return AlertLog(Path(here.store.root) / "alerts")


def benchable(lineup: dict[str, Any]) -> dict[str, Any]:
    """An outfield player of the first match in the eleven: the one an official lineup benches."""
    first = (MATCHES[0].home, MATCHES[0].away)
    return dict(next(p for p in lineup["starters"] if p["club"] in first and p["role"] != "P"))
