"""As-of reads of the season figures (design C6; R7.4): each the latest submission at or before `as_of`."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from pydantic import BaseModel

from fantadamus.domains.facts import Source, latest_by, latest_submissions
from fantadamus.domains.players.resolve import KnownPlayer
from fantadamus.domains.season.silver import PenaltyTakerRow, PlayerSeasonRow, TeamSeasonRow
from fantadamus.domains.sources import best_by
from fantadamus.engine.constants import LEAGUE_GOALS_PER_MATCH


class PenaltyOrder(BaseModel):
    takers: list[str]
    """Names as the page writes them, first choice first."""
    source: Source


def known_players(rows: Sequence[PlayerSeasonRow], as_of: dt.datetime) -> list[KnownPlayer]:
    latest = latest_by(rows, as_of, key=lambda row: row.player_id)
    return [
        KnownPlayer(player_id=row.player_id, name=row.name, club=row.club)
        for _, row in sorted(latest.items())
    ]


def player_form(
    rows: Sequence[PlayerSeasonRow], player_id: int, as_of: dt.datetime
) -> PlayerSeasonRow | None:
    return latest_by(rows, as_of, key=lambda row: row.player_id).get(player_id)


def team_season(rows: Sequence[TeamSeasonRow], club: str, as_of: dt.datetime) -> TeamSeasonRow | None:
    """The club's row from the highest-ranked source, its newest read (mvp-collect R5.1)."""
    return best_by(rows, as_of, key=lambda row: row.club).get(club)


def league_goals_per_match(rows: Sequence[TeamSeasonRow], as_of: dt.datetime) -> float:
    """Each team's goals per match across the league, setting an average keeper's skill (mvp-roles R3.3)."""
    table = best_by(rows, as_of, key=lambda row: row.club).values()
    played = sum(row.played for row in table)
    goals = sum(row.goals_for for row in table)
    return goals / played if played and goals else LEAGUE_GOALS_PER_MATCH


def penalty_order(rows: Sequence[PenaltyTakerRow], club: str, as_of: dt.datetime) -> PenaltyOrder | None:
    """The club's takers from the latest submission that lists the club."""
    latest = latest_submissions(rows, as_of, key=lambda row: row.club).get(club)
    if latest is None:
        return None
    takers = sorted(latest, key=lambda row: row.rank)
    return PenaltyOrder(takers=[row.name for row in takers], source=takers[0].source)
