"""`set_league_rules`: the user's bonuses and maluses, set the first time they ask and whenever they change
(design C9; R12.2)."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from fantadamus.contracts.xy.league import LeagueRules
from fantadamus.core.clock import Clock
from fantadamus.league.rules import RulesStore, StoredRules


def register(server: MCPServer, store: RulesStore, *, user: str, clock: Clock) -> None:
    """Add `set_league_rules` to `server`, storing the rules of `user`."""

    @server.tool(
        description="Set this user's league rules: the bonus and malus for each event. Ask the user for "
        "every value first (compare_players lists them, with the Fantacalcio Classic values as the starting "
        "choice), and call it again whenever their league changes. Bonuses are 0 to 10, maluses -10 to 0; "
        "a value out of range is rejected with the reason."
    )
    def set_league_rules(rules: LeagueRules) -> StoredRules:
        return store.set(user, rules, at=clock())
