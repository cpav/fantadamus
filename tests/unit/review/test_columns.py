"""mvp-review task 1.1: statistics stored before the three new columns still read, with them unknown (design
C1; R2.1)."""

from __future__ import annotations

from typing import Any

from fantadamus.contracts.xy.season import PlayerSeasonPayload, SeasonStatsPayload
from tests.roles_data import stats_row

_NEW = ("fantasy_average", "penalties_saved", "red_cards")


def _as_stored_before(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in _NEW}


def test_rows_stored_before_still_read() -> None:
    old = _as_stored_before(stats_row("Alfa", "A", "Pc", 9201))
    read = SeasonStatsPayload.model_validate({"players": [old]}).players[0]
    assert (read.fantasy_average, read.penalties_saved, read.red_cards) == (None, None, None)
    profile = PlayerSeasonPayload.model_validate(old)
    assert profile.fantasy_average is None


def test_the_new_columns_are_bounded() -> None:
    row = stats_row("Alfa", "P", "Por", 9202)
    fine = {"penalties_saved": 1, "red_cards": 0, "fantasy_average": -1.5}
    assert SeasonStatsPayload.model_validate({"players": [row | fine]}).players[0].penalties_saved == 1
    for change in ({"penalties_saved": -1}, {"red_cards": -1}, {"fantasy_average": 40.0}):
        try:
            SeasonStatsPayload.model_validate({"players": [row | change]})
        except ValueError:
            continue
        raise AssertionError(change)
