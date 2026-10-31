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
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import RulesStore
from fantadamus.mcp.tools import compare, league, submit
from fantadamus.mcp.tools.compare import ReadingItem

DEFAULT_SOURCES = Path("config/sources.toml")
DEFAULT_PROMPT = Path("docs/agent-prompt.md")
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
) -> MCPServer:
    """The server Claude Desktop runs: `compare_players`, `set_league_rules` and the submit tools (R13.1)."""
    server = AdvisorServer(name="fantadamus", instructions=instructions)
    submit.register(server, lake, allowed_hosts=allowed_hosts, clock=clock, submitted_by=user, clubs=clubs)
    league.register(server, rules, user=user, clock=clock)
    advisor = compare.Advisor(
        lake=lake, rules=rules, log=log, clubs=clubs, reading=reading, user=user, clock=clock
    )
    compare.register(server, advisor)
    return server
