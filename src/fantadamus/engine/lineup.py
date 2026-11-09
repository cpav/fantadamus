"""Arranging a lineup: the eleven and the bench for one formation (mvp-lineup design C6; R3; method §A3, §A6).

Each role is sorted by the key: the top fill the formation's places and the rest go to the bench in order. A
club's keepers are one place: the likelier starter is fielded, whatever their keys, and the other goes first
among the bench keepers, since he plays exactly when the starter doesn't."""

from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence

from pydantic import BaseModel, ConfigDict

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.league import LineupRules, formation_lines

ROLES: tuple[Role, ...] = ("P", "D", "C", "A")
ROLE_WORDS = {"P": "keeper", "D": "defender", "C": "midfielder", "A": "forward"}


class CannotFieldError(ValueError):
    """A lineup that can't be fielded; the message says why."""


class Candidate(BaseModel):
    """A squad player as the ordering rule sees him."""

    model_config = ConfigDict(frozen=True)

    player_id: int
    name: str
    role: Role
    club: str
    p_start: float
    p_cameo: float
    key: float


class Arrangement(BaseModel):
    """Who plays in one formation."""

    model_config = ConfigDict(frozen=True)

    formation: str
    starters: tuple[Candidate, ...]
    """By role, each role by key."""
    bench: tuple[Candidate, ...]
    """In the order substitutes are taken: each role by key, and by key across roles."""
    left_off: tuple[Candidate, ...]
    """Those a smaller bench has no place for."""
    captain: int | None = None
    """The captain the user named; without one, the simulation picks the captain and the vice."""
    vice: int | None = None
    """His vice, when named with him; without one, the simulation picks the best vice for him."""


def _rank(player: Candidate) -> tuple[bool, float, int]:
    """A player with no chance of a rating comes last, whatever his value. A lower ID settles a tie."""
    return player.p_start + player.p_cameo > 0, player.key, -player.player_id


def _in_order(players: Iterable[Candidate], role: Role) -> list[Candidate]:
    """Best first. Keepers go by club: the likeliest starter of the best club, then his club-mates."""
    of_role = [player for player in players if player.role == role]
    if role != "P":
        return sorted(of_role, key=_rank, reverse=True)
    clubs: dict[str, list[Candidate]] = {}
    for keeper in of_role:
        clubs.setdefault(keeper.club, []).append(keeper)
    units = [
        sorted(unit, key=lambda keeper: (keeper.p_start, *_rank(keeper)), reverse=True)
        for unit in clubs.values()
    ]
    return [
        keeper for unit in sorted(units, key=lambda unit: _rank(unit[0]), reverse=True) for keeper in unit
    ]


def _fielded(
    order: Sequence[Candidate], places: int, start: Collection[int], leave_out: Collection[int]
) -> list[Candidate]:
    """Those told to start, then the best of the rest, in the role's own order."""
    forced = [player for player in order if player.player_id in start]
    free = [player for player in order if player.player_id not in start and player.player_id not in leave_out]
    chosen = {player.player_id for player in (*forced, *free[: max(places - len(forced), 0)])}
    return [player for player in order if player.player_id in chosen]


def _merged(lines: dict[Role, list[Candidate]]) -> list[Candidate]:
    """One order for the whole bench, by key, without changing the order within a role."""
    heads = {role: list(players) for role, players in lines.items() if players}
    merged = []
    while heads:
        role = max(heads, key=lambda role: _rank(heads[role][0]))
        merged.append(heads[role].pop(0))
        if not heads[role]:
            del heads[role]
    return merged


def arrange(
    candidates: Sequence[Candidate],
    formation: str,
    rules: LineupRules,
    start: Collection[int] = (),
    leave_out: Collection[int] = (),
) -> Arrangement:
    """The eleven and the bench. `start` and `leave_out`, by player ID, come before the sort: whoever is left
    out of the eleven stays available for the bench."""
    known = {player.player_id for player in candidates}
    for player_id in (*start, *leave_out):
        if player_id not in known:
            raise CannotFieldError(f"player {player_id} isn't in the squad")
    both = set(start) & set(leave_out)
    if both:
        raise CannotFieldError(f"players {sorted(both)} can't both start and be left out")
    places = dict(zip(ROLES, (1, *formation_lines(formation)), strict=True))
    starters: list[Candidate] = []
    bench: dict[Role, list[Candidate]] = {}
    for role in ROLES:
        order = _in_order(candidates, role)
        forced = sum(player.player_id in start for player in order)
        if forced > places[role]:
            raise CannotFieldError(
                f"{formation} has {places[role]} {ROLE_WORDS[role]} places, and {forced} are told to start"
            )
        fielded = _fielded(order, places[role], start, leave_out)
        if len(fielded) < places[role]:
            raise CannotFieldError(
                f"{formation} needs {places[role]} {ROLE_WORDS[role]}s, and {len(fielded)} can play"
            )
        starters += fielded
        bench[role] = [player for player in order if player not in fielded]
    left_off = _make_room(bench, rules.bench_size)
    return Arrangement(
        formation=formation, starters=tuple(starters), bench=tuple(_merged(bench)), left_off=tuple(left_off)
    )


def _make_room(bench: dict[Role, list[Candidate]], size: int | None) -> list[Candidate]:
    """Take off the lowest keys until the bench fits, keeping the first of each role (R3.2)."""
    left_off: list[Candidate] = []
    while size is not None and sum(map(len, bench.values())) > size:
        spare = [player for players in bench.values() for player in players[1:]]
        lowest = min(spare, key=_rank)
        bench[lowest.role].remove(lowest)
        left_off.append(lowest)
    return left_off
