"""mvp-lineup tasks 5.1, 5.3 and 5.4: `best_lineup`'s steps, what it warns about and what it logs (design C8,
C9; R1.4, R2.2, R2.3, R3.1, R5.3, R7.1)."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest

from fantadamus.lake.decision_log import DecisionLog
from fantadamus.league.rules import CLASSIC
from fantadamus.league.squads import SquadPlayer
from fantadamus.web.fetch import Response
from tests.collect_harness import ROUND_ROUTE, STATS_ROUTE
from tests.collect_pages import FcoMatch
from tests.lineup_harness import MATCHES, SQUAD, a_round, player_id, rows
from tests.roles_data import stats_row
from tests.xy_harness import NOW, send, set_classic

pytestmark = pytest.mark.anyio


MATE = [
    "Beta Uno",
    "Delta Uno",
    *(f"Delta {word}" for word in ("Due", "Tre", "Quattro", "Cinque", "Sei", "Sette", "Otto", "Dodici")),
    *(f"Beta {word}" for word in ("Due", "Tre", "Sei", "Sette", "Nove", "Dieci", "Undici", "Tredici")),
]


def _all_names(lineup: dict[str, Any]) -> set[str]:
    return {part["name"] for part in [*lineup["starters"], *lineup["bench"]]}


async def test_statuses(tmp_path: Path) -> None:
    async with a_round(tmp_path, league=False, squad=False, table=False) as here:
        none = await here.ask()
        assert none["status"] == "setup"
        assert {field["field"] for field in none["setup"]["fields"]} >= {"goal", "yellow_card"}  # the bonuses

        await set_classic(here.client)
        bonuses = await here.ask()
        assert bonuses["status"] == "setup"
        assert bonuses["setup"] is None
        assert {field["field"] for field in bonuses["lineup_setup"]["fields"]} == {
            "format",
            "thresholds",
            "bench_size",
            "substitutions",
            "substitution_mode",
            "formations",
        }

        await here.set_rules(format=None)
        just_one = await here.ask()
        assert just_one["status"] == "setup"
        assert [field["field"] for field in just_one["lineup_setup"]["fields"]] == ["format"]

        await here.set_rules()
        no_squad = await here.ask()
        assert no_squad["status"] == "squad"
        assert "set_squad" in no_squad["message"]

        await here.set_squad()
        needed = await here.ask()  # the pages are read, but nothing gives the table or the takers
        assert needed["status"] == "refresh"
        assert {item["fact"] for item in needed["refresh"]} == {"team_season", "penalty_takers"}
        assert needed["lineup"] is None


async def test_one_call_collects_and_answers(tmp_path: Path) -> None:
    """R3.1: with a squad and rules, one call reads the round page and answers."""
    async with a_round(tmp_path) as here:
        result = await here.ask()
    assert result["status"] == "lineup", result
    assert result["lineup"]["round"] == 10
    assert [url for url, _, _ in here.web.calls].count(f"{here.base}{ROUND_ROUTE}") == 1


async def test_no_match_with_lineups_is_a_refresh_plan(tmp_path: Path) -> None:
    """Nothing to rest a lineup on: as today, a plan rather than a guess at every player."""
    bare = (FcoMatch("Alfa", "Beta", lineups=False), FcoMatch("Gamma", "Delta", lineups=False))
    async with a_round(tmp_path, matches=bare) as here:
        result = await here.ask()
    assert result["status"] == "refresh"
    assert {item["fact"] for item in result["refresh"]} >= {"probable_lineups"}


async def test_a_match_without_lineups_goes_ahead_with_a_warning(tmp_path: Path) -> None:
    half = (MATCHES[0], FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00", lineups=False))
    async with a_round(tmp_path, matches=half) as here:
        result = await here.ask()
    assert result["status"] == "lineup", result
    lineup = result["lineup"]
    assert any("Gamma v Delta" in warning and "no lineups" in warning for warning in lineup["warnings"])
    assert ("probable_lineups", "Gamma v Delta") in {
        (item["fact"], item["about"]) for item in lineup["improve"]
    }
    gamma = [part for part in [*lineup["starters"], *lineup["bench"]] if part["club"] == "Gamma"]
    assert gamma
    assert all(part["confidence"] is None for part in gamma)  # nobody gave this chance
    assert all(0 < part["p_start"] <= 0.9 for part in gamma)  # from how often he's played: rated 8 of 8


async def test_player_no_longer_listed(tmp_path: Path) -> None:
    """R1.4: he's named and left out of the eleven."""
    async with a_round(tmp_path) as here:
        stored = here.squads.get("user-1")
        assert stored is not None
        gone = SquadPlayer(player_id=999, name="Partito Via", club="Alfa", role="A")
        here.squads.set("user-1", "mine", [*stored.players, gone], at=NOW)
        result = await here.ask()
    lineup = result["lineup"]
    assert "Partito Via" not in _all_names(lineup)
    assert any("Partito Via" in warning and "no longer listed" in warning for warning in lineup["warnings"])


