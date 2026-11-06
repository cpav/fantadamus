"""Each user's squads, kept privately, by team name (mvp-lineup design C3; R1).

One JSON file per pseudonymous user under the git-ignored `data/local/league/`. Team names and rosters are
personal data about league members, so they never reach the repository, fixtures or committed logs.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel

from fantadamus.contracts.types import Role, UtcDatetime
from fantadamus.contracts.xy.league import formation_lines
from fantadamus.core.clubs import Clubs, UnknownClubError
from fantadamus.core.files import temporary_beside
from fantadamus.core.names import name_key
from fantadamus.domains.players.resolve import KnownPlayer, resolve
from fantadamus.league.rules import DEFAULT_ROOT, user_file

MINE = "mine"
"""The user's own squad; any other name is a league-mate's (R1.5)."""
_WITH_CLUB = re.compile(r"(?P<name>.+?)\s*\((?P<club>[^()]+)\)\s*")


class SquadPlayer(BaseModel):
    player_id: int
    name: str
    """As it was written when the squad was stored."""
    club: str
    role: Role


class StoredSquad(BaseModel):
    team: str
    saved_at: UtcDatetime
    players: list[SquadPlayer]


class _Squads(BaseModel):
    teams: dict[str, StoredSquad] = {}


def _team_key(team: str) -> str:
    key = name_key(team)
    if not key:
        raise ValueError(f"a team needs a name, got {team!r}")
    return key


class SquadStore:
    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def _path(self, user: str) -> Path:
        return user_file(self.root, user, "-squads.json")

    def _read(self, user: str) -> _Squads:
        path = self._path(user)
        return _Squads.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else _Squads()

    def get(self, user: str, team: str = MINE) -> StoredSquad | None:
        return self._read(user).teams.get(_team_key(team))

    def set(self, user: str, team: str, players: Sequence[SquadPlayer], *, at: dt.datetime) -> StoredSquad:
        """Store the team's squad, replacing the one it had; the user's other squads stay."""
        squads = self._read(user)
        stored = StoredSquad(team=team, saved_at=at, players=list(players))
        squads.teams[_team_key(team)] = stored
        path = self._path(user)
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = temporary_beside(path)
        temporary.write_text(squads.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
        return stored


class SquadMatch(BaseModel):
    players: list[KnownPlayer]
    """Everyone, by ID; or nobody, if any name failed (R1.2)."""
    unresolved: dict[str, list[KnownPlayer]]
    """Each name that failed, with the players it could be: none if nobody matched, one if he's listed
    twice."""


def match_squad(names: Iterable[str], known: Sequence[KnownPlayer], clubs: Clubs) -> SquadMatch:
    """The players `names` mean. A name may give its club in brackets: "Rossi (Inter)"."""
    found: dict[str, KnownPlayer] = {}
    unresolved: dict[str, list[KnownPlayer]] = {}
    for written in names:
        given = _WITH_CLUB.fullmatch(written)
        name, among = written, known
        if given:
            name = given["name"]
            try:
                club = clubs.key(given["club"])
            except UnknownClubError:
                unresolved[written] = []
                continue
            among = [player for player in known if player.club == club]
        resolution = resolve(name, among)
        if resolution.player is None:
            unresolved[written] = resolution.candidates
        else:
            found[written] = resolution.player
    times = Counter(player.player_id for player in found.values())
    unresolved |= {written: [player] for written, player in found.items() if times[player.player_id] > 1}
    players = [] if unresolved else sorted(found.values(), key=lambda player: player.player_id)
    return SquadMatch(players=players, unresolved=unresolved)


def cannot_field(formations: Iterable[str], roles: Mapping[Role, int]) -> list[str]:
    """What the squad can't field: no keeper, or a formation the league allows (R1.3)."""
    warnings = [] if roles.get("P") else ["No keeper: a lineup can't be fielded without one."]
    has = roles.get("D", 0), roles.get("C", 0), roles.get("A", 0)
    for formation in formations:
        lines = formation_lines(formation)
        if any(needed > held for needed, held in zip(lines, has, strict=True)):
            warnings.append(
                f"Can't field {formation}: it needs {lines[0]} defenders, {lines[1]} midfielders and "
                f"{lines[2]} forwards, and the squad has {has[0]}, {has[1]} and {has[2]}."
            )
    return warnings
