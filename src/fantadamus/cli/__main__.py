"""The `fantadamus` command line.

fantadamus serve     run the advisor's MCP server on stdio, for Claude Desktop (ADR-0005)
fantadamus collect   read the round page now and store its facts; `--report` shows the last run (C10)
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from fantadamus.core.clock import utc_now
from fantadamus.core.clubs import Clubs
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import DEFAULT_ROOT, LakeStore
from fantadamus.league.rules import RulesStore
from fantadamus.mcp.server import DEFAULT_SOURCES, build_advisor, load_allowed_hosts, load_instructions
from fantadamus.mcp.tools.compare import DEFAULT_READING_LIST, load_reading_list
from fantadamus.web.collector import Collector, CollectReport, PageReport, load_round_page
from fantadamus.web.fetch import Fetcher

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
        round_page=load_round_page(),
    )
    server.run("stdio")
    return 0


def _page_lines(page: PageReport) -> list[str]:
    line = f"{page.url}: {page.outcome}"
    if page.stored:
        line += " " + ", ".join(f"{table} {rows}" for table, rows in page.stored.items())
    if page.reason:
        line += f" ({page.reason})"
    lines = [line, *(f"  left out: {problem}" for problem in page.problems)]
    if page.for_claude:
        lines.append("  for Claude, through read_page: " + ", ".join(page.for_claude))
    return lines


def _run_lines(report: CollectReport) -> list[str]:
    return [line for page in report.pages for line in _page_lines(page)]


def _collect(args: argparse.Namespace) -> int:
    lake_root = Path(args.lake)
    log = CollectLog(lake_root.parent / "collect")  # next to the lake: data/local/collect by default
    if args.report:
        last = log.last()
        if last is None:
            print("No collection has run yet.")
            return 0
        which = f"round {last.round}" if last.round is not None else "the current round"
        print(f"Last run: {last.started_at:%Y-%m-%d %H:%M} UTC, {which}")
        print("\n".join(_run_lines(last)))
        print("Last worked:")
        for url, when in sorted(log.last_worked().items()):
            print(f"  {url}: {when:%Y-%m-%d %H:%M} UTC")
        return 0
    hosts = load_allowed_hosts(Path(args.sources))
    collector = Collector(
        fetcher=lambda: Fetcher(allowed_hosts=hosts, clock=utc_now, robots_cache=log.root / "robots"),
        lake=LakeStore(lake_root),
        clubs=Clubs.from_toml(DEFAULT_CLUBS.read_text(encoding="utf-8")),
        page=load_round_page(Path(args.reading_list)),
        allowed_hosts=hosts,
        clock=utc_now,
    )
    report = collector.collect(args.round)
    log.append(report)
    print("\n".join(_run_lines(report)))
    return 0 if all(page.outcome in {"stored", "unchanged", "switched off"} for page in report.pages) else 1


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

    collect = commands.add_parser("collect", help="read the round page now and store its facts")
    collect.add_argument("--round", type=int, help="the round to read (default: the next round)")
    collect.add_argument("--report", action="store_true", help="show the last run instead of collecting")
    collect.add_argument("--lake", default=str(DEFAULT_ROOT), help="lake root directory")
    collect.add_argument("--sources", default=str(DEFAULT_SOURCES), help="allowlist (TOML)")
    collect.add_argument("--reading-list", default=str(DEFAULT_READING_LIST), help="reading list (TOML)")
    collect.set_defaults(handler=_collect)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    code: int = args.handler(args)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
