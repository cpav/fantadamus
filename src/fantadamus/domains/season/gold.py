"""As-of reads of the season figures (design C6; R7.4): each the latest submission at or before `as_of`."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from pydantic import BaseModel

from fantadamus.domains.facts import Source, latest_by, latest_submissions
from fantadamus.domains.players.resolve import KnownPlayer, resolve
from fantadamus.domains.season.silver import PenaltyTakerRow, PlayerSeasonRow, TeamSeasonRow
from fantadamus.domains.sources import best_by
from fantadamus.engine.constants import LEAGUE_GOALS_PER_MATCH

ORDER_CHANGE_SHOWN_FOR = dt.timedelta(days=7)
"""How long an answer mentions a changed penalty order: about a round (mvp-lineup R10.4)."""


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


def penalty_share(
    player: KnownPlayer,
    order: PenaltyOrder,
    mates: Sequence[KnownPlayer],
    chance_of_starting: Callable[[KnownPlayer], float],
) -> float:
    """His share of his club's penalties: the chance that everyone listed ahead of him misses the start. A
    name no club-mate answers to has no rated game, so he isn't taking them (mvp-lineup R10.1)."""
    listed = [resolve(name, mates).player for name in order.takers]
    if player not in listed:
        return 0.0
    share = 1.0
    for ahead in listed[: listed.index(player)]:
        if ahead is not None:
            share *= 1.0 - chance_of_starting(ahead)
    return share


def takers_ahead(player: KnownPlayer, order: PenaltyOrder, mates: Sequence[KnownPlayer]) -> list[str]:
    """The names listed ahead of him, as the page writes them; none if he's first or not listed."""
    listed = [resolve(name, mates).player for name in order.takers]
    return order.takers[: listed.index(player)] if player in listed else []


@dataclass(frozen=True)
class OrderChange:
    before: list[str]
    after: list[str]
    at: dt.datetime
    """When the new order was first read."""


def order_change(rows: Sequence[PenaltyTakerRow], club: str, as_of: dt.datetime) -> OrderChange | None:
    """How the club's listed order differs between its two latest reads, while the newer is recent enough to
    mention (mvp-lineup R10.4). Reads that repeat an order aren't a change."""
    now = penalty_order(rows, club, as_of)
    if now is None:
        return None
    at = now.source.captured_at
    earlier = penalty_order(rows, club, at - dt.timedelta(microseconds=1))
    if earlier is None or earlier.takers == now.takers or as_of - at > ORDER_CHANGE_SHOWN_FOR:
        return None
    return OrderChange(before=earlier.takers, after=now.takers, at=at)


@dataclass(frozen=True)
class PenaltyMismatch:
    first: PlayerSeasonRow
    """The listed first taker."""
    other: PlayerSeasonRow
    """A club-mate who has taken more penalties this season."""


def penalty_mismatch(
    player: KnownPlayer,
    order: PenaltyOrder,
    mates: Sequence[KnownPlayer],
    seasons: Mapping[int, PlayerSeasonRow],
) -> PenaltyMismatch | None:
    """When someone has taken more of the club's penalties than the listed first, and `player` is one of the
    two: the first hears about whoever has taken the most (mvp-lineup R10.5)."""
    named = resolve(order.takers[0], mates).player
    first = seasons.get(named.player_id) if named is not None else None
    if first is None:
        return None
    ahead = [
        row
        for mate in mates
        if (row := seasons.get(mate.player_id)) is not None and row.penalties_taken > first.penalties_taken
    ]
    if not ahead:
        return None
    if player.player_id == first.player_id:
        return PenaltyMismatch(first, max(ahead, key=lambda row: (row.penalties_taken, row.name)))
    his = next((row for row in ahead if row.player_id == player.player_id), None)
    return PenaltyMismatch(first, his) if his is not None else None
