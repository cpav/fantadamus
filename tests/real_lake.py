"""The answers of a copy of the owner's lake, before and after a change (mvp-store design C7; AT-8).

    python -m tests.real_lake --record    keep a snapshot of data/local, and its answers at five past times
    python -m tests.real_lake --compare   ask the snapshot again, and say whether each answer is identical
    python -m tests.real_lake --compare --rebuilt   the same, once every silver table has been rebuilt

Everything it keeps is under git-ignored `data/private/mvp-store/`: the snapshot, the questions (they name the
squad's players) and the answers. It prints times and counts only. Each question is asked of a fresh copy of
the snapshot, through the functions the tools call, with no collector: nothing is fetched, and the owner's own
`data/local` is only ever read.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import shutil
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from fantadamus.core.clock import fixed_clock
from fantadamus.core.clubs import Clubs
from fantadamus.domains.facts import rebuild
from fantadamus.domains.tables import DOMAINS
from fantadamus.lake.alert_log import AlertLog
from fantadamus.lake.calibration_store import CalibrationStore
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.lake.review_log import ReviewLog
from fantadamus.league.fielded import FieldedStore
from fantadamus.league.rules import RulesStore
from fantadamus.league.squads import MINE, SquadStore
from fantadamus.mcp.advisor import load_reading_list
from fantadamus.mcp.alerts import check_alerts
from fantadamus.mcp.calibrate import Calibrator
from fantadamus.mcp.server import make_advisor
from fantadamus.mcp.tools.cards import card_for, overview_for
from fantadamus.mcp.tools.lineup import lineup_for
from fantadamus.mcp.tools.review import review_for
from fantadamus.web.collector import CollectReport, PageReport

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "data" / "local"
PRIVATE = ROOT / "data" / "private" / "mvp-store"
SNAPSHOT = PRIVATE / "snapshot"
ANSWERS = PRIVATE / "answers"
PLAN = PRIVATE / "plan.json"
TIMES = 5
AFTER_THE_LAST_RUN = dt.timedelta(minutes=10)


@dataclass(frozen=True)
class Question:
    tool: str
    as_of: str
    """ISO 8601, in UTC."""
    args: dict[str, Any]


@dataclass(frozen=True)
class Result:
    index: int
    tool: str
    status: str
    size: int
    seconds: float
    text: str
    """The answer as JSON: it names players, so it's kept and compared, never printed."""


def _dumped(found: object) -> Any:
    if isinstance(found, BaseModel):
        return found.model_dump(mode="json")
    if dataclasses.is_dataclass(found) and not isinstance(found, type):
        return dataclasses.asdict(found)
    return found


def _status(found: Any) -> str:
    return str(found.get("status") or found.get("outcome") or "?") if isinstance(found, dict) else "?"


def ask(question: Question, home: Path, user: str) -> Any:
    """One question, of the lake under `home`, as its tool answers a replay of `as_of`."""
    as_of = dt.datetime.fromisoformat(question.as_of)
    clock = fixed_clock(as_of)
    lake = LakeStore(home / "lake")
    log = DecisionLog(home / "decisions")
    collect_log = CollectLog(home / "collect")
    rules = RulesStore(home / "league")
    squads = SquadStore(home / "league")
    advisor = make_advisor(
        lake,
        rules=rules,
        log=log,
        clubs=_clubs(),
        reading=load_reading_list(ROOT / "config" / "reading_list.toml"),
        user=user,
        clock=clock,
        collect_log=collect_log,
    )
    args = question.args
    match question.tool:
        case "compare_players":
            return advisor.compare(args["first"], args["second"], as_of=as_of)
        case "player_outlook":
            return advisor.outlook(args["player"], as_of=as_of)
        case "best_lineup":
            return lineup_for(advisor, squads, MINE, as_of)
        case "match_card":
            return card_for(advisor, squads, args["club"], as_of=as_of)
        case "round_overview":
            return overview_for(advisor, as_of=as_of)
        case "review_round":
            calibrator = Calibrator(
                lake=lake,
                log=log,
                store=CalibrationStore(home / "calibration"),
                clock=clock,
                collect_log=collect_log,
            )
            return review_for(
                advisor,
                squads,
                FieldedStore(squads.root),
                ReviewLog(home / "reviews"),
                calibrator,
                round=args["round"],
                as_advised=True,
                as_of=as_of,
            )
        case "alerts_check":
            stored = CollectReport(
                started_at=as_of,
                finished_at=as_of,
                round=None,
                pages=[
                    PageReport(
                        url="https://example.org/round", outcome="stored", stored={"official_lineups": 22}
                    )
                ],
            )
            return check_alerts(advisor, AlertLog(home / "alerts"), stored, lambda *_: None)
        case _:
            raise ValueError(f"no such tool: {question.tool}")


