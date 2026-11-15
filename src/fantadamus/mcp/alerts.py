"""The alerts' check, after a scheduled run: has what it stored changed the user's call? (mvp-alerts C4)

The lineup is the one `best_lineup` would give, replayed on the stored facts as the review replays the
advice: it neither collects nor logs to the decision log. Only the alert log is written.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from fantadamus.contracts.types import Role
from fantadamus.core.names import name_key
from fantadamus.domains.alerts import Alert, Call, Latest, call_of, call_of_advice, decide, newest
from fantadamus.domains.availability.silver import INJURIES, OFFICIAL_LINEUPS, OUTLET_VIEWS, SUSPENSIONS
from fantadamus.domains.facts import read_silver
from fantadamus.domains.fixtures.gold import deadline, next_round
from fantadamus.domains.fixtures.silver import FIXTURES
from fantadamus.domains.freshness import FACTS_WINDOW
from fantadamus.domains.review import last_advice
from fantadamus.engine.constants import ALERT_WINDOW_HOURS, SIMULATIONS
from fantadamus.lake.alert_log import AlertLine, AlertLog
from fantadamus.league.squads import MINE
from fantadamus.mcp.advisor import Advisor, PlayerFacts
from fantadamus.mcp.tools.lineup import Lineup, replayed_lineup, squad_at
from fantadamus.web.collector import CollectReport

ALERT_TABLES = frozenset(
    domain.table.name for domain in (OFFICIAL_LINEUPS, OUTLET_VIEWS, INJURIES, SUSPENSIONS)
)
"""What a run must store for a check: lineups, official or probable, and the injured and suspended pages
(decision 1 of the requirements)."""

Notify = Callable[[str, str, str], str | None]
"""Shows a notification from its title, subtitle and text: None once shown, else why it couldn't be."""

Outcome = Literal[
    "off",
    "nothing new",
    "outside the window",
    "no league",
    "no lineup",
    "baseline",
    "unchanged",
    "sent",
    "not shown",
]


@dataclass(frozen=True)
class Checked:
    outcome: Outcome
    message: str
    alert: Alert | None = None


def stored_news(report: CollectReport | None) -> bool:
    """Whether the run stored a new lineup, injury or ban; a page that only confirmed one isn't new (R4.1)."""
    return report is not None and any(
        count for page in report.pages for table, count in page.stored.items() if table in ALERT_TABLES
    )


def _latest(side: PlayerFacts) -> Latest:
    official = side.present.official if side.present is not None else None
    news = side.news
    out = news.out if news is not None else None
    return Latest(
        official=official.status if official is not None else None,
        official_at=official.source.captured_at if official is not None else None,
        out=out.reason if out is not None else None,
        banned=news.banned if news is not None else False,
        out_at=max((source.captured_at for source in news.sources), default=None)
        if news is not None
        else None,
    )


def _call(lineup: Lineup, roles: Mapping[int, Role], chances: Mapping[int, float], at: dt.datetime) -> Call:
    by_name = {player.name: player.player_id for player in lineup.starters}
    return call_of(
        round=lineup.round,
        formation=lineup.formation,
        starters=[player.player_id for player in lineup.starters],
        bench=[player.player_id for player in lineup.bench],
        roles=roles,
        captain=by_name.get(lineup.captain or ""),
        vice=by_name.get(lineup.vice or ""),
        chances=chances,
        at=at,
    )


def check_alerts(
    advisor: Advisor,
    alerts: AlertLog,
    report: CollectReport | None,
    notify: Notify,
    *,
    enabled: bool = True,
    rounds: int = SIMULATIONS,
) -> Checked:
    """After a scheduled run: the user's call worked out again on the facts now, and one notification if it
    changed from the one they last saw (R1 to R3)."""
    if not enabled:
        return Checked("off", "Alerts are switched off in the private configuration.")
    if not stored_news(report):
        return Checked("nothing new", "No new lineup, injury or ban was stored: nothing to check.")
    now = advisor.clock().astimezone(dt.UTC)
    fixtures = read_silver(advisor.lake, FIXTURES, now - FACTS_WINDOW, now)
    round = next_round(fixtures, now)
    lock = deadline(fixtures, round, now) if round is not None else None
    if round is None or lock is None or now < lock - dt.timedelta(hours=ALERT_WINDOW_HOURS):
        return Checked("outside the window", "No round's deadline is in the next day.")
    stored = advisor.rules.get(advisor.user)
    squad = advisor.squads.get(advisor.user, MINE) if advisor.squads is not None else None
    if stored is None or stored.rules.lineup is None or squad is None:
        return Checked("no league", "No league rules or squad are stored.")
    at = squad_at(advisor, stored, squad, now)
    replayed = replayed_lineup(advisor, stored, squad, at, rounds=rounds) if at is not None else None
    if at is None or replayed is None or replayed.lineup is None or replayed.lineup.round != round:
        return Checked("no lineup", f"Round {round}'s lineup can't be worked out from the stored facts.")
    roles = {player.player_id: player.role for player in squad.players}
    names = {player.player_id: player.name for player in squad.players}
    sides = at.gathered.sides
    chances = {side.player.player_id: side.present.p_start for side in sides if side.present is not None}
    call = _call(replayed.lineup, roles, chances, now)
    told = last_advice(advisor.log.read(), user=advisor.user, team=squad.team, round=round, lock=lock)
    logged = [
        line.call
        for line in alerts.read()
        if line.user == advisor.user and name_key(line.team) == name_key(squad.team) and line.round == round
    ]
    baseline = newest([*logged, call_of_advice(told, round=round, roles=roles) if told is not None else None])
    decided = decide(
        baseline,
        call,
        saved_at=max(squad.saved_at, stored.saved_at),
        roles=roles,
        latest={side.player.player_id: _latest(side) for side in sides},
        names=names,
    )
    line = AlertLine(
        kind="baseline", logged_at=now, user=advisor.user, team=squad.team, round=round, call=call
    )
    if decided.step == "unchanged":
        return Checked("unchanged", f"Round {round}'s call hasn't changed.")
    if decided.alert is None:
        why = (
            "no lineup was told this round" if baseline is None else "the squad or the rules were saved since"
        )
        alerts.append(line.model_copy(update={"reason": why}))
        return Checked("baseline", f"Round {round}'s call kept to compare with: {why}.")
    alert = decided.alert
    reason = notify(alert.title, alert.subtitle, alert.text)
    alerts.append(
        line.model_copy(
            update={
                "kind": "alert",
                "changes": decided.found,
                "title": alert.title,
                "subtitle": alert.subtitle,
                "text": alert.text,
                "delivered": reason is None,
                "reason": reason,
            }
        )
    )
    if reason is not None:
        return Checked("not shown", f"The alert couldn't be shown ({reason}): {alert.text}", alert)
    return Checked("sent", f"Alert sent: {alert.text}", alert)
