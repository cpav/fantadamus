"""Shared by the `mvp-x-or-y` tests: synthetic pages, invented clubs, the tools on an in-process client."""

from __future__ import annotations

import contextlib
import datetime as dt
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from mcp import Client
from mcp.types import CallToolResult

from fantadamus.core.clock import fixed_clock
from fantadamus.core.clubs import Clubs
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import CLASSIC, RulesStore
from fantadamus.mcp.server import AdvisorServer
from fantadamus.mcp.tools import compare, league, submit

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "tests" / "fixtures" / "xy"
URL = "https://example.org/page"
NOW = dt.datetime(2026, 10, 26, 10, 0, tzinfo=dt.UTC)
CLUBS = Clubs.from_toml(
    "".join(f'[clubs.{key}]\nname = "{key.title()}"\n' for key in ("alfa", "beta", "gamma", "delta"))
)


def page(name: str) -> dict[str, Any]:
    """A synthetic page from `tests/fixtures/xy/`, as Claude would submit it."""
    loaded: dict[str, Any] = json.loads((PAGES / f"{name}.json").read_text(encoding="utf-8"))
    return loaded


@contextlib.asynccontextmanager
async def tools(store: LakeStore, now: dt.datetime = NOW) -> AsyncIterator[Client]:
    """The tools over `store`, accepting pages from example.org, as user `user-1`; league rules and the
    decision log are kept under the lake's root."""
    server = AdvisorServer(name="fantadamus-test")
    clock = fixed_clock(now)
    submit.register(
        server, store, allowed_hosts=["example.org"], clock=clock, submitted_by="user-1", clubs=CLUBS
    )
    rules = RulesStore(store.root / "league")
    league.register(server, rules, user="user-1", clock=clock)
    advisor = compare.Advisor(
        lake=store,
        rules=rules,
        log=DecisionLog(store.root / "decisions"),
        clubs=CLUBS,
        reading=compare.load_reading_list(ROOT / "config" / "reading_list.toml"),
        user="user-1",
        clock=clock,
    )
    compare.register(server, advisor)
    async with Client(server) as client:
        yield client


async def send(
    client: Client, tool: str, payload: dict[str, Any], captured_at: dt.datetime, url: str = URL
) -> CallToolResult:
    """Call a submit tool the way Claude does: the payload and where and when the page was read."""
    return await client.call_tool(
        tool, {"payload": payload, "source_url": url, "captured_at": captured_at.isoformat()}
    )


def error_text(result: CallToolResult) -> str:
    assert result.is_error
    return " ".join(getattr(block, "text", "") for block in result.content)


def probable(outlet: str, **teams: dict[str, Any]) -> dict[str, Any]:
    """The synthetic probable lineup as `outlet` sees it, with `home_team` or `away_team` replaced."""
    payload = page("probable_lineup") | {"outlet": outlet}
    return payload | teams


def alfa_team(nove: str) -> dict[str, Any]:
    """Alfa's probable team with Alfa Nove as a `starter`, in a 50/50 `ballottaggio`, on the `bench` or
    `unavailable`. The eleven starters stay eleven."""
    team: dict[str, Any] = page("probable_lineup")["home_team"]
    if nove != "starter":
        team["starters"] = [name for name in team["starters"] if name != "Alfa Nove"] + ["Alfa Dodici"]
        team["ballottaggi"] = []
        team["bench"] = ["Alfa Tredici"]
    if nove == "ballottaggio":
        team["ballottaggi"] = [
            {"players": [{"name": "Alfa Nove", "percent": 50}, {"name": "Alfa Dodici", "percent": 50}]}
        ]
    elif nove in {"bench", "unavailable"}:
        team[nove].append("Alfa Nove")
    return team


WORDS = [
    "Uno",
    "Due",
    "Tre",
    "Quattro",
    "Cinque",
    "Sei",
    "Sette",
    "Otto",
    "Nove",
    "Dieci",
    "Undici",
    "Dodici",
    "Tredici",
    "Quattordici",
]
GAMMA_NOVE = {
    "player_id": 9003,
    "name": "Gamma Nove",
    "club": "Gamma",
    "role": "A",
    "mantra_role": "W",
    "appearances": 8,
    "rated_appearances": 7,
    "average_rating": 6.1,
    "goals": 2,
    "assists": 2,
    "yellow_cards": 1,
    "penalties_scored": 0,
    "penalties_taken": 0,
}


