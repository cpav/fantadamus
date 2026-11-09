"""`set_league_rules`: the user's league rules, set the first time they ask and whenever they change (design
C9; R12.2), with what a lineup needs (mvp-lineup R2); it reads back what's priced and what's left out
(mvp-rules R4.2)."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from fantadamus.contracts.xy.league import LeagueRules
from fantadamus.core.clock import Clock
from fantadamus.league.rules import RulesStore, StoredRules, left_out, priced, with_stored_lineup


class SavedRules(StoredRules):
    """The rules as stored, and what to read back to the user."""

    priced: list[str]
    """Every event and formula rule the numbers count, in plain words."""
    left_out: list[str]
    """Rules the league uses that the numbers leave out, each with what it needs."""


def register(server: MCPServer, store: RulesStore, *, user: str, clock: Clock) -> None:
    """Add `set_league_rules` to `server`, storing the rules of `user`."""

    @server.tool(
        description="Set this user's league rules: one row in `events` for each thing the league scores, "
        "`formula_rules` for modifiers and the captain, and under `lineup` what a lineup needs; a rule that "
        "fits neither goes in `lineup.other_rules`, by name with what it needs. Take the values from the "
        "user, their league profile or their rulebook, never a guess; the setup step offers Classic's "
        "values and ready-made entries. An event left out isn't scored. An impossible value is rejected "
        "with the reason, and nothing is stored. Lineup settings left out keep their stored values. It "
        "returns `priced` and `left_out`: read both back to the user."
    )
    def set_league_rules(rules: LeagueRules) -> SavedRules:
        stored = store.get(user)
        saved = store.set(user, with_stored_lineup(rules, stored.rules if stored else None), at=clock())
        return SavedRules(**saved.model_dump(), priced=priced(saved.rules), left_out=left_out(saved.rules))
