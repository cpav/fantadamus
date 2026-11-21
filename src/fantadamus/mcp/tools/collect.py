"""`collect`: Fantadamus reads its pages now and stores their facts; each run goes to the collection log
(mvp-collect design C10; R1.2; mvp-roles C4). It takes any fact the collector reads (mvp-fixes R2)."""

from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from fantadamus.lake.collect_log import CollectLog
from fantadamus.web.collector import PAGE_NAMES, CollectFact, Collector, CollectReport

DESCRIPTION = (
    "Read pages now and store their facts. The pages: "
    + "; ".join(PAGE_NAMES.values())
    + ". Without `fact` it reads the round page and Fantacalcio.it's statistics, penalty-takers and table "
    "pages; `fact` reads only the page that carries it, any of the facts listed. Without `round` it reads "
    "the next round. The report says, per page, what was stored or unchanged, or why the page couldn't be "
    "used and which facts to read through read_page instead; a page that got no answer is tried again at the "
    "next run."
)


def register(server: MCPServer, collector: Collector, log: CollectLog) -> None:
    """Add `collect` to `server`."""

    @server.tool(description=DESCRIPTION)
    def collect(
        round: Annotated[int, Field(ge=1, le=38)] | None = None,
        fact: CollectFact | None = None,
    ) -> CollectReport:
        report = collector.collect(round, [fact] if fact else None)
        log.append(report)
        return report
