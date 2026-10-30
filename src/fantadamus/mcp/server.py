"""The MCP servers: the advisor `fantadamus serve` gives Claude (mvp-x-or-y C13), and the walking skeleton's
two tools, which `fantadamus skeleton run` still uses (Spec 0 C10, R16.10 to R16.12)."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.types import Tool
from pydantic import AwareDatetime, BaseModel, JsonValue

from fantadamus.contracts.skeleton.tables import SkeletonRoleCount
from fantadamus.core.clock import Clock
from fantadamus.core.clubs import Clubs
from fantadamus.domains.skeleton import pipeline
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import RulesStore
from fantadamus.mcp.tools import compare, league, submit
from fantadamus.mcp.tools.compare import ReadingItem

DEFAULT_SOURCES = Path("config/sources.toml")
DEFAULT_PROMPT = Path("docs/agent-prompt.md")
_HOST = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+")

INSTRUCTIONS = (
    "Fantadamus stores facts read from allowed sources and answers from them. Submit what a page says with "
    "its URL and when you read it; then call the read tool. Never answer from the page directly."
)


class SkeletonSummary(BaseModel):
    """The gold product `skeleton_role_counts`, each row with the source URLs it was built from."""

    rows: list[SkeletonRoleCount]


def load_allowed_hosts(path: Path = DEFAULT_SOURCES) -> tuple[str, ...]:
    """The allowlist from `config/sources.toml`: a non-empty list of lower-case host names."""
    hosts = tomllib.loads(path.read_text(encoding="utf-8")).get("allowed_hosts")
    if not isinstance(hosts, list) or not hosts:
        raise ValueError(f"{path}: allowed_hosts must be a non-empty list")
    bad = [host for host in hosts if not isinstance(host, str) or not _HOST.fullmatch(host)]
    if bad:
        raise ValueError(f"{path}: allowed_hosts entries must be lower-case host names, got {bad}")
    return tuple(hosts)


def build_server(
    store: LakeStore, *, allowed_hosts: Sequence[str], clock: Clock, submitted_by: str
) -> MCPServer:
    """The server with the skeleton's submit and read tools, over the given lake."""
    server = MCPServer(name="fantadamus", instructions=INSTRUCTIONS)
    hosts = tuple(allowed_hosts)

    @server.tool()
    def submit_skeleton_rows(
        rows: list[JsonValue],
        source_url: str,
        captured_at: AwareDatetime,
        published_at: AwareDatetime | None = None,
    ) -> pipeline.SubmitResult:
        """Submit skeleton player rows read from one page.

        `source_url` must be on the allowlist of sources (a listed host or a subdomain of one); otherwise
        nothing is stored. `captured_at` is when you read the page and `published_at` when the page was
        published, both with a time zone. Each row is `{player_id, name, club, role}` with role P, D, C or
        A. Invalid rows are rejected one by one with the reason; the others are stored.
        """
        submission = pipeline.Submission(
            rows=rows, source_url=source_url, captured_at=captured_at, published_at=published_at
        )
        return pipeline.submit(store, submission, allowed_hosts=hosts, clock=clock, submitted_by=submitted_by)

    @server.tool()
    def get_skeleton_summary() -> SkeletonSummary:
        """Players per club and role, from the stored data, with the source URLs each count came from."""
        return SkeletonSummary(rows=pipeline.summary(store))

    return server


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
