"""`compare_players`: "X or Y?" for two players of one role (design C10; mvp-roles design C9). The advisor
behind it is in `mcp/advisor.py`."""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from pydantic import AwareDatetime

from fantadamus.mcp.advisor import Advisor, CompareResult


def register(server: MCPServer, advisor: Advisor) -> None:
    """Add `compare_players` to `server`."""

    @server.tool(
        description='Answer "X or Y?" for two players for the next round, from the stored facts. It '
        "returns one of: the setup step (no league rules yet: ask the user, then call set_league_rules); "
        "candidates (a name matches several players: ask which); a refresh plan (facts missing or stale: "
        "read the listed pages, submit with the named tools, then call again); 'answer', the verdict for two "
        "players of one role with its breakdown; or 'outlooks', each player's breakdown and no verdict for "
        "two roles, since that choice is the formation call. Set odds_unavailable only after looking for the "
        "match odds on the listed "
        "pages and finding none: the answer then uses regressed team form and says so. as_of replays an "
        "earlier question."
    )
    def compare_players(
        first: str, second: str, as_of: AwareDatetime | None = None, odds_unavailable: bool = False
    ) -> CompareResult:
        return advisor.compare(first, second, as_of=as_of, odds_unavailable=odds_unavailable)
