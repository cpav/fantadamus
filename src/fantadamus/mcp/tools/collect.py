"""`collect`: Fantadamus reads the round and statistics pages now and stores their facts; each run goes to the
collection log (mvp-collect design C10; R1.2; mvp-roles C4)."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from fantadamus.lake.collect_log import CollectLog
from fantadamus.web.collector import Collector, CollectReport


def register(server: MCPServer, collector: Collector, log: CollectLog) -> None:
    """Add `collect` to `server`."""

    @server.tool(
        description="Read the pages now and store their facts: Fantacalcio-Online's round page (the "
        "fixtures, four outlets' chances of starting, the official lineups once out, and the odds) and "
        "Fantacalcio.it's statistics page (every player's season figures). Without `round` it reads the next "
        "round; `fact` reads only the page that carries it. The report says, per page, what was stored or "
        "unchanged, or why the page couldn't be used and which facts to read through read_page instead."
    )
    def collect(
        round: Annotated[int, Field(ge=1, le=38)] | None = None,
        fact: Literal["fixtures", "probable_lineups", "official_lineups", "match_odds", "player_season"]
        | None = None,
    ) -> CollectReport:
        report = collector.collect(round, [fact] if fact else None)
        log.append(report)
        return report
