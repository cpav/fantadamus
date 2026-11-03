"""mvp-roles task 1.1: a keeper's goals conceded, and one read of the statistics page (design C1; R1.3,
R6.1, R6.2)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from fantadamus.contracts.base import Contract
from fantadamus.contracts.xy.season import PlayerSeasonPayload, SeasonStatsPayload
from tests.roles_data import stats_read, stats_row
from tests.xy_harness import page


def parse[C: Contract](contract: type[C], payload: dict[str, Any]) -> C:
    """As a submit tool will: the payload arrives as JSON."""
    return contract.model_validate_json(json.dumps(payload))


def test_profile_without_goals_conceded_still_valid() -> None:
    profile = parse(PlayerSeasonPayload, page("player_season"))
    assert profile.goals_conceded is None
    assert PlayerSeasonPayload.__version__ == "1.1.0"
    assert "rated appearances" in str(PlayerSeasonPayload.model_fields["appearances"].description)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({}, None),
        ({"role": "D", "mantra_role": "Dc", "goals_conceded": 0}, None),
        ({"role": "D", "mantra_role": "Dc", "goals_conceded": 3}, "only a keeper concedes"),
        ({"goals_conceded": 81}, "81 goals conceded in 8 rated appearances"),
        (
            {"goals_conceded": 1, "rated_appearances": 0, "average_rating": None},
            "1 goals conceded in 0 rated appearances",
        ),
        ({"goals_conceded": -1}, "greater than or equal to 0"),
    ],
)
def test_goals_conceded_rules(change: dict[str, Any], message: str | None) -> None:
    keeper = stats_row("Alfa", "P", "Por", 7001) | change
    for contract in (PlayerSeasonPayload, SeasonStatsPayload):
        payload = keeper if contract is PlayerSeasonPayload else {"players": [keeper]}
        if message is None:
            parse(contract, payload)
        else:
            with pytest.raises(ValidationError, match=message):
                parse(contract, payload)


def test_season_stats_players_once() -> None:
    read = stats_read()
    assert len(parse(SeasonStatsPayload, read).players) == len(read["players"])
    twice = {"players": [*read["players"], read["players"][0] | {"name": "Someone Else"}]}
    with pytest.raises(ValidationError, match="player 7000 is listed twice"):
        parse(SeasonStatsPayload, twice)
    with pytest.raises(ValidationError, match="at least 1 item"):
        parse(SeasonStatsPayload, {"players": []})
