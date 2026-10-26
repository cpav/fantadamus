"""Each user's league rules, kept privately, and the setup step that asks for them (design C9; R12).

One JSON file per pseudonymous user under the git-ignored `data/local/league/`. A change keeps the previous
file as `<user>.<when it was set>.json`, so every past answer's rules can be traced.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from pydantic import BaseModel

from fantadamus.contracts.types import Role, UtcDatetime
from fantadamus.contracts.xy.league import GoalByRole, LeagueRules
from fantadamus.engine.forwards import Scoring

DEFAULT_ROOT = Path("data/local/league")
_USER = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")
_ROLE_FIELDS = {"P": "keeper", "D": "defender", "C": "midfielder", "A": "forward"}

CLASSIC = LeagueRules(
    goal=3.0,
    assist=1.0,
    penalty_scored=3.0,
    penalty_missed=-3.0,
    penalty_saved=3.0,
    own_goal=-2.0,
    yellow_card=-0.5,
    red_card=-1.0,
    goal_conceded=-1.0,
    clean_sheet=1.0,
)
"""Fantacalcio.it Classic values, offered as the starting choice (R12.3)."""


class StoredRules(BaseModel):
    """A user's rules and when they were set; answers name them (R12.4)."""

    user: str
    saved_at: UtcDatetime
    rules: LeagueRules


class RuleField(BaseModel):
    field: str
    classic: float
    meaning: str


class SetupStep(BaseModel):
    """What `compare_players` returns to a user without league rules (R12.3)."""

    message: str
    tool: str
    fields: list[RuleField]


def setup_step() -> SetupStep:
    classic = CLASSIC.model_dump()
    return SetupStep(
        message="Fantadamus needs this league's bonuses and maluses before it can answer. Ask the user for "
        "each value, offering the Fantacalcio Classic values below as the starting choice; the goal bonus "
        "can also be set per role (keeper, defender, midfielder, forward). Then call set_league_rules.",
        tool="set_league_rules",
        fields=[
            RuleField(field=name, classic=classic[name], meaning=info.description or name)
            for name, info in LeagueRules.model_fields.items()
        ],
    )


def scoring_for(rules: LeagueRules, role: Role) -> Scoring:
    """The values the player model uses for a player of `role` (R12.5)."""
    goal = getattr(rules.goal, _ROLE_FIELDS[role]) if isinstance(rules.goal, GoalByRole) else rules.goal
    return Scoring(
        goal=goal, penalty_scored=rules.penalty_scored, assist=rules.assist, yellow=rules.yellow_card
    )


class RulesStore:
    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def _path(self, user: str) -> Path:
        if not _USER.fullmatch(user):
            raise ValueError(f"user ID {user!r} must be lower-case letters, digits, '-' or '_'")
        return self.root / f"{user}.json"

    def get(self, user: str) -> StoredRules | None:
        path = self._path(user)
        return StoredRules.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None

    def set(self, user: str, rules: LeagueRules, *, at: dt.datetime) -> StoredRules:
        """Store the user's rules, keeping the ones they replace."""
        path, previous = self._path(user), self.get(user)
        if previous is not None:
            path.rename(self.root / f"{user}.{previous.saved_at:%Y%m%dT%H%M%S%fZ}.json")
        stored = StoredRules(user=user, saved_at=at, rules=rules)
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(stored.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        return stored
