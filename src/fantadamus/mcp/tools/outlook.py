"""`player_outlook`: one player's forecast for the round, of any role, on the same steps as `compare_players`
(mvp-roles design C10; R5)."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from pydantic import AwareDatetime

from fantadamus.mcp.tools.compare import Advisor, CompareResult


def register(server: MCPServer, advisor: Advisor) -> None:
    """Add `player_outlook` to `server`."""

    @server.tool(
        description='Answer "Will he start? Is he worth it?" for one player of any role for the next round, '
        "from the stored facts. It returns one of: the setup step (no league rules yet: ask the user, then "
        "call set_league_rules); candidates (the name matches several players: ask which); a refresh plan "
        "(facts missing or stale: read the listed pages, submit with the named tools, then call again); or "
        "'outlook', his chance of starting with each outlet's view and his rivals, what he's worth if he "
        "starts, his chance to score or a keeper's clean sheet, his form and match, how it has moved, when "
        "it was updated and the sources. Set odds_unavailable only after looking for the match odds on the "
        "listed pages and finding none. as_of replays an earlier question."
    )
    def player_outlook(
        player: str, as_of: AwareDatetime | None = None, odds_unavailable: bool = False
    ) -> CompareResult:
        return advisor.outlook(player, as_of=as_of, odds_unavailable=odds_unavailable)
