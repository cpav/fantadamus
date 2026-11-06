"""The `fantadamus` command line.

fantadamus serve run the advisor's MCP server on stdio, for Claude Desktop (ADR-0005) fantadamus collect read
the round page now and store its facts; `--due` only if something is past its cadence (the schedule, C7), and
score a finished round; `--report` shows the last run (C10) fantadamus calibrate print a finished round's
report, scoring it if it hasn't been; `--again` recomputes it"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from fantadamus.core.clock import utc_now
from fantadamus.core.clubs import Clubs
from fantadamus.domains.calibration import render
from fantadamus.lake.calibration_store import CalibrationStore
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import DEFAULT_ROOT, LakeStore
from fantadamus.league.rules import RulesStore
from fantadamus.mcp.advisor import DEFAULT_READING_LIST, load_reading_list
from fantadamus.mcp.calibrate import Calibrator
from fantadamus.mcp.server import DEFAULT_SOURCES, build_advisor, load_allowed_hosts, load_instructions
from fantadamus.web.cadence import collect_due
from fantadamus.web.collector import FACTS, Collector, CollectReport, PageReport, load_collector
from fantadamus.web.fetch import Fetcher

DEFAULT_CLUBS = Path("config/clubs.toml")


def _serve(args: argparse.Namespace) -> int:
    server = build_advisor(
        LakeStore(Path(args.lake)),
        allowed_hosts=load_allowed_hosts(Path(args.sources)),
        clubs=_clubs(),
        rules=RulesStore(),
        log=DecisionLog(),
        reading=load_reading_list(),
        user=args.user,
        clock=utc_now,
        instructions=load_instructions(),
        collector=load_collector(),
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


def _collector(args: argparse.Namespace, log: CollectLog) -> Collector:
    hosts = load_allowed_hosts(Path(args.sources))
    return Collector(
        fetcher=lambda: Fetcher(allowed_hosts=hosts, clock=utc_now, robots_cache=log.root / "robots"),
        lake=LakeStore(Path(args.lake)),
        clubs=_clubs(),
        config=load_collector(Path(args.reading_list)),
        allowed_hosts=hosts,
        clock=utc_now,
    )


def _clubs() -> Clubs:
    return Clubs.from_toml(DEFAULT_CLUBS.read_text(encoding="utf-8"))


def _calibrator(args: argparse.Namespace) -> Calibrator:
    lake_root = Path(args.lake)
    log = CollectLog(lake_root.parent / "collect")
    return Calibrator(
        lake=LakeStore(lake_root),
        log=DecisionLog(lake_root.parent / "decisions"),
        store=CalibrationStore(lake_root.parent / "calibration"),
        clock=utc_now,
        collector=_collector(args, log),
        collect_log=log,
    )


def _calibrate(args: argparse.Namespace) -> int:
    report = _calibrator(args).report(args.round, again=args.again)
    if report is None:
        print(f"Round {args.round} hasn't finished, or the lake doesn't know it.")
        return 1
    print(render(report))
    return 0


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
    collector = _collector(args, log)
    if args.due:
        due = collect_due(collector, log)
        calibrator = _calibrator(args)
        scored = calibrator.if_due(calibrator.clock())
        if scored is not None:
            print(f"Round {scored.round} scored.")
        if due is None:
            print("Nothing due.")
            return 0
        report = due
        print("Due: " + ", ".join(report.due))
    else:
        report = collector.collect(args.round, [args.fact] if args.fact else None)
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

    collect = commands.add_parser(
        "collect", help="read the round and statistics pages now and store their facts"
    )
    which = collect.add_mutually_exclusive_group()
    which.add_argument("--round", type=int, help="the round to read (default: the next round)")
    which.add_argument("--due", action="store_true", help="read only if a fact is past its cadence (launchd)")
    which.add_argument("--fact", choices=FACTS, help="read only the page that carries this fact")
    collect.add_argument("--report", action="store_true", help="show the last run instead of collecting")
    collect.add_argument("--lake", default=str(DEFAULT_ROOT), help="lake root directory")
    collect.add_argument("--sources", default=str(DEFAULT_SOURCES), help="allowlist (TOML)")
    collect.add_argument("--reading-list", default=str(DEFAULT_READING_LIST), help="reading list (TOML)")
    collect.set_defaults(handler=_collect)

    calibrate = commands.add_parser("calibrate", help="print a finished round's report on the forecasts")
    calibrate.add_argument("--round", type=int, required=True, help="the round")
    calibrate.add_argument("--again", action="store_true", help="score it again, reading the page again")
    calibrate.add_argument("--lake", default=str(DEFAULT_ROOT), help="lake root directory")
    calibrate.add_argument("--sources", default=str(DEFAULT_SOURCES), help="allowlist (TOML)")
    calibrate.add_argument("--reading-list", default=str(DEFAULT_READING_LIST), help="reading list (TOML)")
    calibrate.set_defaults(handler=_calibrate)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    code: int = args.handler(args)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
