"""The `fantadamus` command line.

fantadamus serve   run the advisor's MCP server on stdio, for Claude Desktop (ADR-0005)
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from fantadamus.core.clock import utc_now
from fantadamus.core.clubs import Clubs
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import DEFAULT_ROOT, LakeStore
from fantadamus.league.rules import RulesStore
from fantadamus.mcp.server import DEFAULT_SOURCES, build_advisor, load_allowed_hosts, load_instructions
from fantadamus.mcp.tools.compare import load_reading_list

DEFAULT_CLUBS = Path("config/clubs.toml")


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
