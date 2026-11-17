"""A season around a synthetic round, for timing at season size (mvp-store design C7; the requirements'
glossary): the round page's 1,000 stored reads, 60 of them in the answer's window, each 2,200 rows of
invented matches with their odds, and official lineups in a fifth of them; 250 reads of the statistics page,
500 invented players each; two reads of each round's ratings; 3,000 collection runs and 1,000 answers.

DuckDB writes it natively: month files, `_table.json` as the lake keeps it, and no bronze, since a table in
step never looks at it. The round's own rows stay after the season's in their month, as the newest. Nothing
here is about a real club or player."""

from __future__ import annotations

import datetime as dt
import tempfile
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from fantadamus.domains.availability.silver import OFFICIAL_LINEUPS, OUTLET_VIEWS
from fantadamus.domains.facts import Domain
from fantadamus.domains.freshness import FACTS_WINDOW
from fantadamus.domains.odds.silver import ODDS
from fantadamus.domains.ratings.silver import MATCH_RATINGS
from fantadamus.domains.season.silver import SEASON_STATS
from fantadamus.lake.collect_log import CollectLog
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.lake.months import Description, month_of
from fantadamus.web.collector import CollectReport, PageReport
from tests.collect_harness import ROUND_ROUTE, STATS_ROUTE
from tests.lineup_harness import a_round
from tests.xy_harness import NOW

BASE = "https://example.org"
READS = 1_000
IN_WINDOW = 60
MATCHES = 10
OUTLETS = ["Fantacalcio.it", "Gazzetta", "SOS Fanta", "Sky"]
LISTED = 55
"""Players an outlet lists for a match: 10 matches, 4 outlets and 55 players are 2,200 rows a read."""
STATISTICS = 250
PLAYERS = 500
RATED_ROUNDS = 38
DESKS = ["Fantacalcio.it", "Roma", "Torino"]
RUNS = 3_000
ANSWERS = 1_000

ROUND_PAGE = (
    "SELECT $url AS source_url, captured_at, content_sha256, home, away, outlet, "
    "CASE WHEN player < $listed // 2 THEN home ELSE away END AS club, "
    "'Giocatore ' || (match * 100 + player) AS name, 'C' AS role, "
    "((read * 7 + player * 13) % 100)::DOUBLE AS percent, false AS unavailable "
    "FROM (SELECT captured_at, read, match, $outlets[outlet + 1] AS outlet, "
    "md5('a' || read || match || outlet) || md5('b' || read || match || outlet) AS content_sha256, "
    "'c' || lpad((2 * match)::VARCHAR, 2, '0') AS home, "
    "'c' || lpad((2 * match + 1)::VARCHAR, 2, '0') AS away "
    "FROM (SELECT unnest($times) AS captured_at, generate_subscripts($times, 1) - 1 AS read), "
    "range($matches) m(match), range(len($outlets)) o(outlet)) AS submission, range($listed) p(player) "
    "ORDER BY captured_at, match, submission.outlet, player"
)
ODDS_ROWS = (
    "SELECT $url AS source_url, captured_at, md5('o' || read || match) || md5('p' || read || match) "
    "AS content_sha256, "
    "'c' || lpad((2 * match)::VARCHAR, 2, '0') AS home, "
    "'c' || lpad((2 * match + 1)::VARCHAR, 2, '0') AS away, "
    "'Banco Esempio' AS bookmaker, 0.40 + (read % 7) / 100 AS p_home, "
    "0.28 AS p_draw, 0.32 - (read % 7) / 100 AS p_away, 0.55 AS p_over, 0.50 AS p_btts "
    "FROM (SELECT unnest($times) AS captured_at, generate_subscripts($times, 1) - 1 AS read), "
    "range($matches) m(match) ORDER BY captured_at, match"
)
OFFICIAL_ROWS = (
    "SELECT $url AS source_url, captured_at, md5('l' || read || match) || md5('m' || read || match) "
    "AS content_sha256, "
    "'c' || lpad((2 * match)::VARCHAR, 2, '0') AS home, "
    "'c' || lpad((2 * match + 1)::VARCHAR, 2, '0') AS away, "
    "CASE WHEN player < 11 THEN home ELSE away END AS club, "
    "'Giocatore ' || (match * 100 + player) AS name, 'starter' AS status, 0 AS unnamed_starters "
    "FROM (SELECT unnest($times) AS captured_at, generate_subscripts($times, 1) - 1 AS read), "
    "range($matches) m(match), range(22) p(player) WHERE read % 5 = 0 "
    "ORDER BY captured_at, match, player"
)
STATISTICS_ROWS = (
    "SELECT $url AS source_url, captured_at, md5('s' || read) || md5('t' || read) AS content_sha256, "
    "100000 + player AS player_id, 'Calciatore ' || player AS name, "
    "'c' || lpad((player % (2 * $matches))::VARCHAR, 2, '0') AS club, 'C' AS role, NULL AS mantra_role, "
    "10 + read % 3 AS appearances, 9 AS rated_appearances, 6.0 + (player % 5) / 10 AS average_rating, "
    "player % 4 AS goals, player % 3 AS assists, player % 2 AS yellow_cards, 0 AS penalties_scored, "
    "0 AS penalties_taken, NULL AS goals_conceded, NULL AS fantasy_average, NULL AS penalties_saved, "
    "NULL AS red_cards "
    "FROM (SELECT unnest($times) AS captured_at, generate_subscripts($times, 1) - 1 AS read), "
    "range($players) p(player) ORDER BY captured_at, player"
)
RATING_ROWS = (
    "SELECT 'https://example.org/voti/' || (read // 2 + 1) || '-giornata' AS source_url, captured_at, "
    "md5('r' || read) || md5('v' || read) AS content_sha256, read // 2 + 1 AS round, "
    "$homes[match + 1] AS home, $aways[match + 1] AS away, "
    "CASE WHEN player < 30 THEN home ELSE away END AS club, "
    "'GIOCATORE' || player || ' ' || upper(club[1]) || '.' AS name, 'C' AS role, false AS came_on, "
    "NULL AS minutes, $desks[desk + 1] AS desk, 6.0 + ((player + desk + read) % 3) / 2 AS rating "
    "FROM (SELECT unnest($times) AS captured_at, generate_subscripts($times, 1) - 1 AS read), "
    "range(len($homes)) m(match), range(60) p(player), range(len($desks)) d(desk) "
    "ORDER BY captured_at, match, player, desk"
)
"""The season's rows, as static SQL with parameters: invented matches, `c00` v `c01` and on, and the real
round's clubs only in the ratings, under invented names."""


