"""Each user's league rules, kept privately, and the setup step that asks for them (design C9; R12).

One JSON file per pseudonymous user under the git-ignored `data/local/league/`. A change keeps the previous
file as `<user>.<when it was set>.json`, so every past answer's rules can be traced.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from fantadamus.contracts.types import Role, UtcDatetime
from fantadamus.contracts.xy.league import GoalByRole, LeagueRules, LineupRules
from fantadamus.engine.rank import Scoring

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

COMMON_LINEUP: dict[str, list[Any]] = {
    "format": ["head_to_head", "total_points"],
    "thresholds": [[66, 72, 77, 81, 85, 89], [66, 72]],
    "bench_size": [11, 7],
    "substitutions": [4, 3, 5],
    "substitution_mode": ["role_first", "same_role", "bench_order"],
    "formations": [["3-4-3", "3-5-2", "4-3-3", "4-4-2", "4-5-1", "5-3-2", "5-4-1"]],
}
"""What a lineup needs, with what most leagues use, most common first (mvp-lineup requirements, "What leagues
can set"). They are only ever offered: a user's league is never assumed to use them (R2.2)."""
_ALSO_ASK: dict[str, list[Any]] = {
    "no_rating_vote": [],
    "other_rules": ["defence modifier", "captain", "home factor"],
}


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


class LineupSetting(BaseModel):
    field: str
    common: list[Any]
    """What leagues most often use, most common first."""
    meaning: str


class LineupSetup(BaseModel):
    """What a lineup returns while the league's settings for it are unset (mvp-lineup R2.2)."""

    message: str
    tool: str
    fields: list[LineupSetting]
    also: list[LineupSetting]
    """Worth asking while asking: many leagues have neither, so a lineup doesn't wait for them."""


def _setting(field: str, common: list[Any]) -> LineupSetting:
    return LineupSetting(
        field=field, common=common, meaning=LineupRules.model_fields[field].description or field
    )


def lineup_setup_step(rules: LeagueRules) -> LineupSetup | None:
    """The settings a lineup still needs, or None if it has them all. A total-points league isn't asked for
    thresholds, which don't matter there."""
    lineup = rules.lineup or LineupRules()
    unset = [
        name
        for name in COMMON_LINEUP
        if getattr(lineup, name) is None and (name != "thresholds" or lineup.format != "total_points")
    ]
    if not unset:
        return None
    return LineupSetup(
        message="Fantadamus needs these settings of this league before it can pick a lineup. Ask the user "
        "for each one, offering the common values, most common first; never assume them. Ask about `also` "
        "at the same time. Then call set_league_rules with them under `lineup`: what's already stored "
        "stays.",
        tool="set_league_rules",
        fields=[_setting(name, COMMON_LINEUP[name]) for name in unset],
        also=[_setting(name, common) for name, common in _ALSO_ASK.items() if not getattr(lineup, name)],
    )


def with_stored_lineup(rules: LeagueRules, stored: LeagueRules | None) -> LeagueRules:
    """`rules`, with the stored lineup settings where they don't give their own: a change of bonuses, or an
    answer to the setup step, shouldn't lose what's already set."""
    if stored is None or stored.lineup is None:
        return rules
    given = rules.lineup.model_dump(exclude_unset=True) if rules.lineup is not None else {}
    lineup = LineupRules.model_validate(stored.lineup.model_dump() | given)
    return rules.model_copy(update={"lineup": lineup})


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
            if name != "lineup"
        ],
    )


def scoring_for(rules: LeagueRules, role: Role) -> Scoring:
    """The values the models use for a player of `role` (R12.5; mvp-roles R2.5, R3.1)."""
    goal = getattr(rules.goal, _ROLE_FIELDS[role]) if isinstance(rules.goal, GoalByRole) else rules.goal
    return Scoring(
        goal=goal,
        penalty_scored=rules.penalty_scored,
        assist=rules.assist,
        yellow=rules.yellow_card,
        clean_sheet=rules.clean_sheet,
        goal_conceded=rules.goal_conceded,
    )


def user_file(root: Path, user: str, suffix: str) -> Path:
    """A user's private file; a user ID can't reach outside `root`."""
    if not _USER.fullmatch(user):
        raise ValueError(f"user ID {user!r} must be lower-case letters, digits, '-' or '_'")
    return root / f"{user}{suffix}"


class RulesStore:
    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def _path(self, user: str) -> Path:
        return user_file(self.root, user, ".json")

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
