"""`set_squad`: the user's players, or a league-mate's, stored by player ID (mvp-lineup design C3; R1)."""

from __future__ import annotations

import datetime as dt
from collections import Counter
from collections.abc import Sequence
from typing import Literal

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel

from fantadamus.contracts.types import Role
from fantadamus.domains.facts import latest_by
from fantadamus.domains.freshness import FACTS_WINDOW
from fantadamus.domains.players.resolve import KnownPlayer
from fantadamus.domains.season.gold import known_players
from fantadamus.domains.season.silver import PlayerSeasonRow, read_player_seasons
from fantadamus.league.squads import MINE, SquadPlayer, SquadStore, cannot_field, match_squad
from fantadamus.mcp.advisor import Advisor, RefreshItem

_ROLES: tuple[Role, ...] = ("P", "D", "C", "A")


class SquadResult(BaseModel):
    status: Literal["stored", "choose", "refresh"]
    message: str
    team: str
    by_role: dict[Role, list[SquadPlayer]] = {}
    unresolved: dict[str, list[KnownPlayer]] = {}
    """Each name that failed, with the players it could be: none if nobody matched, one if he's listed
    twice."""
    warnings: list[str] = []
    refresh: list[RefreshItem] = []


def _seasons(advisor: Advisor, now: dt.datetime) -> list[PlayerSeasonRow]:
    return read_player_seasons(advisor.lake, now - FACTS_WINDOW, now)


def store_squad(advisor: Advisor, store: SquadStore, players: Sequence[str], team: str) -> SquadResult:
    """Store the squad if every name finds its one player; otherwise store nothing and say which didn't."""
    now = advisor.clock().astimezone(dt.UTC)
    rows = _seasons(advisor, now)
    if not known_players(rows, now) and advisor.collect_now({"player_season"}, now) is not None:
        now = advisor.clock().astimezone(dt.UTC)
        rows = _seasons(advisor, now)
    known = known_players(rows, now)
    if not known:
        item = advisor.refresh_item("player_season", "missing", "every player's season figures")
        message = "No player is known yet. Read their season figures as this item says, then call set_squad."
        return SquadResult(status="refresh", message=message, team=team, refresh=[item])
    match = match_squad(players, known, advisor.clubs)
    if match.unresolved:
        return SquadResult(
            status="choose",
            message="Nothing was stored. Ask the user which player each of these names means, then call "
            "set_squad again with every player. A name can give its club in brackets, as in 'Rossi (Inter)'.",
            team=team,
            unresolved=match.unresolved,
        )
    forms = latest_by(rows, now, key=lambda row: row.player_id)
    squad = [
        SquadPlayer(
            player_id=player.player_id,
            name=player.name,
            club=advisor.clubs.names[player.club],
            role=forms[player.player_id].role,
        )
        for player in match.players
    ]
    stored = store.set(advisor.user, team, squad, at=now)
    rules = advisor.rules.get(advisor.user)
    formations = (rules.rules.lineup.formations or []) if rules and rules.rules.lineup else []
    by_role = {role: [player for player in squad if player.role == role] for role in _ROLES}
    return SquadResult(
        status="stored",
        message=f"Stored {len(squad)} players for {stored.team}.",
        team=stored.team,
        by_role={role: found for role, found in by_role.items() if found},
        warnings=cannot_field(formations, Counter(player.role for player in squad)),
    )


def register(server: MCPServer, advisor: Advisor, store: SquadStore) -> None:
    """Add `set_squad` to `server`."""

    @server.tool(
        description="Store the user's squad, by the players' names, replacing the one stored under that "
        "team. A name can give its club in brackets, as in 'Rossi (Inter)', which helps when two players "
        "share a name. Without a team it's the user's own squad; with a team name, it's a league-mate's, "
        "kept apart. It stores everyone or nobody: if a name matches several players or none, it returns "
        "each such name with the players it could be, so ask the user and call it again with every player."
    )
    def set_squad(players: list[str], team: str = MINE) -> SquadResult:
        return store_squad(advisor, store, players, team)
