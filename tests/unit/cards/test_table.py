"""mvp-cards task 1.1: the table's record and form, optional and checked against the matches played; tables
stored before them stay valid (design C1; R2.4)."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from pydantic import ValidationError

from fantadamus.contracts.xy.season import TeamRow, TeamSeasonPayload
from fantadamus.core.clubs import Clubs
from fantadamus.domains.facts import Source
from fantadamus.domains.season.silver import TEAM_SEASONS

CLUBS = Clubs.from_toml('[clubs.alfa]\nname = "Alfa"\n')
SOURCE = Source(
    source_url="https://example.org/classifica",
    captured_at=dt.datetime(2026, 11, 1, 9, 0, tzinfo=dt.UTC),
    content_sha256="0" * 64,
)
BEFORE = {"club": "Alfa", "played": 9, "goals_for": 17, "goals_against": 8}
"""A row as tables were submitted before this slice."""


def _row(**changes: Any) -> TeamRow:
    return TeamRow.model_validate(BEFORE | changes)


def test_tables_stored_before_still_read() -> None:
    """A row without the record or the form validates, and its silver row has them unknown; with them, the
    form is kept as its letters, oldest first."""
    old = TEAM_SEASONS.to_rows(TeamSeasonPayload(teams=[_row()]), CLUBS, SOURCE)
    assert [(row.wins, row.draws, row.losses, row.form) for row in old] == [(None, None, None, None)]
    new = TEAM_SEASONS.to_rows(
        TeamSeasonPayload(teams=[_row(wins=6, draws=2, losses=1, form=["W", "W", "D", "L", "W"])]),
        CLUBS,
        SOURCE,
    )
    assert [(row.wins, row.draws, row.losses, row.form) for row in new] == [(6, 2, 1, "WWDLW")]


@pytest.mark.parametrize(
    "record",
    [
        {"wins": 6, "draws": 2, "losses": 2},  # ten matches, not nine
        {"wins": 6},  # a record has all three or none
        {"wins": 6, "draws": 3},
    ],
)
def test_the_record_adds_up(record: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        _row(**record)
    assert _row(wins=6, draws=2, losses=1).played == 9


@pytest.mark.parametrize(
    "changes",
    [
        {
            "wins": 6,
            "draws": 2,
            "losses": 1,
            "form": ["W", "L", "D", "L", "W"],
        },  # two losses, one in the record
        {"wins": 6, "draws": 2, "losses": 1, "form": ["W", "W", "W", "W", "W", "W"]},  # six results
        {"played": 2, "goals_for": 2, "goals_against": 1, "form": ["W", "D", "W"]},  # more than played
        {"form": ["W", "X"]},
    ],
)
def test_the_form_fits_the_record(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _row(**changes)
    assert _row(form=["W", "D"]).form == ["W", "D"]  # without a record, any results up to the matches played
