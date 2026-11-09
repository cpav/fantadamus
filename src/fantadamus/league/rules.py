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
from fantadamus.contracts.xy.league import (
    EVENT_MEANINGS,
    Band,
    EventRow,
    FormulaRule,
    LeagueRules,
    LineupRules,
    Unit,
)
from fantadamus.core.files import temporary_beside
from fantadamus.engine.constants import DECISIVE_GOAL_SHARE, SET_PIECE_ASSIST_SHARE
from fantadamus.engine.rank import Scoring

DEFAULT_ROOT = Path("data/local/league")
_USER = re.compile(r"[a-z0-9][a-z0-9_-]{0,39}")

_EVERY_ROLE: list[Role] = ["P", "D", "C", "A"]
CLASSIC = LeagueRules(
    events=[
        EventRow(event="goal", points=3.0, roles=_EVERY_ROLE),
        EventRow(event="assist", points=1.0, roles=_EVERY_ROLE),
        EventRow(event="penalty_scored", points=3.0, roles=_EVERY_ROLE),
        EventRow(event="penalty_missed", points=-3.0, roles=_EVERY_ROLE),
        EventRow(event="penalty_saved", points=3.0, roles=["P"]),
        EventRow(event="own_goal", points=-2.0, roles=_EVERY_ROLE),
        EventRow(event="yellow_card", points=-0.5, roles=_EVERY_ROLE),
        EventRow(event="red_card", points=-1.0, roles=_EVERY_ROLE),
        EventRow(event="goal_conceded", points=-1.0, roles=["P"]),
        EventRow(event="clean_sheet", points=1.0, roles=["P"]),
    ]
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
    "other_rules": ["home factor: needs the opponent's team", "fair play: not priced yet"],
}


class ReadyMade(BaseModel):
    """A common rule, to add to `formula_rules` as it is or with the league's own values (mvp-rules R2.3)."""

    meaning: str
    rule: FormulaRule


def _bands(*pairs: tuple[float, float]) -> list[Band]:
    return [Band(from_value=start, points=points) for start, points in pairs]


READY_MADE = [
    ReadyMade(
        meaning="The keeper and the three best defenders, averaged, with at least four defenders fielded: "
        "from 6 +1, from 6.5 +3, from 7 +6",
        rule=FormulaRule(
            name="defence modifier",
            who=[Unit(role="P"), Unit(role="D", best=3, at_least=4)],
            combine="average",
            bands=_bands((6.0, 1.0), (6.5, 3.0), (7.0, 6.0)),
        ),
    ),
    ReadyMade(
        meaning="Each forward who didn't score, on his own: from 6.5 +0.5 up to +2 from 8, by half points",
        rule=FormulaRule(
            name="attack modifier",
            who=[Unit(role="A")],
            combine="each",
            leave_out="bonus_or_goal",
            bands=_bands((6.5, 0.5), (7.0, 1.0), (7.5, 1.5), (8.0, 2.0)),
        ),
    ),
    ReadyMade(
        meaning="The captain's pure vote, his vice's when he has none: from -2.5 below 4 to +2.5 from 8.5, "
        "by half points, and nothing from 6 to 6.49",
        rule=FormulaRule(
            name="captain",
            who="captain",
            combine="each",
            bands=_bands((0.0, -2.5), *((4.0 + step / 2, -2.0 + step / 2) for step in range(10))),
        ),
    ),
]
"""Fantacalcio-Online's common rules, at the values its guides give (read 2026-11-09)."""


class StoredRules(BaseModel):
    """A user's rules and when they were set; answers name them (R12.4)."""

    user: str
    saved_at: UtcDatetime
    rules: LeagueRules


class RuleField(BaseModel):
    field: str
    classic: float
    meaning: str
    roles: list[Role]


class LineupSetting(BaseModel):
    field: str
    common: list[Any]
    """What leagues most often use, most common first."""
    meaning: str


class SetupStep(BaseModel):
    """Whatever the question still needs of the league's rules, in one step (mvp-rules R4.1)."""

    message: str
    tool: str
    events: list[RuleField]
    """The bonuses and maluses, at Fantacalcio Classic's values, when the league has none stored."""
    lineup: list[LineupSetting]
    """What a lineup still needs (mvp-lineup R2.2)."""
    also: list[LineupSetting]
    """Worth asking while asking: many leagues have neither, so a lineup doesn't wait for them."""
    ready_made: list[ReadyMade]
    """Common modifiers and the captain, offered until the league has formula rules."""


def _setting(field: str, common: list[Any]) -> LineupSetting:
    return LineupSetting(
        field=field, common=common, meaning=LineupRules.model_fields[field].description or field
    )


def with_stored_lineup(rules: LeagueRules, stored: LeagueRules | None) -> LeagueRules:
    """`rules`, with the stored lineup settings where they don't give their own: a change of bonuses, or an
    answer to the setup step, shouldn't lose what's already set."""
    if stored is None or stored.lineup is None:
        return rules
    given = rules.lineup.model_dump(exclude_unset=True) if rules.lineup is not None else {}
    lineup = LineupRules.model_validate(stored.lineup.model_dump() | given)
    return rules.model_copy(update={"lineup": lineup})