def questions(snapshot: Path, user: str) -> list[Question]:
    """What to ask: every logged question again at its own time, and at five times the lineup, a card for two
    clubs, the overview, four outlooks and two comparisons; then a review and an alerts' check."""
    decisions = [found for found in DecisionLog(snapshot / "decisions").read() if found.user == user]
    runs = CollectLog(snapshot / "collect").runs()
    squad = SquadStore(snapshot / "league").get(user, MINE)
    last_of_day: dict[dt.date, dt.datetime] = {}
    for decision in decisions:
        day = decision.as_of.date()
        last_of_day[day] = max(last_of_day.get(day, decision.as_of), decision.as_of)
    times = sorted(last_of_day.values())[-(TIMES - 1) :]
    if runs:
        times.append(max(run.finished_at for run in runs) + AFTER_THE_LAST_RUN)
    asked: list[Question] = []
    for decision in decisions:
        names = [player.name for player in decision.players]
        at = decision.as_of.isoformat()
        if decision.kind in ("compare", "outlooks") and len(names) == 2:
            asked.append(Question("compare_players", at, {"first": names[0], "second": names[1]}))
        elif decision.kind == "outlook" and names:
            asked.append(Question("player_outlook", at, {"player": names[0]}))
    by_role: dict[str, list[tuple[str, str]]] = {}
    for player in squad.players if squad is not None else []:
        by_role.setdefault(player.role, []).append((player.name, player.club))
    for moment in times:
        at = moment.isoformat()
        asked.append(Question("best_lineup", at, {}))
        asked.append(Question("round_overview", at, {}))
        for role in ("A", "P"):
            pair = by_role.get(role, [])[:2]
            if len(pair) == 2:
                asked.append(Question("compare_players", at, {"first": pair[0][0], "second": pair[1][0]}))
            if pair:
                asked.append(Question("match_card", at, {"club": pair[0][1]}))
        for role in ("P", "D", "C", "A"):
            for name, _ in by_role.get(role, [])[:1]:
                asked.append(Question("player_outlook", at, {"player": name}))
        asked.append(Question("alerts_check", at, {}))
    if times:
        for round in sorted({decision.round for decision in decisions})[-2:]:
            asked.append(Question("review_round", times[-1].isoformat(), {"round": round}))
    return asked_once(asked)


def asked_once(asked: Sequence[Question]) -> list[Question]:
    """Each question once, in order: a logged question can be one of the five times' own."""
    seen: set[str] = set()
    kept = []
    for question in asked:
        key = json.dumps(dataclasses.asdict(question), sort_keys=True)
        if key not in seen:
            seen.add(key)
            kept.append(question)
    return kept


def run(snapshot: Path, plan: Sequence[Question], user: str) -> list[Result]:
    """Each question's answer, asked of a copy of the snapshot of its own: a replay may log, and the next
    question mustn't see it."""
    results = []
    for index, question in enumerate(plan):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder) / "local"
            shutil.copytree(snapshot, home)
            started = time.process_time()
            found = _dumped(ask(question, home, user))
            seconds = time.process_time() - started
        text = json.dumps(found, sort_keys=True, ensure_ascii=False, indent=1, default=str)
        results.append(Result(index, question.tool, _status(found), len(text.encode()), seconds, text))
    return results


def report_lines(results: Sequence[Result], same: Sequence[bool] | None = None) -> list[str]:
    """One line for each answer: its number, tool, status, size and time, and whether it's identical. Never a
    name or a number from the answer itself."""
    lines = []
    for position, result in enumerate(results):
        line = (
            f"{result.index:02d} {result.tool} {result.status}: {result.size:,} bytes, {result.seconds:.2f} s"
        )
        if same is not None:
            line += ", identical" if same[position] else ", DIFFERENT"
        lines.append(line)
    total = sum(result.seconds for result in results)
    lines.append(f"{len(results)} answers, {total:.1f} CPU-seconds")
    if same is not None:
        lines.append(f"{sum(same)} identical, {len(same) - sum(same)} different")
    return lines


def _load_plan() -> list[Question]:
    return [Question(**entry) for entry in json.loads(PLAN.read_text(encoding="utf-8"))]


def record(user: str) -> int:
    if ANSWERS.exists():
        print(f"Already recorded: remove {PRIVATE.relative_to(ROOT)} to record again.")
        return 1
    PRIVATE.mkdir(parents=True, exist_ok=True)
    shutil.copytree(LOCAL, SNAPSHOT)
    plan = questions(SNAPSHOT, user)
    PLAN.write_text(
        json.dumps([dataclasses.asdict(question) for question in plan], indent=1), encoding="utf-8"
    )
    results = run(SNAPSHOT, plan, user)
    ANSWERS.mkdir()
    for result in results:
        (ANSWERS / f"{result.index:02d}-{result.tool}.json").write_text(result.text, encoding="utf-8")
    print("\n".join(report_lines(results)))
    return 0


def _clubs() -> Clubs:
    return Clubs.from_toml((ROOT / "config" / "clubs.toml").read_text(encoding="utf-8"))


def rebuilt_copy(snapshot: Path, folder: Path) -> Path:
    """A copy of the snapshot whose silver tables have all been rebuilt from bronze: the lake as it will be
    once it has stored again, in month files."""
    home = folder / "rebuilt"
    shutil.copytree(snapshot, home)
    lake, clubs = LakeStore(home / "lake"), _clubs()
    rows = sum(rebuild(lake, domain, clubs) for domain in DOMAINS)
    print(f"Rebuilt {len(DOMAINS)} tables, {rows:,} rows")
    return home


def compare(user: str, rebuilt: bool = False) -> int:
    if not ANSWERS.exists():
        print("Nothing recorded yet: run `python -m tests.real_lake --record` first.")
        return 1
    with tempfile.TemporaryDirectory() as folder:
        snapshot = rebuilt_copy(SNAPSHOT, Path(folder)) if rebuilt else SNAPSHOT
        results = run(snapshot, _load_plan(), user)
    same = [
        (ANSWERS / f"{result.index:02d}-{result.tool}.json").read_text(encoding="utf-8") == result.text
        for result in results
    ]
    print("\n".join(report_lines(results, same)))
    return 0 if all(same) else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", action="store_true", help="keep the snapshot and its answers")
    mode.add_argument("--compare", action="store_true", help="ask again and compare")
    parser.add_argument("--rebuilt", action="store_true", help="compare once every table is rebuilt")
    parser.add_argument("--user", default="owner", help="whose squad and rules")
    args = parser.parse_args(argv)
    return record(args.user) if args.record else compare(args.user, args.rebuilt)


if __name__ == "__main__":
    raise SystemExit(main())