async def test_rules_left_out_are_named(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await here.set_rules(other_rules=["defence modifier", "captain"])
        lineup = (await here.ask())["lineup"]
    assert any("defence modifier" in warning and "captain" in warning for warning in lineup["warnings"])


async def test_a_league_mates_squad(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await here.set_squad(*MATE, team="Rivali")
        theirs = await here.ask(team="Rivali")
        nobody = await here.ask(team="Nessuno")
        mine = await here.ask()
    assert theirs["lineup"]["team"] == "Rivali"
    assert _all_names(theirs["lineup"]) <= set(MATE)
    assert _all_names(mine["lineup"]) <= set(SQUAD)
    assert nobody["status"] == "squad"


async def test_lineup_logged(tmp_path: Path) -> None:
    """R7.1: the as-of time, the lineup and formation, every squad player's chances, the threshold chances,
    the rules and the content hashes."""
    async with a_round(tmp_path) as here:
        result = await here.ask()
        [decision] = here.log.read()
    lineup = result["lineup"]
    assert decision.kind == "lineup"
    assert decision.user == "user-1"
    assert decision.team == "mine"
    assert decision.round == 10
    assert decision.formation == lineup["formation"]
    assert decision.expected == pytest.approx(lineup["expected"], abs=0.01)
    assert decision.thresholds is not None
    assert {float(points): chance for points, chance in decision.thresholds.items()} == {
        mark["points"]: mark["chance"] for mark in lineup["thresholds"]
    }
    assert decision.as_of == NOW
    assert decision.starters == [part["player_id"] for part in lineup["starters"]]
    assert decision.bench == [part["player_id"] for part in lineup["bench"]]
    assert {logged.name for logged in decision.players} == set(SQUAD)
    keeper = next(logged for logged in decision.players if logged.name == "Alfa Uno")
    assert keeper.p_clean_sheet is not None
    forward = next(logged for logged in decision.players if logged.name == "Beta Nove")
    assert forward.p_scores is not None
    assert decision.rules.rules.lineup is not None
    assert decision.content_hashes


async def test_a_replay_is_not_logged(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        first = await here.ask()
        replay = await here.ask(as_of=NOW.isoformat())
        assert len(here.log.read()) == 1
    assert replay["lineup"]["expected"] == first["lineup"]["expected"]


async def test_earlier_lines_still_read(tmp_path: Path) -> None:
    earlier = {
        "as_of": "2026-10-20T09:00:00+00:00",
        "logged_at": "2026-10-20T09:00:00+00:00",
        "user": "user-1",
        "round": 9,
        "players": [],
        "rules": {
            "user": "user-1",
            "saved_at": "2026-10-20T09:00:00+00:00",
            "rules": CLASSIC.model_dump(exclude={"lineup"}),
        },
        "content_hashes": [],
    }
    log = DecisionLog(tmp_path)
    (tmp_path / "2026-10.jsonl").write_text(json.dumps(earlier) + "\n", encoding="utf-8")
    [read] = log.read()
    assert (read.kind, read.team, read.formation, read.thresholds, read.expected) == (
        "compare",
        None,
        None,
        None,
        None,
    )


async def test_what_moved_since_the_last_lineup(tmp_path: Path) -> None:
    """Compared with the last log entry for this team, with no replay (design C8)."""
    fewer = {f"Alfa {word}": (40, 40, 45, 40) for word in ("Due", "Tre", "Quattro", "Cinque", "Sei", "Sette")}
    async with a_round(tmp_path) as here:
        first = await here.ask()
        assert first["lineup"]["moved"] == []
        here.round_page(dataclasses.replace(MATCHES[0], percents=fewer), MATCHES[1])
        here.clock.now = NOW + dt.timedelta(
            hours=13
        )  # the lineups are stale by now, so the page is read again
        second = await here.ask()
    changes = second["lineup"]["moved"]
    assert any(change.startswith("Alfa Due 91%") and "→" in change for change in changes)
    assert any(change.startswith("expected") for change in changes)


async def test_a_new_round_starts_with_nothing_moved(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await here.ask()
        decision = here.log.read()[0]
        for path in here.log.root.glob("*.jsonl"):
            path.unlink()
        last_round = decision.model_copy(
            update={"round": 9, "as_of": NOW - dt.timedelta(days=7), "expected": 1.0, "formation": "5-4-1"}
        )
        here.log.append(last_round)
        here.clock.now = NOW + dt.timedelta(hours=1)
        assert (await here.ask())["lineup"]["moved"] == []


async def test_warnings_about_basic_data(tmp_path: Path) -> None:
    """R5.5: a player without rated games, a keeper whose goals conceded aren't known."""
    players = rows(
        Alfa_Sei={"rated_appearances": 0, "appearances": 0, "average_rating": None, "goals": 0, "assists": 0}
    )
    async with a_round(tmp_path, players=players) as here:
        lineup = (await here.ask())["lineup"]
    assert any("Alfa Sei" in warning and "no rated games" in warning for warning in lineup["warnings"])


async def test_each_source_once(tmp_path: Path) -> None:
    """R5.4: a page read twice is one line, as read most recently."""
    async with a_round(tmp_path) as here:
        await here.ask()
        result = await send(
            here.client,
            "submit_team_season",
            {
                "teams": [
                    {"club": club, "played": 8, "goals_for": 12, "goals_against": 9}
                    for club in ("Alfa", "Beta", "Gamma", "Delta")
                ]
            },
            NOW,
        )
        assert not result.is_error
        lineup = (await here.ask())["lineup"]
    labels = [source["label"] for source in lineup["sources"]]
    assert labels
    assert len(labels) == len(set(labels))


async def test_chances_without_lineups_come_from_how_often_he_has_played(tmp_path: Path) -> None:
    half = (MATCHES[0], FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00", lineups=False))
    regular = {"rated_appearances": 8, "appearances": 8}
    sometimes = {"rated_appearances": 4, "appearances": 4}
    players = rows(Gamma_Due=regular, Gamma_Tre=sometimes)
    async with a_round(tmp_path, matches=half, players=players) as here:
        lineup = (await here.ask())["lineup"]
    chance = {part["name"]: part["p_start"] for part in [*lineup["starters"], *lineup["bench"]]}
    assert chance["Gamma Due"] == 0.9  # 8 of 8, capped at a listed starter's chance
    assert chance["Gamma Tre"] == 0.5  # 4 of 8


async def test_a_player_with_no_match(tmp_path: Path) -> None:
    """His club doesn't play in the round: he's at zero, it says so, and he has no clean sheet to price."""
    async with a_round(tmp_path, matches=(MATCHES[0],)) as here:
        lineup = (await here.ask())["lineup"]
    keeper = next(part for part in lineup["bench"] if part["name"] == "Gamma Uno")
    assert (keeper["match"], keeper["p_start"], keeper["p_clean_sheet"]) == (None, 0.0, None)
    assert any("Gamma Uno has no match in round 10" in warning for warning in lineup["warnings"])
    assert "Gamma Uno" not in {entry["name"] for entry in lineup["out_and_doubtful"]}


async def test_a_match_without_odds_is_priced_from_team_form(tmp_path: Path) -> None:
    no_odds = (FcoMatch("Alfa", "Beta", odds=None), MATCHES[1])
    async with a_round(tmp_path, matches=no_odds) as here:
        result = await here.ask()
    assert result["status"] == "lineup", result
    lineup = result["lineup"]
    assert any(
        "Alfa v Beta has no odds" in warning and "Alfa Uno" in warning for warning in lineup["warnings"]
    )
    assert ("match_odds", "Alfa v Beta", "missing") in {
        (item["fact"], item["about"], item["why"]) for item in lineup["improve"]
    }
    assert not any("Gamma v Delta" in warning for warning in lineup["warnings"])


async def test_a_name_matched_by_surname_is_said(tmp_path: Path) -> None:
    """The outlets write `DUE A`, the statistics page `Zambo Due` (mvp-roles R4.4)."""
    players = rows(Alfa_Due={"name": "Zambo Due"})
    names = ["Zambo Due" if name == "Alfa Due" else name for name in SQUAD]
    async with a_round(tmp_path, players=players, squad=False) as here:
        await here.set_squad(*names)
        lineup = (await here.ask())["lineup"]
    assert any(
        "DUE A" in warning and "Zambo Due" in warning and "surname" in warning
        for warning in lineup["warnings"]
    )


async def test_a_keeper_whose_goals_conceded_are_unknown(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await here.ask()
        profile = stats_row("Alfa", "P", "Por", player_id("Alfa", "Uno"), name="Alfa Uno")
        del profile["goals_conceded"]
        here.clock.now = NOW + dt.timedelta(minutes=1)
        assert not (await send(here.client, "submit_player_season", profile, here.clock.now)).is_error
        lineup = (await here.ask())["lineup"]
    assert any("Alfa Uno's goals conceded aren't known" in warning for warning in lineup["warnings"])


async def test_a_formation_that_cant_be_fielded_is_left_out_and_said(tmp_path: Path) -> None:
    gamma_defenders = {f"Gamma {word}" for word in ("Due", "Tre", "Quattro", "Cinque")}
    four_defenders = [name for name in SQUAD if name not in gamma_defenders]
    async with a_round(tmp_path, squad=False) as here:
        await here.set_squad(*four_defenders)
        lineup = (await here.ask())["lineup"]
    shown = {entry["formation"] for entry in lineup["formations"]}
    assert "5-3-2" not in shown
    assert "5-4-1" not in shown
    assert "4-4-2" in shown
    assert any("5-3-2 is left out" in warning and "5 defenders" in warning for warning in lineup["warnings"])


async def test_a_squad_that_cant_field_any_formation_says_so(tmp_path: Path) -> None:
    no_keeper = [name for name in SQUAD if not name.endswith("Uno")]
    async with a_round(tmp_path, squad=False) as here:
        await here.set_squad(*no_keeper)
        result = await here.ask()
    assert result["status"] == "squad"
    assert "keeper" in result["message"]
    assert result["lineup"] is None


async def test_what_moved_is_about_this_team_alone(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await here.set_squad(*MATE, team="Rivali")
        await here.ask(team="Rivali")  # logged under the league-mate's name, with other players and numbers
        here.clock.now = NOW + dt.timedelta(minutes=1)
        assert (await here.ask())["lineup"]["moved"] == []  # the user's own first lineup


async def test_what_moved_looks_only_at_earlier_lineups(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await here.ask()
        moved = dataclasses.replace(MATCHES[0], percents={"Alfa Due": (40, 40, 45, 40)})
        here.round_page(moved, MATCHES[1])
        here.clock.now = NOW + dt.timedelta(hours=13)
        assert (await here.ask())["lineup"]["moved"]
        replay = await here.ask(as_of=(NOW + dt.timedelta(hours=1)).isoformat())
    assert replay["lineup"]["moved"] == []  # as it stood then, against the first lineup, not the later one


async def test_a_change_of_formation_is_said(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        first = await here.ask()
        decision = here.log.read()[0]
        for path in here.log.root.glob("*.jsonl"):
            path.unlink()
        here.log.append(
            decision.model_copy(update={"formation": "9-9-9", "expected": first["lineup"]["expected"]})
        )
        here.clock.now = NOW + dt.timedelta(hours=1)
        second = (await here.ask())["lineup"]
    assert f"formation 9-9-9 → {second['formation']}" in second["moved"]


async def test_a_replay_never_collects(tmp_path: Path) -> None:
    async with a_round(tmp_path) as here:
        await here.ask()
        here.clock.now = NOW + dt.timedelta(hours=30)
        calls = len(here.web.calls)
        replay = await here.ask(
            as_of=(NOW + dt.timedelta(hours=26)).isoformat()
        )  # by then, everything is stale
        assert len(here.web.calls) == calls
    assert replay["status"] in ("lineup", "refresh")


async def test_what_is_needed_holds_the_lineup_back(tmp_path: Path) -> None:
    """Season figures past their freshness target, and the statistics page unreadable: a plan, saying what was
    tried, not a lineup on old figures."""
    async with a_round(tmp_path) as here:
        assert (await here.ask())["status"] == "lineup"
        here.routes[f"{here.base}{STATS_ROUTE}"] = Response(500, {}, b"")
        here.clock.now = NOW + dt.timedelta(days=3)
        result = await here.ask()
    assert result["status"] == "refresh"
    assert result["lineup"] is None
    stale = [item for item in result["refresh"] if item["fact"] == "player_season"]
    assert len(stale) == len(SQUAD)
    assert {item["why"] for item in stale} == {"stale"}
    assert all("couldn't read" in item["collector"] for item in stale)
