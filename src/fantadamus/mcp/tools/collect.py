"""`collect`: Fantadamus reads the round page now and stores its facts; each run goes to the collection log
(mvp-collect design C10; R1.2)."""

from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from fantadamus.lake.collect_log import CollectLog
from fantadamus.web.collector import Collector, CollectReport


def register(server: MCPServer, collector: Collector, log: CollectLog) -> None:
    """Add `collect` to `server`."""

    @server.tool(
        description="Read Fantacalcio-Online's round page now and store its facts: the fixtures, four "
        "outlets' chances of starting, the official lineups once out, and the odds. Without `round` it reads "
        "the next round. The report says what was stored or unchanged, or why the page couldn't be used and "
        "which facts to read through read_page instead."
    )
    def collect(round: Annotated[int, Field(ge=1, le=38)] | None = None) -> CollectReport:
        report = collector.collect(round)
        log.append(report)
        return report
