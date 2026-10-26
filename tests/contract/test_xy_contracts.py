"""Task 1.2: the fact contracts and their quality rules, on synthetic pages (design C2; R8)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from fantadamus.contracts.base import Contract
from fantadamus.contracts.xy.fixtures import FixturesPayload
from fantadamus.contracts.xy.lineups import OfficialLineupPayload, ProbableLineupPayload
from fantadamus.contracts.xy.odds import MatchOddsPayload
from fantadamus.contracts.xy.season import PenaltyTakersPayload, PlayerSeasonPayload, TeamSeasonPayload

PAGES = Path(__file__).resolve().parents[1] / "fixtures" / "xy"


def page(name: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((PAGES / f"{name}.json").read_text(encoding="utf-8"))
    return loaded


def parse[C: Contract](contract: type[C], payload: dict[str, Any]) -> C:
    """As a submit tool will: the payload arrives as JSON."""
    return contract.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(
    ("contract", "name"),
    [
        (FixturesPayload, "fixtures"),
        (ProbableLineupPayload, "probable_lineup"),
        (OfficialLineupPayload, "official_lineup"),
        (MatchOddsPayload, "match_odds"),
        (PlayerSeasonPayload, "player_season"),
        (TeamSeasonPayload, "team_season"),
        (PenaltyTakersPayload, "penalty_takers"),
    ],
)
def test_synthetic_pages_parse(contract: type[Contract], name: str) -> None:
    assert parse(contract, page(name)).__version__ == "1.0.0"


def test_kickoffs_are_stored_in_utc_and_clubs_meet_once() -> None:
    fixtures = parse(FixturesPayload, page("fixtures"))
    assert fixtures.matches[0].kickoff_at == dt.datetime(2026, 10, 31, 14, 0, tzinfo=dt.UTC)
    payload = page("fixtures")
    payload["matches"][1]["away"] = "ALFA"
    with pytest.raises(ValidationError, match="Alfa plays twice"):
        parse(FixturesPayload, payload)
    payload["matches"][1]["home"] = "ALFA"
    with pytest.raises(ValidationError, match="plays itself"):
        parse(FixturesPayload, payload)


@pytest.mark.parametrize(
    ("contract", "name"),
    [(ProbableLineupPayload, "probable_lineup"), (OfficialLineupPayload, "official_lineup")],
)
def test_eleven_starters(contract: type[Contract], name: str) -> None:
    short = page(name)
    short["home_team"]["starters"].pop()
    with pytest.raises(ValidationError, match="needs 11 starters, got 10"):
        parse(contract, short)
    repeated = page(name)
    repeated["away_team"]["starters"][1] = repeated["away_team"]["starters"][0]
    with pytest.raises(ValidationError, match="Beta Uno is listed twice"):
        parse(contract, repeated)


@pytest.mark.parametrize(
    ("first", "second", "ok"), [(60, 40, True), (50, 48, True), (50, 30, False), (70, 40, False)]
)
def test_ballottaggio_shares(first: float, second: float, ok: bool) -> None:
    payload = page("probable_lineup")
    payload["home_team"]["ballottaggi"][0]["players"][0]["percent"] = first
    payload["home_team"]["ballottaggi"][0]["players"][1]["percent"] = second
    if ok:
        parse(ProbableLineupPayload, payload)
    else:
        with pytest.raises(ValidationError, match=r"shares sum to \d+%, outside 95% to 105%"):
            parse(ProbableLineupPayload, payload)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"home_win": 1.6, "draw": 2.9, "away_win": 2.9}, r"1X2 margin 31\.5% is outside 0% to 15%"),
        ({"over_2_5": 2.3, "under_2_5": 2.3}, r"over/under 2\.5 margin -13\.0% is outside 0% to 15%"),
        ({"goal": 1.4, "no_goal": 1.4}, r"goal/no goal margin 42\.9% is outside 0% to 15%"),
        ({"no_goal": None}, "goal and no goal go together"),
        ({"draw": 1.0}, "greater than 1"),
    ],
)
def test_odds_margin(change: dict[str, float | None], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse(MatchOddsPayload, page("match_odds") | change)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"goals": 41}, "41 goals in 8 appearances"),
        ({"average_rating": 2.5}, "greater than or equal to 3"),
        ({"average_rating": 10.5}, "less than or equal to 10"),
        ({"rated_appearances": 9}, "9 rated appearances out of 8"),
        ({"average_rating": None}, "an average rating goes with rated appearances"),
        ({"rated_appearances": 0}, "an average rating goes with rated appearances"),
        ({"penalties_scored": 3}, "3 penalties scored out of 2 taken"),
    ],
)
def test_impossible_season_figures(change: dict[str, float | None], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse(PlayerSeasonPayload, page("player_season") | change)