@dataclass(frozen=True)
class Season:
    """What the season added: rows by table, collection runs and answers."""

    rows: dict[str, int]
    runs: int
    answers: int


def read_times() -> list[dt.datetime]:
    """The round page's stored reads, oldest first: every six hours before the window, and 60 spread over
    it, the last two hours before the round's own read."""
    start = NOW - FACTS_WINDOW
    step = (FACTS_WINDOW - dt.timedelta(hours=2)) / IN_WINDOW
    window = [start + (index + 1) * step for index in range(IN_WINDOW)]
    older = [start - (index + 1) * dt.timedelta(hours=6) for index in range(READS - IN_WINDOW)]
    return sorted([*older, *window])


def _statistics_times() -> list[dt.datetime]:
    return sorted(NOW - dt.timedelta(hours=2) - index * dt.timedelta(days=1) for index in range(STATISTICS))


def _rating_times() -> list[dt.datetime]:
    """Two reads of each earlier round's ratings, a week apart round by round: the morning after it, and the
    day after that."""
    first = NOW - dt.timedelta(days=7 * RATED_ROUNDS)
    return [first + dt.timedelta(days=7 * (slot // 2) + slot % 2) for slot in range(2 * RATED_ROUNDS)]


def _generator() -> duckdb.DuckDBPyConnection:
    """A database of its own on four threads, in UTC: the lake's runs on one, as an answer does, and a season
    is millions of rows to sort."""
    connection = duckdb.connect()
    connection.execute("SET TimeZone = 'UTC'")
    connection.execute("SET threads = 4")
    return connection


def _grow(store: LakeStore, domain: Domain[Any, Any], query: str, params: dict[str, object]) -> int:
    """Add the query's rows to the domain's table, each month's before what its file already holds, the
    round's own rows among them: the season is older. Returns how many rows it added."""
    table = domain.table
    folder = store.root / "silver" / table.name
    folder.mkdir(parents=True, exist_ok=True)
    written = store.description(table)
    files = dict(written.files) if written is not None else {}
    typed = ", ".join(f'"{name}"::{kind} AS "{name}"' for name, kind in table.columns.items())
    with tempfile.TemporaryDirectory() as scratch, _generator() as connection:
        season = Path(scratch) / "season.parquet"
        connection.sql(query, params=params).project(typed).write_parquet(str(season))
        rows = connection.read_parquet(str(season))
        added = int(rows.aggregate("count(*)").fetchall()[0][0])
        month = duckdb.FunctionExpression(
            "strftime", duckdb.ColumnExpression("captured_at"), duckdb.ConstantExpression("%Y-%m")
        )
        months = sorted(str(found) for (found,) in rows.project(month).distinct().fetchall())
        for name in months:
            part = rows.filter(month == duckdb.ConstantExpression(name))
            if name in files:
                part = part.union(connection.read_parquet(str(folder / files[name])))
            files[name] = f"{name}.{uuid.uuid4().hex[:12]}.parquet"
            part.write_parquet(str(folder / files[name]))
    grown = Description(
        columns=list(table.columns.items()),
        rows_version=domain.rows_version,
        last_bronze=written.last_bronze if written is not None else None,
        files=dict(sorted(files.items())),
    )
    store._describe(table, grown)
    store._tidy(table, grown)
    return added


def _before(root: Path, lines: dict[str, list[str]]) -> None:
    """Put each month's lines before those its log file already holds: they're older."""
    root.mkdir(parents=True, exist_ok=True)
    for month, added in lines.items():
        path = root / f"{month}.jsonl"
        kept = path.read_text(encoding="utf-8") if path.is_file() else ""
        path.write_text("".join(line + "\n" for line in added) + kept, encoding="utf-8")


def _runs(log: CollectLog) -> int:
    """A run every two hours before the round's own, each finding the round page and the statistics as they
    were: their confirmations come before the round's reads, so they confirm nothing of it."""
    lines: dict[str, list[str]] = defaultdict(list)
    for index in reversed(range(RUNS)):
        at = NOW - dt.timedelta(hours=3) - index * dt.timedelta(hours=2)
        run = CollectReport(
            started_at=at,
            finished_at=at,
            round=None,
            pages=[
                PageReport(
                    url=f"{BASE}{ROUND_ROUTE}",
                    page="round",
                    outcome="unchanged",
                    fetched_at=at,
                    confirmed=["outlet_views", "odds"],
                ),
                PageReport(
                    url=f"{BASE}{STATS_ROUTE}",
                    page="statistics",
                    outcome="unchanged",
                    fetched_at=at,
                    confirmed=["season_stats"],
                ),
            ],
        )
        lines[month_of(at)].append(run.model_dump_json())
    _before(log.root, lines)
    return RUNS


def _answers(log: DecisionLog) -> int:
    """The round's own lineup, as if asked every six hours before it."""
    told = log.read()[-1]
    lines: dict[str, list[str]] = defaultdict(list)
    for index in reversed(range(ANSWERS)):
        at = NOW - dt.timedelta(hours=2) - index * dt.timedelta(hours=6)
        lines[month_of(at)].append(told.model_copy(update={"as_of": at, "logged_at": at}).model_dump_json())
    _before(log.root, lines)
    return ANSWERS


async def seasoned(folder: Path) -> Season:
    """A synthetic round in `folder`, laid out as `a_round` lays it out, its lineup asked for once; then the
    season around it."""
    async with a_round(folder) as here:
        await here.ask()
    store = LakeStore(folder / "lake")
    return grow(store, CollectLog(folder / "collect"), DecisionLog(store.root / "decisions"))


def grow(store: LakeStore, collect_log: CollectLog, decisions: DecisionLog) -> Season:
    """The season around a synthetic round already stored in `store`, its lineup asked for once."""
    round_page = {"url": f"{BASE}{ROUND_ROUTE}", "times": read_times(), "matches": MATCHES}
    rows = {
        OUTLET_VIEWS.table.name: _grow(
            store, OUTLET_VIEWS, ROUND_PAGE, {**round_page, "outlets": OUTLETS, "listed": LISTED}
        ),
        ODDS.table.name: _grow(store, ODDS, ODDS_ROWS, round_page),
        OFFICIAL_LINEUPS.table.name: _grow(store, OFFICIAL_LINEUPS, OFFICIAL_ROWS, round_page),
        SEASON_STATS.table.name: _grow(
            store,
            SEASON_STATS,
            STATISTICS_ROWS,
            {
                "url": f"{BASE}{STATS_ROUTE}",
                "times": _statistics_times(),
                "matches": MATCHES,
                "players": PLAYERS,
            },
        ),
        MATCH_RATINGS.table.name: _grow(
            store,
            MATCH_RATINGS,
            RATING_ROWS,
            {
                "times": _rating_times(),
                "homes": ["alfa", "gamma", *(f"c{2 * match:02d}" for match in range(MATCHES))],
                "aways": ["beta", "delta", *(f"c{2 * match + 1:02d}" for match in range(MATCHES))],
                "desks": DESKS,
            },
        ),
    }
    return Season(rows=rows, runs=_runs(collect_log), answers=_answers(decisions))