def setup_step(rules: LeagueRules | None, *, lineup: bool) -> SetupStep | None:
    """What the question still needs, or None if nothing: the table of events when the league has none, and
    for a lineup the settings it lacks. A total-points league isn't asked for thresholds, which don't matter
    there."""
    events = (
        []
        if rules is not None
        else [
            RuleField(field=row.event, classic=row.points, meaning=EVENT_MEANINGS[row.event], roles=row.roles)
            for row in CLASSIC.events
        ]
    )
    settings = (rules.lineup if rules is not None else None) or LineupRules()
    unset = [
        name
        for name in COMMON_LINEUP
        if lineup
        and getattr(settings, name) is None
        and (name != "thresholds" or settings.format != "total_points")
    ]
    if not events and not unset:
        return None
    return SetupStep(
        message="Fantadamus needs these of this league's rules first. Ask the user for each, or read them "
        "from their league profile or rulebook, offering the values given, most common first; never assume "
        "them. `events` are the bonuses and maluses, at Fantacalcio Classic's values: any can differ by "
        "role, one row per value. `lineup` is what a lineup needs; ask about `also` at the same time. "
        "`ready_made` holds common modifiers and the captain: add those the league uses to formula_rules, "
        "with its own values. Then call set_league_rules: what's already stored stays.",
        tool="set_league_rules",
        events=events,
        lineup=[_setting(name, COMMON_LINEUP[name]) for name in unset],
        also=[
            _setting(name, common)
            for name, common in _ALSO_ASK.items()
            if unset and not getattr(settings, name)
        ],
        ready_made=READY_MADE if rules is None or not rules.formula_rules else [],
    )


def priced(rules: LeagueRules) -> list[str]:
    """Every event and formula rule the numbers count, in plain words, for reading back (mvp-rules R4.2)."""
    lines = [f"{EVENT_MEANINGS[row.event]}: {row.points:+g} ({', '.join(row.roles)})" for row in rules.events]
    return lines + [f"{rule.name}: {_described(rule)}" for rule in rules.formula_rules]


def _described(rule: FormulaRule) -> str:
    bands = ", ".join(f"from {band.from_value:g} {band.points:+g}" for band in rule.bands)
    if rule.who == "captain":
        return f"the captain's pure vote, his vice's when he has none; {bands}"
    units = []
    for unit in rule.who:
        counted = f"the best {unit.best} {unit.role}" if unit.best is not None else unit.role
        limits = [
            *([f"at least {unit.at_least}"] if unit.at_least is not None else []),
            *([f"at most {unit.at_most}"] if unit.at_most is not None else []),
        ]
        units.append(counted + (f" ({' and '.join(limits)} {unit.role} fielded)" if limits else ""))
    how = {"average": "averaged", "sum": "summed", "each": "each on his own"}[rule.combine]
    words = [f"pure votes of {' and '.join(units)}, {how}"]
    if rule.leave_out == "bonus_or_goal":
        words.append("leaving out a player who scored, conceded or saved a penalty")
    if rule.base is not None:
        stand_in = (
            f" with stand-in votes {', '.join(f'{vote:g}' for vote in rule.stand_in)}"
            if rule.stand_in
            else ""
        )
        words.append(f"counting {rule.base}{stand_in}")
    return "; ".join([", ".join(words), bands])


def left_out(rules: LeagueRules) -> list[str]:
    """The league's rules the numbers leave out, each with what it needs (mvp-rules R4.3)."""
    return list(rules.lineup.other_rules) if rules.lineup is not None else []


def scoring_for(rules: LeagueRules, role: Role) -> Scoring:
    """What the table says for a player of `role`, as the models read it (mvp-rules R1). An event it leaves
    out is worth nothing, and a share-based event joins the worth of the event it's a share of (R1.5)."""
    points = {row.event: row.points for row in rules.events if role in row.roles}
    decisive = DECISIVE_GOAL_SHARE * points.get("decisive_goal", 0.0)
    assist = points.get("assist", 0.0)
    return Scoring(
        goal=points.get("goal", 0.0) + decisive,
        penalty_scored=points.get("penalty_scored", 0.0) + decisive,
        assist=assist + SET_PIECE_ASSIST_SHARE * (points.get("set_piece_assist", assist) - assist),
        yellow=points.get("yellow_card", 0.0),
        clean_sheet=points.get("clean_sheet", 0.0),
        goal_conceded=points.get("goal_conceded", 0.0),
        penalty_missed=points.get("penalty_missed", 0.0),
        penalty_saved=points.get("penalty_saved", 0.0),
        own_goal=points.get("own_goal", 0.0),
        red=points.get("red_card", 0.0),
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
        temporary = temporary_beside(path)
        temporary.write_text(stored.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        return stored
