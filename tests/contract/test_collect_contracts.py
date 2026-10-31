"""mvp-collect task 1.1: outlets' per-player percentages and a page's chance of 3+ goals (C4; R3.1, R4.1)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from fantadamus.contracts.base import Contract
from fantadamus.contracts.xy.lineups import OutletLineupPayload
from fantadamus.contracts.xy.odds import MatchOddsPayload
from tests.xy_harness import outlet_lineup, page


def parse[C: Contract](contract: type[C], payload: dict[str, Any]) -> C:
    return contract.model_validate_json(json.dumps(payload))


def test_outlet_lineup_rules() -> None:
    view = parse(OutletLineupPayload, outlet_lineup("Uno", Alfa_Nove=55))
    nove = next(player for player in view.home_team.players if player.name == "Alfa Nove")
    assert (nove.percent, nove.role, view.home_team.unavailable) == (55, "A", ["Alfa Quattordici"])
    short = outlet_lineup("Uno")
    short["home_team"]["players"] = short["home_team"]["players"][:10]
    with pytest.raises(ValidationError, match="needs at least 11 players, got 10"):
        parse(OutletLineupPayload, short)
    repeated = outlet_lineup("Uno")
    repeated["away_team"]["players"][1]["name"] = "Beta Uno"
    with pytest.raises(ValidationError, match="Beta Uno is listed twice"):
        parse(OutletLineupPayload, repeated)
    with pytest.raises(ValidationError, match="less than or equal to 100"):
        parse(OutletLineupPayload, outlet_lineup("Uno", Alfa_Uno=120))


def test_odds_with_percent_over() -> None:
    only_percent = page("match_odds") | {"over_2_5": None, "under_2_5": None, "over_2_5_percent": 53}
    assert parse(MatchOddsPayload, only_percent).over_2_5_percent == 53
    assert parse(MatchOddsPayload, page("match_odds") | {"over_2_5_percent": 53}).over_2_5 == 1.95
    with pytest.raises(ValidationError, match="less than or equal to 100"):
        parse(MatchOddsPayload, only_percent | {"over_2_5_percent": 101})
