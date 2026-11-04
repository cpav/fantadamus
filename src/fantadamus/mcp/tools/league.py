"""`set_league_rules`: the user's bonuses and maluses, set the first time they ask and whenever they change
(design C9; R12.2), and what a lineup needs (mvp-lineup R2)."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from fantadamus.contracts.xy.league import LeagueRules
from fantadamus.core.clock import Clock
from fantadamus.league.rules import RulesStore, StoredRules, with_stored_lineup


def register(server: MCPServer, store: RulesStore, *, user: str, clock: Clock) -> None:
    """Add `set_league_rules` to `server`, storing the rules of `user`."""

    @server.tool(
        description="Set this user's league rules: the bonus and malus for each event, and under `lineup` "
        "what a lineup needs. Ask the user for every value first (compare_players lists the bonuses, with "
        "the Fantacalcio Classic values as the starting choice), and call it again whenever their league "
        "changes. Bonuses are 0 to 10, maluses -10 to 0; an impossible value is rejected with the reason. "
        "Lineup settings left out keep their stored values."
    )
    def set_league_rules(rules: LeagueRules) -> StoredRules:
        stored = store.get(user)
        return store.set(user, with_stored_lineup(rules, stored.rules if stored else None), at=clock())
