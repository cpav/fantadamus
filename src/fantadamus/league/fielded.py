"""What each user really fielded in a round, kept privately beside their squads (mvp-review design C4; R1).

One JSON file per pseudonymous user under the git-ignored `data/local/league/`. A fielded lineup says what a
named team did, so it never reaches the repository, fixtures or committed logs.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from fantadamus.contracts.types import UtcDatetime
from fantadamus.contracts.xy.league import LineupRules
from fantadamus.core.files import temporary_beside
from fantadamus.core.names import name_key
from fantadamus.domains.players.resolve import KnownPlayer, resolve
from fantadamus.domains.review import Advice, Picked, formation_of
from fantadamus.league.rules import DEFAULT_ROOT, user_file
from fantadamus.league.squads import StoredSquad

ELEVEN = 11


class FieldedLineup(BaseModel):
    round: int
    team: str
    formation: str
    starters: list[int]
    bench: list[int]
    """In the order the user put it."""
    captain: int | None = None
    vice: int | None = None
    as_advised: bool = False
    saved_at: UtcDatetime

    def picked(self) -> Picked:
        return Picked(self.formation, tuple(self.starters), tuple(self.bench), self.captain, self.vice)


class Refused(BaseModel):
    reason: str


class Choose(BaseModel):
    unresolved: dict[str, list[KnownPlayer]]
    """Each name that could be more than one player of the squad, with who it could be."""


class _Fielded(BaseModel):
    lineups: dict[str, FieldedLineup] = {}


def _key(team: str, round: int) -> str:
    return f"{name_key(team)}:{round}"


class FieldedStore:
    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def _path(self, user: str) -> Path:
        return user_file(self.root, user, "-fielded.json")

    def _read(self, user: str) -> _Fielded:
        path = self._path(user)
        return (
            _Fielded.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else _Fielded()
        )

    def get(self, user: str, team: str, round: int) -> FieldedLineup | None:
        return self._read(user).lineups.get(_key(team, round))

    def set(self, user: str, lineup: FieldedLineup) -> FieldedLineup:
        """Store it, replacing what the user said before for the same team and round."""
        fielded = self._read(user)
        fielded.lineups[_key(lineup.team, lineup.round)] = lineup
        path = self._path(user)
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = temporary_beside(path)
        temporary.write_text(fielded.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        return lineup


def as_advised(advice: Advice, *, round: int, team: str, at: dt.datetime) -> FieldedLineup:
    """What the user fielded when they followed the advice (R1.2)."""
    return FieldedLineup(
        round=round,
        team=team,
        formation=advice.formation,
        starters=advice.starters,
        bench=advice.bench,
        captain=advice.captain,
        vice=advice.vice,
        as_advised=True,
        saved_at=at,
    )


def fielded_lineup(
    squad: StoredSquad,
    rules: LineupRules,
    *,
    round: int,
    starters: Sequence[str],
    bench: Sequence[str],
    captain: str | None,
    vice: str | None,
    at: dt.datetime,
) -> FieldedLineup | Refused | Choose:
    """The lineup the names mean, as the league could have fielded it (R1.1, R1.3)."""
    known = [
        KnownPlayer(player_id=player.player_id, name=player.name, club=player.club)
        for player in squad.players
    ]
    found: dict[str, int] = {}
    unresolved: dict[str, list[KnownPlayer]] = {}
    for name in dict.fromkeys([*starters, *bench, *(choice for choice in (captain, vice) if choice)]):
        resolution = resolve(name, known)
        if resolution.player is not None:
            found[name] = resolution.player.player_id
        elif resolution.candidates:
            unresolved[name] = resolution.candidates
        else:
            return Refused(reason=f"{name} isn't in this squad")
    if unresolved:
        return Choose(unresolved=unresolved)
    eleven, kept = [found[name] for name in starters], [found[name] for name in bench]
    problem = _cant_field(squad, rules, eleven, kept)
    if problem is not None:
        return Refused(reason=problem)
    roles = {player.player_id: player.role for player in squad.players}
    wearing, covering = (found[choice] if choice else None for choice in (captain, vice))
    for who, player in (("the captain", wearing), ("the vice", covering)):
        if player is not None and player not in eleven:
            return Refused(reason=f"{who} must start")
    if wearing is not None and wearing == covering:
        return Refused(reason="the vice can't be the captain")
    return FieldedLineup(
        round=round,
        team=squad.team,
        formation=formation_of(roles, eleven),
        starters=eleven,
        bench=kept,
        captain=wearing,
        vice=covering,
        saved_at=at,
    )


def _cant_field(squad: StoredSquad, rules: LineupRules, eleven: list[int], bench: list[int]) -> str | None:
    """Why the league couldn't field this, or None if it could."""
    names = {player.player_id: player.name for player in squad.players}
    twice = [player for player, times in Counter([*eleven, *bench]).items() if times > 1]
    if twice:
        return f"{names[twice[0]]} is listed twice"
    if len(eleven) != ELEVEN:
        return f"an eleven needs {ELEVEN} players: got {len(eleven)}"
    roles = {player.player_id: player.role for player in squad.players}
    keepers = sum(roles[player] == "P" for player in eleven)
    if keepers != 1:
        return f"an eleven needs one keeper: got {keepers}"
    formation = formation_of(roles, eleven)
    if rules.formations is not None and formation not in rules.formations:
        return f"{formation} isn't a formation this league allows: {', '.join(rules.formations)}"
    if rules.bench_size is not None and len(bench) > rules.bench_size:
        return f"a bench of {len(bench)} places, and this league's has {rules.bench_size}"
    return None
