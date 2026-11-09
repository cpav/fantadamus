"""mvp-lineup task 3.2: asking for just the settings a lineup still needs, and keeping what's stored (design
C2; R2.1, R2.2). Since mvp-rules task 5 it's part of the one setup step (R4.1)."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from fantadamus.contracts.xy.league import EventRow, LeagueRules, LineupRules
from fantadamus.league.rules import (
    CLASSIC,
    COMMON_LINEUP,
    SetupStep,
    setup_step,
    with_stored_lineup,
)

REQUIRED = {"format", "thresholds", "bench_size", "substitutions", "substitution_mode", "formations"}
COMPLETE: dict[str, Any] = {
    "format": "head_to_head",
    "thresholds": [66, 72],
    "bench_size": 12,
    "substitutions": 5,
    "substitution_mode": "same_role",
    "formations": ["3-4-3", "4-3-3"],
}
AT = dt.datetime(2026, 11, 4, 9, 0, tzinfo=dt.UTC)


def _step(rules: LeagueRules) -> SetupStep | None:
    return setup_step(rules, lineup=True)


def _with(**lineup: Any) -> LeagueRules:
    return LeagueRules.model_validate(CLASSIC.model_dump() | {"lineup": lineup})


def test_only_bonuses_asks_for_everything() -> None:
    step = _step(CLASSIC)
    assert step is not None
    assert step.tool == "set_league_rules"
    assert step.events == []  # the table is stored
    assert {field.field for field in step.lineup} == REQUIRED
    assert all(field.common and field.meaning for field in step.lineup)


def test_asks_for_just_what_is_unset() -> None:
    step = _step(_with(format="head_to_head", bench_size=12))
    assert step is not None
    assert {field.field for field in step.lineup} == REQUIRED - {"format", "bench_size"}


def test_nothing_to_ask_once_complete() -> None:
    assert _step(_with(**COMPLETE)) is None


def test_thresholds_not_asked_of_a_total_points_league() -> None:
    """They don't matter there, so they aren't worth the user's time (R2.2)."""
    no_thresholds = {key: value for key, value in COMPLETE.items() if key != "thresholds"}
    assert _step(_with(**no_thresholds | {"format": "total_points"})) is None
    step = _step(_with(**no_thresholds))
    assert step is not None
    assert [field.field for field in step.lineup] == ["thresholds"]


def test_also_asks_about_what_can_be_left_out_while_it_asks() -> None:
    step = _step(CLASSIC)
    assert step is not None
    assert {field.field for field in step.also} == {"no_rating_vote", "other_rules"}
    step = _step(_with(no_rating_vote=6, other_rules=["captain"]))
    assert step is not None
    assert step.also == []


def test_it_never_assumes_a_common_value() -> None:
    """What the step offers isn't stored until the user says so."""
    assert CLASSIC.lineup is None
    assert _step(CLASSIC) is not None
    assert _step(CLASSIC) is not None


@pytest.mark.parametrize(("field", "values"), COMMON_LINEUP.items())
def test_every_common_value_is_a_valid_one(field: str, values: list[Any]) -> None:
    assert values
    for value in values:
        assert getattr(LineupRules.model_validate({field: value}), field) == value


def test_a_call_without_lineup_keeps_the_stored_one() -> None:
    stored = _with(**COMPLETE)
    richer = LeagueRules(events=[EventRow(event="goal", points=3.5, roles=["A"])])
    kept = with_stored_lineup(richer, stored)
    assert kept.events == richer.events
    assert kept.lineup == stored.lineup


def test_a_partial_lineup_fills_in_the_stored_one() -> None:
    stored = _with(**COMPLETE | {"other_rules": ["captain"]})
    kept = with_stored_lineup(_with(bench_size=7), stored)
    assert kept.lineup is not None
    assert kept.lineup.bench_size == 7
    assert kept.lineup.substitutions == 5
    assert kept.lineup.other_rules == ["captain"]


def test_an_explicit_empty_list_clears_other_rules() -> None:
    stored = _with(**COMPLETE | {"other_rules": ["captain"]})
    kept = with_stored_lineup(_with(other_rules=[]), stored)
    assert kept.lineup is not None
    assert kept.lineup.other_rules == []


def test_with_nothing_stored_the_rules_stand_as_given() -> None:
    assert with_stored_lineup(CLASSIC, None) == CLASSIC
