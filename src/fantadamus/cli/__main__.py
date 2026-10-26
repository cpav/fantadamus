"""The `fantadamus` command line.

fantadamus skeleton run   submit the skeleton fixture through the MCP tools, read gold back, print it,
                          and compare it with a golden file (C10, `make skeleton`)
fantadamus serve          run the advisor's MCP server on stdio, for Claude Desktop (ADR-0005)
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from mcp import Client
from mcp.server.mcpserver import MCPServer
from pydantic import AwareDatetime, BaseModel, JsonValue

from fantadamus.core.clock import utc_now
from fantadamus.core.clubs import Clubs
from fantadamus.domains.skeleton.pipeline import SubmitResult
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import DEFAULT_ROOT, LakeStore
from fantadamus.league.rules import RulesStore
from fantadamus.mcp.server import (
    DEFAULT_SOURCES,
    SkeletonSummary,
    build_advisor,
    build_server,
    load_allowed_hosts,
    load_instructions,
)
from fantadamus.mcp.tools.compare import load_reading_list

SKELETON_FIXTURE = Path("tests/fixtures/skeleton/rows.json")
SKELETON_SOURCES = Path("tests/fixtures/skeleton/sources.toml")
DEFAULT_CLUBS = Path("config/clubs.toml")
DEFAULT_USER = "local"


class SkeletonFixture(BaseModel):
    """A submission as a client would make it: where and when the rows were read, and the rows."""

    source_url: str
    published_at: AwareDatetime | None = None
    captured_at: AwareDatetime
    rows: list[JsonValue]


def render_rows(summary: SkeletonSummary) -> str:
    """Gold rows in the golden file's form: sorted keys, two-space indent, trailing newline."""
    return json.dumps(summary.model_dump(mode="json")["rows"], indent=2, sort_keys=True) + "\n"


async def run_skeleton(server: MCPServer, fixture: SkeletonFixture) -> tuple[SubmitResult, SkeletonSummary]:
    """Submit the fixture through the MCP submit tool and read gold back through the read tool."""
    async with Client(server, raise_exceptions=True) as client:
        arguments = fixture.model_dump(mode="json", exclude_none=True)
        submitted = await client.call_tool("submit_skeleton_rows", arguments)
        summary = await client.call_tool("get_skeleton_summary", {})
    return SubmitResult.model_validate(submitted.structured_content), SkeletonSummary.model_validate(
        summary.structured_content
    )


def _skeleton(args: argparse.Namespace) -> int:
    fixture = SkeletonFixture.model_validate_json(Path(args.fixture).read_text(encoding="utf-8"))
    server = build_server(
        LakeStore(Path(args.lake)),
        allowed_hosts=load_allowed_hosts(Path(args.sources)),
        clock=utc_now,
        submitted_by=args.user,
    )
    result, summary = asyncio.run(run_skeleton(server, fixture))
    if result.rejected:
        print(f"rejected: {result.model_dump_json()}", file=sys.stderr)
        return 1
    print(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
    if args.golden:
        golden_path = Path(args.golden)
        expected, actual = golden_path.read_text(encoding="utf-8"), render_rows(summary)
        if actual != expected:
            diff = difflib.unified_diff(
                expected.splitlines(keepends=True), actual.splitlines(keepends=True), str(golden_path), "gold"
            )
            print(f"gold differs from the golden file {golden_path}:\n{''.join(diff)}", file=sys.stderr)
            return 1
    return 0


def _serve(args: argparse.Namespace) -> int:
    server = build_advisor(
        LakeStore(Path(args.lake)),
        allowed_hosts=load_allowed_hosts(Path(args.sources)),
        clubs=Clubs.from_toml(DEFAULT_CLUBS.read_text(encoding="utf-8")),
        rules=RulesStore(),
        log=DecisionLog(),
        reading=load_reading_list(),
        user=args.user,
        clock=utc_now,
        instructions=load_instructions(),
    )
    server.run("stdio")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="fantadamus", description="Fantadamus, a Fantacalcio advisor.")
    commands = parser.add_subparsers(dest="command", required=True)

    skeleton = commands.add_parser("skeleton", help="the walking skeleton").add_subparsers(
        dest="action", required=True
    )
    run = skeleton.add_parser("run", help="submit the fixture, read gold back, compare with a golden file")
    run.add_argument("--fixture", default=str(SKELETON_FIXTURE), help="submission to send (JSON)")
    run.add_argument("--sources", default=str(SKELETON_SOURCES), help="allowlist (TOML)")
    run.add_argument("--lake", default=str(DEFAULT_ROOT), help="lake root directory")
    run.add_argument("--golden", help="golden file the gold rows must equal")
    run.add_argument("--user", default=DEFAULT_USER, help="pseudonymous user ID recorded as submitted_by")
    run.set_defaults(handler=_skeleton)

    serve = commands.add_parser("serve", help="run the MCP server on stdio")
    serve.add_argument("--sources", default=str(DEFAULT_SOURCES), help="allowlist (TOML)")
    serve.add_argument("--lake", default=str(DEFAULT_ROOT), help="lake root directory")
    serve.add_argument(
        "--user", default="owner", help="pseudonymous user ID: whose league rules, who submitted"
    )
    serve.set_defaults(handler=_serve)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    code: int = args.handler(args)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
