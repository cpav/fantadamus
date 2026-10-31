"""The MCP server `fantadamus serve` gives Claude: the advisor's tools (mvp-x-or-y C13)."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import Tool

from fantadamus.core.clock import Clock
from fantadamus.core.clubs import Clubs
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import RulesStore
from fantadamus.mcp.tools import collect, compare, league, pages, submit
from fantadamus.mcp.tools.compare import ReadingItem
from fantadamus.web.collector import Collector, RoundPageConfig
from fantadamus.web.fetch import Fetcher

DEFAULT_SOURCES = Path("config/sources.toml")
DEFAULT_PROMPT = Path("docs/agent-prompt.md")
COLLECT_BUDGET = 60.0  # seconds a collection may take when a question needs it (mvp-collect R1.3)
READ_PAGE_BLOCK = 3600.0  # seconds read_page leaves a host alone after it blocks (R2.3)
_HOST = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+")


def load_allowed_hosts(path: Path = DEFAULT_SOURCES) -> tuple[str, ...]:
    """The allowlist from `config/sources.toml`: a non-empty list of lower-case host names."""
    hosts = tomllib.loads(path.read_text(encoding="utf-8")).get("allowed_hosts")
    if not isinstance(hosts, list) or not hosts:
        raise ValueError(f"{path}: allowed_hosts must be a non-empty list")
    bad = [host for host in hosts if not isinstance(host, str) or not _HOST.fullmatch(host)]
    if bad:
        raise ValueError(f"{path}: allowed_hosts entries must be lower-case host names, got {bad}")
    return tuple(hosts)


def inline_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """The schema with every local `$ref` replaced by its definition, and no `$defs` left."""
    definitions: dict[str, Any] = schema.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, list):
            return [resolve(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            definition = resolve(definitions[node["$ref"].removeprefix("#/$defs/")])
            return definition | {key: resolve(value) for key, value in node.items() if key != "$ref"}
        return {key: resolve(value) for key, value in node.items() if key != "$defs"}

    resolved: dict[str, Any] = resolve(schema)
    return resolved


class AdvisorServer(MCPServer):
    """Serves each tool's input schema whole. In the first test round Claude Desktop guessed the shape of
    payloads it could only reach through `$ref`s, and every submission was rejected."""

    async def list_tools(self) -> list[Tool]:
        tools = await super().list_tools()
        return [tool.model_copy(update={"input_schema": inline_refs(tool.input_schema)}) for tool in tools]


def load_instructions(path: Path = DEFAULT_PROMPT) -> str:
    """The agent prompt as the server's instructions: everything after its `---` line (R13.2)."""
    return path.read_text(encoding="utf-8").split("\n---\n", 1)[1].strip() + "\n"


def build_advisor(
    lake: LakeStore,
    *,
    allowed_hosts: Sequence[str],
    clubs: Clubs,
    rules: RulesStore,
    log: DecisionLog,
    reading: dict[str, ReadingItem],
    user: str,
    clock: Clock,
    instructions: str,
    round_page: RoundPageConfig,
) -> MCPServer:
    """The server Claude Desktop runs: `compare_players`, `set_league_rules`, the submit tools (R13.1), and
    `collect` and `read_page` (mvp-collect C10, C3.2). The collection log and robots.txt cache sit next to the
    lake, as for `fantadamus collect`."""
    server = AdvisorServer(name="fantadamus", instructions=instructions)
    hosts = tuple(allowed_hosts)
    collect_dir = lake.root.parent / "collect"
    collect_log = CollectLog(collect_dir)

    def run_fetcher() -> Fetcher:  # a new one per run: a host that blocks is stopped for that run only
        return Fetcher(
            allowed_hosts=hosts, clock=clock, robots_cache=collect_dir / "robots", budget=COLLECT_BUDGET
        )

    collector = Collector(
        fetcher=run_fetcher, lake=lake, clubs=clubs, page=round_page, allowed_hosts=hosts, clock=clock
    )
    page_fetcher = Fetcher(
        allowed_hosts=hosts, clock=clock, robots_cache=collect_dir / "robots", block_for=READ_PAGE_BLOCK
    )
    submit.register(server, lake, allowed_hosts=hosts, clock=clock, submitted_by=user, clubs=clubs)
    league.register(server, rules, user=user, clock=clock)
    collect.register(server, collector, collect_log)
    pages.register(server, pages.PageReader(reading, page_fetcher))
    advisor = compare.Advisor(
        lake=lake,
        rules=rules,
        log=log,
        clubs=clubs,
        reading=reading,
        user=user,
        clock=clock,
        collector=collector,
        collect_log=collect_log,
    )
    compare.register(server, advisor)
    return server
