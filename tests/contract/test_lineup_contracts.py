"""mvp-lineup task 3.1: the league's lineup rules (design C2; R2.1, R2.3, R2.4)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from fantadamus.contracts.xy.league import LeagueRules, LineupRules, formation_lines
from fantadamus.league.rules import CLASSIC, StoredRules

GOOD: dict[str, Any] = {
    "format": "head_to_head",
    "thresholds": [66, 72, 77],
    "bench_size": 11,
    "substitutions": 4,
    "substitution_mode": "role_first",
    "formations": ["3-4-3", "4-4-2"],
}


def _rules(**lineup: Any) -> LeagueRules:
    return LeagueRules.model_validate(CLASSIC.model_dump() | {"lineup": GOOD | lineup})


def test_lineup_rules() -> None:
    lineup = _rules(no_rating_vote=6, other_rules=["defence modifier"]).lineup
    assert lineup is not None
    assert lineup.format == "head_to_head"
    assert lineup.thresholds == [66, 72, 77]
    assert (lineup.bench_size, lineup.substitutions, lineup.substitution_mode) == (11, 4, "role_first")
    assert lineup.formations == ["3-4-3", "4-4-2"]
    assert lineup.no_rating_vote == 6
    assert lineup.other_rules == ["defence modifier"]


def test_a_lineup_can_be_set_a_little_at_a_time() -> None:
    """The setup step asks for what's unset, so any of them may still be."""
    lineup = LineupRules.model_validate({"bench_size": 12})
    assert lineup.bench_size == 12
    assert lineup.thresholds is None
    assert lineup.other_rules == []


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"thresholds": [66, 66]}, "thresholds must rise"),
        ({"thresholds": [72, 66]}, "thresholds must rise"),
        ({"thresholds": [66]}, "at least two thresholds"),
        ({"thresholds": [0, 6]}, "above 0"),
        ({"formations": ["3-4-2"]}, "ten outfield players"),
        ({"formations": ["4-4-3"]}, "ten outfield players"),
        ({"formations": ["3-4-2-1"]}, "three lines"),
        ({"formations": ["433"]}, "three lines"),
        ({"formations": ["0-5-5"]}, "at least one player"),
        ({"formations": ["4-4-2", "4-4-2"]}, "listed twice"),
        ({"formations": []}, "at least one formation"),
        ({"bench_size": 3}, "a keeper and one of each role"),
        ({"bench_size": 26}, "less than or equal to 25"),
        ({"substitutions": -1}, "greater than or equal to 0"),
        ({"substitutions": 12}, "less than or equal to 11"),
        ({"no_rating_vote": 11}, "less than or equal to 10"),
        ({"format": "mantra"}, "head_to_head"),
        ({"substitution_mode": "any"}, "role_first"),
        ({"unknown": 1}, "Extra inputs"),
    ],
)
def test_impossible_values_refused(changes: dict[str, Any], reason: str) -> None:
    with pytest.raises(ValidationError, match=reason):
        _rules(**changes)


def test_stored_rules_without_lineup_stay_valid() -> None:
    """Rules stored before this slice still read, so "X or Y?" keeps working (R2.2)."""
    bonuses = CLASSIC.model_dump(exclude={"lineup"})
    assert "lineup" not in bonuses
    stored = StoredRules.model_validate(
        {"user": "user-1", "saved_at": "2026-10-26T09:00:00+00:00", "rules": bonuses}
    )
    assert stored.rules.lineup is None
    assert stored.rules.goal == CLASSIC.goal


def test_formation_lines() -> None:
    assert formation_lines("3-4-3") == (3, 4, 3)
    assert formation_lines("5-3-2") == (5, 3, 2)
