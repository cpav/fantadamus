"""The MCP server. In Spec 0 it exposes only the walking skeleton's two tools (C10, R16.10 to R16.12)."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Sequence
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from pydantic import AwareDatetime, BaseModel, JsonValue

from fantadamus.contracts.skeleton.tables import SkeletonRoleCount
from fantadamus.core.clock import Clock
from fantadamus.domains.skeleton import pipeline
from fantadamus.lake.duckdb_store import LakeStore

DEFAULT_SOURCES = Path("config/sources.toml")
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
