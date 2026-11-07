"""`LeagueRules`: a Fantacalcio Classic league's table of events, set by each user (mvp-rules R1), and what a
lineup also needs: thresholds, the bench, substitutions and formations (mvp-lineup R2)."""

from __future__ import annotations

import itertools
import re
from collections.abc import Mapping
from typing import Any, Literal, Self

from pydantic import Field, field_validator, model_validator

from fantadamus.contracts.base import Contract, Part
from fantadamus.contracts.types import Name, Role
from fantadamus.contracts.xy import once_each

EventName = Literal[
    "goal",
    "decisive_goal",
    "assist",
    "set_piece_assist",
    "penalty_scored",
    "penalty_missed",
    "penalty_saved",
    "own_goal",
    "yellow_card",
    "red_card",
    "goal_conceded",
    "clean_sheet",
]
EVENT_MEANINGS: dict[str, str] = {
    "goal": "A goal scored",
    "decisive_goal": "A goal that wins or draws the match, on top of the goal's own points",
    "assist": "An assist",
    "set_piece_assist": "An assist from a set piece, in place of the assist's points",
    "penalty_scored": "A penalty scored, counted in place of the goal bonus",
    "penalty_missed": "A penalty missed",
    "penalty_saved": "A penalty saved, for keepers",
    "own_goal": "An own goal",
    "yellow_card": "A yellow card",
    "red_card": "A red card",
    "goal_conceded": "Each goal conceded, usually a keeper's",
    "clean_sheet": "A clean sheet, usually a keeper's",
}
_BONUSES = frozenset(
    {"goal", "decisive_goal", "assist", "set_piece_assist", "penalty_scored", "penalty_saved", "clean_sheet"}
)
_KEEPERS_ONLY = frozenset({"penalty_saved"})
_EVERY_ROLE: tuple[Role, ...] = ("P", "D", "C", "A")
_KEEPER: tuple[Role, ...] = ("P",)
_EARLIER_VALUES: dict[str, tuple[Role, ...]] = {
    "goal": _EVERY_ROLE,
    "assist": _EVERY_ROLE,
    "penalty_scored": _EVERY_ROLE,
    "penalty_missed": _EVERY_ROLE,
    "penalty_saved": _KEEPER,
    "own_goal": _EVERY_ROLE,
    "yellow_card": _EVERY_ROLE,
    "red_card": _EVERY_ROLE,
    "goal_conceded": _KEEPER,
    "clean_sheet": _KEEPER,
}
"""The ten fixed values of the earlier form, in its order, and who each applied to."""
_EARLIER_ROLES: dict[str, Role] = {"keeper": "P", "defender": "D", "midfielder": "C", "forward": "A"}
OUTFIELD = 10
FEWEST_ON_THE_BENCH = 4
_FORMATION = re.compile(r"\d-\d-\d")


def formation_lines(formation: str) -> tuple[int, int, int]:
    """Defenders, midfielders and forwards: `3-4-3` is (3, 4, 3)."""
    defenders, midfielders, forwards = map(int, formation.split("-"))
    return defenders, midfielders, forwards


