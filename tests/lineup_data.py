"""Invented squads and league settings for the lineup's tests. A real squad never reaches the repository."""

from __future__ import annotations

from typing import Any

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.league import LineupRules
from fantadamus.engine.lineup import Candidate

FORMATIONS = ["3-4-3", "3-5-2", "4-3-3", "4-4-2", "4-5-1", "5-3-2", "5-4-1"]
SHAPE: tuple[tuple[Role, int], ...] = (("P", 3), ("D", 8), ("C", 8), ("A", 6))


def lineup_rules(**changes: Any) -> LineupRules:
    """A complete league: head to head, a bench for everyone, five substitutions, role for role."""
    settings: dict[str, Any] = {
        "format": "head_to_head",
        "thresholds": [66, 72],
        "bench_size": 14,
        "substitutions": 5,
        "substitution_mode": "same_role",
        "formations": FORMATIONS,
    }
    return LineupRules.model_validate(settings | changes)


def candidate(player_id: int, role: Role, **changes: Any) -> Candidate:
    settings: dict[str, Any] = {
        "player_id": player_id,
        "name": f"{role}{player_id}",
        "role": role,
        "club": f"club{player_id}",
        "p_start": 0.9,
        "p_cameo": 0.05,
        "key": 6.0,
    }
    return Candidate.model_validate(settings | changes)


def full_squad(**changes: Any) -> list[Candidate]:
    """Twenty-five players, three keepers of whom two share a club; within a role, a lower ID has a higher
    key."""
    players: list[Candidate] = []
    for role, count in SHAPE:
        for number in range(count):
            player_id = len(players) + 1
            club = "a" if role == "P" and number < 2 else f"club{player_id}"
            players.append(candidate(player_id, role, club=club, key=8.0 - 0.2 * number, **changes))
    return players


# Three common modifiers, for the budget with rules (mvp-rules AT-12).
THREE_RULES: list[dict[str, Any]] = [
    {
        "name": "defence modifier",
        "who": [{"role": "P"}, {"role": "D", "best": 3, "at_least": 4}],
        "combine": "average",
        "base": 4,
        "stand_in": [5.0, 4.5],
        "bands": [
            {"from_value": 6.0, "points": 1.0},
            {"from_value": 6.5, "points": 3.0},
            {"from_value": 7.0, "points": 6.0},
        ],
    },
    {
        "name": "attack modifier",
        "who": [{"role": "A"}],
        "combine": "each",
        "leave_out": "bonus_or_goal",
        "bands": [{"from_value": 6.5, "points": 0.5}, {"from_value": 7.0, "points": 1.0}],
    },
    {
        "name": "midfield sum",
        "who": [{"role": "C"}],
        "combine": "sum",
        "bands": [{"from_value": 24.0, "points": 1.0}, {"from_value": 26.0, "points": 2.0}],
    },
]

# A captain by half points: -2.5 below 4, nothing from 6 to 6.49, +2.5 from 8.5 (mvp-rules AT-7).
CAPTAIN_RULE: dict[str, Any] = {
    "name": "captain",
    "who": "captain",
    "combine": "each",
    "bands": [
        {"from_value": 0.0, "points": -2.5},
        *({"from_value": 4.0 + step / 2, "points": -2.0 + step / 2} for step in range(10)),
    ],
}
BUDGET_RULES = [*THREE_RULES, CAPTAIN_RULE]
"""A captain and three modifiers: the budget's league (mvp-rules R5.1)."""