def lineup(home: str, away: str, outlet: str) -> dict[str, Any]:
    """A probable lineup where each club's players are `<Club> Uno` to `<Club> Quattordici`."""

    def team(club: str) -> dict[str, Any]:
        squad = [f"{club} {word}" for word in WORDS]
        return {"starters": squad[:11], "ballottaggi": [], "bench": squad[11:13], "unavailable": squad[13:]}

    return {"outlet": outlet, "home": home, "away": away, "home_team": team(home), "away_team": team(away)}


def odds_for(home: str, away: str) -> dict[str, Any]:
    return page("match_odds") | {"home": home, "away": away}


TEAM_TABLE = {
    "teams": [
        {"club": "Alfa", "played": 8, "goals_for": 14, "goals_against": 9},
        {"club": "Beta", "played": 8, "goals_for": 10, "goals_against": 11},
        {"club": "Gamma", "played": 8, "goals_for": 6, "goals_against": 10},
        {"club": "Delta", "played": 8, "goals_for": 10, "goals_against": 10},
    ]
}
TAKERS = {
    "clubs": [
        {"club": club, "takers": [f"{club} Nove", f"{club} Dieci"]}
        for club in ("Alfa", "Beta", "Gamma", "Delta")
    ]
}


async def collect(
    client: Client, captured_at: dt.datetime, *, facts: tuple[str, ...] = ("season", "round")
) -> None:
    """Submit the synthetic round: `season` is the profiles, table and takers; `round` the fixtures, two
    outlets' lineups and the odds of Alfa v Beta and Gamma v Delta."""
    submissions: list[tuple[str, dict[str, Any]]] = []
    if "season" in facts:
        submissions += [
            ("submit_player_season", page("player_season")),
            ("submit_player_season", GAMMA_NOVE),
            ("submit_team_season", TEAM_TABLE),
            ("submit_penalty_takers", TAKERS),
        ]
    if "fixtures" in facts or "round" in facts:
        submissions.append(("submit_fixtures", page("fixtures")))
    if "round" in facts:
        for home, away in (("Alfa", "Beta"), ("Gamma", "Delta")):
            submissions += [
                ("submit_probable_lineups", lineup(home, away, "Uno")),
                ("submit_probable_lineups", lineup(home, away, "Due")),
                ("submit_match_odds", odds_for(home, away)),
            ]
    for tool, payload in submissions:
        result = await send(client, tool, payload, captured_at)
        assert not result.is_error, (tool, result)


async def set_classic(client: Client, **changes: object) -> None:
    result = await client.call_tool("set_league_rules", {"rules": CLASSIC.model_dump() | changes})
    assert not result.is_error, result


async def ask(
    client: Client, first: str = "Alfa Nove", second: str = "Gamma Nove", **options: object
) -> dict[str, Any]:
    """`compare_players` as Claude calls it; the structured result."""
    result = await client.call_tool("compare_players", {"first": first, "second": second, **options})
    assert not result.is_error, result
    content: dict[str, Any] | None = result.structured_content
    assert content is not None
    return content


def outlet_lineup(outlet: str, home: str = "Alfa", away: str = "Beta", **percents: float) -> dict[str, Any]:
    """An outlet's per-player start percentages for a match: each club's first eleven at 90, two on the bench
    at 10, the fourteenth unavailable. Keyword arguments set one player's percentage, e.g. `Alfa_Nove=55`."""

    def team(club: str) -> dict[str, Any]:
        squad = [f"{club} {word}" for word in WORDS]
        players = [
            {"name": name, "role": "A", "percent": percents.get(name.replace(" ", "_"), 90 if i < 11 else 10)}
            for i, name in enumerate(squad[:13])
        ]
        return {"players": players, "unavailable": squad[13:]}

    return {"outlet": outlet, "home": home, "away": away, "home_team": team(home), "away_team": team(away)}