class LineupRules(Part):
    """What a lineup needs beyond bonuses and maluses. Any of it may still be unset: the setup step asks for
    what is (mvp-lineup R2.2)."""

    format: Literal["head_to_head", "total_points"] | None = Field(
        default=None, description="Head to head, where thresholds decide; or total points, where they don't"
    )
    thresholds: list[float] | None = Field(
        default=None,
        description="Rising points for the 1st, 2nd and later fantasy goals; past the last, its last step "
        "repeats",
    )
    bench_size: int | None = Field(default=None, le=25, description="Places on the bench")
    substitutions: int | None = Field(default=None, ge=0, le=11, description="Substitutions per match")
    substitution_mode: Literal["same_role", "role_first", "bench_order"] | None = Field(
        default=None,
        description="How a player without a rating is replaced: same role only (the formation never "
        "changes); role first, then bench order; or bench order first. The last two may change the "
        "formation, into an allowed one",
    )
    formations: list[str] | None = Field(
        default=None, description="Allowed formations, as defenders-midfielders-forwards: 3-4-3"
    )
    no_rating_vote: float | None = Field(
        default=None,
        ge=0,
        le=10,
        description="The vote a player without a rating keeps when nobody replaces him, if the league gives "
        "one",
    )
    other_rules: list[Name] = Field(
        default=[],
        description="Rules this league uses that Fantadamus leaves out, such as a modifier or a captain; "
        "every lineup says its score doesn't include them",
    )

    @field_validator("thresholds")
    @classmethod
    def _rising(cls, thresholds: list[float] | None) -> list[float] | None:
        if thresholds is None:
            return None
        if len(thresholds) < 2:
            raise ValueError("needs at least two thresholds: past the last, its last step repeats")
        if thresholds[0] <= 0:
            raise ValueError("thresholds must be above 0")
        for before, after in itertools.pairwise(thresholds):
            if after <= before:
                raise ValueError(f"thresholds must rise: {after:g} comes after {before:g}")
        return thresholds

    @field_validator("bench_size")
    @classmethod
    def _bench_covers_every_role(cls, places: int | None) -> int | None:
        if places is not None and places < FEWEST_ON_THE_BENCH:
            raise ValueError(
                f"a bench needs at least {FEWEST_ON_THE_BENCH} places, a keeper and one of each role: "
                f"got {places}"
            )
        return places

    @field_validator("formations")
    @classmethod
    def _eleven_players(cls, formations: list[str] | None) -> list[str] | None:
        if formations is None:
            return None
        if not formations:
            raise ValueError("needs at least one formation")
        once_each(formations, "{name} is listed twice")
        for formation in formations:
            if not _FORMATION.fullmatch(formation):
                raise ValueError(f"{formation} isn't three lines, such as 3-4-3")
            lines = formation_lines(formation)
            if min(lines) < 1:
                raise ValueError(f"{formation} needs at least one player in each line")
            if sum(lines) != OUTFIELD:
                raise ValueError(f"{formation} must add up to ten outfield players, and a keeper")
        return formations


class EventRow(Part):
    """What one event is worth to some roles."""

    event: EventName = Field(description="The event")
    points: float = Field(
        ge=-10, le=10, description="Its points: a bonus from 0 to 10, a malus from -10 to 0"
    )
    roles: list[Role] = Field(min_length=1, description="Who it applies to: P, D, C and A")

    @model_validator(mode="after")
    def _makes_sense(self) -> Self:
        if self.event in _BONUSES and self.points < 0:
            raise ValueError(f"{self.event} is a bonus, so its points can't be negative")
        if self.event not in _BONUSES and self.points > 0:
            raise ValueError(f"{self.event} is a malus, so its points can't be positive")
        if self.event in _KEEPERS_ONLY and set(self.roles) != {"P"}:
            raise ValueError(f"{self.event} is a keeper's, so it can't apply to other roles")
        return self


class LeagueRules(Contract):
    """A league's rules: one table of events, and what a lineup needs. An event left out isn't scored."""

    __version__ = "2.0.0"

    events: list[EventRow] = Field(
        min_length=1,
        description="Every event this league scores, with its points and the roles they apply to. An event "
        "left out isn't scored. For different values by role, give one row per value",
    )
    lineup: LineupRules | None = Field(
        default=None,
        description="What a lineup needs: thresholds, the bench, substitutions and formations. Not needed "
        "for 'X or Y?'. A call without it, or with only some of it, keeps what's stored",
    )

    @model_validator(mode="before")
    @classmethod
    def _from_the_earlier_form(cls, data: Any) -> Any:
        """Rules stored as ten fixed values, in a user's file or a decision log line, are the same table."""
        if not isinstance(data, Mapping) or not _EARLIER_VALUES.keys() & data.keys():
            return data
        if "events" in data:
            raise ValueError("give a league's rules either as events or in the earlier form, not both")
        rows: list[dict[str, Any]] = []
        for event, roles in _EARLIER_VALUES.items():
            if event not in data:
                continue
            value = data[event]
            if isinstance(value, Mapping):
                rows += [
                    {"event": event, "points": points, "roles": [_EARLIER_ROLES[name]]}
                    for name, points in value.items()
                ]
            else:
                rows.append({"event": event, "points": value, "roles": list(roles)})
        return {key: value for key, value in data.items() if key not in _EARLIER_VALUES} | {"events": rows}

    @model_validator(mode="after")
    def _one_row_per_event_and_role(self) -> Self:
        seen: set[tuple[str, str]] = set()
        for row in self.events:
            for role in row.roles:
                if (row.event, role) in seen:
                    raise ValueError(f"{row.event} is set twice for {role}")
                seen.add((row.event, role))
        return self
