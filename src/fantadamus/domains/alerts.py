"""Alerts: has the news since the user last looked changed their lineup's call? (mvp-alerts C1 to C3)

Pure. A call is what an alert compares: the eleven, the formation, the captain and vice, and each role's first
bench place. Its chances only say why a call changed, never whether it did (R2.3).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from fantadamus.contracts.types import Role
from fantadamus.domains.availability.consensus import OfficialStatus
from fantadamus.domains.review import Advice
from fantadamus.engine.constants import ALERT_CHARACTERS
from fantadamus.engine.lineup import ROLES


@dataclass(frozen=True)
class Call:
    round: int
    formation: str
    starters: frozenset[int]
    first_on_bench: Mapping[Role, int]
    """The first bench player of each role, in the bench's order; a role with none isn't there."""
    captain: int | None
    vice: int | None
    chances: Mapping[int, float]
    """Each squad player's chance of starting, for the cause (C2)."""
    at: dt.datetime
    """When the facts behind it were read."""


def call_of(
    *,
    round: int,
    formation: str,
    starters: Iterable[int],
    bench: Sequence[int],
    roles: Mapping[int, Role],
    captain: int | None,
    vice: int | None,
    chances: Mapping[int, float],
    at: dt.datetime,
) -> Call:
    first: dict[Role, int] = {}
    for player in bench:
        role = roles.get(player)
        if role is not None:
            first.setdefault(role, player)
    return Call(round, formation, frozenset(starters), first, captain, vice, dict(chances), at)


def call_of_advice(advice: Advice, *, round: int, roles: Mapping[int, Role]) -> Call:
    """The call of a lineup the user was told, as `last_advice` finds it: an override's advice."""
    return call_of(
        round=round,
        formation=advice.formation,
        starters=advice.starters,
        bench=advice.bench,
        roles=roles,
        captain=advice.captain,
        vice=advice.vice,
        chances=advice.chances,
        at=advice.as_of,
    )


ChangeKind = Literal["swap", "in", "out", "formation", "captain", "vice", "bench"]


@dataclass(frozen=True)
class Change:
    kind: ChangeKind
    now: int | None = None
    """Who comes in, wears the armband or is first on the bench now."""
    before: int | None = None
    """Who that was."""
    role: Role | None = None
    formations: tuple[str, str] | None = None
    """Before, now."""


def changes(before: Call, after: Call, roles: Mapping[int, Role]) -> list[Change]:
    """What differs, the eleven first: a player out paired with one of his role in, then the formation, the
    captain and vice, and each role's first bench place. A captain or a bench role one call doesn't have isn't
    compared."""
    found: list[Change] = []
    left, came = before.starters - after.starters, after.starters - before.starters
    for role in (*ROLES, None):
        outs = sorted(player for player in left if roles.get(player) == role)
        ins = sorted(player for player in came if roles.get(player) == role)
        found += [Change("swap", now=new, before=old, role=role) for old, new in zip(outs, ins, strict=False)]
        found += [Change("out", before=old, role=role) for old in outs[len(ins) :]]
        found += [Change("in", now=new, role=role) for new in ins[len(outs) :]]
    if before.formation != after.formation:
        found.append(Change("formation", formations=(before.formation, after.formation)))
    armbands: tuple[tuple[ChangeKind, int | None, int | None], ...] = (
        ("captain", before.captain, after.captain),
        ("vice", before.vice, after.vice),
    )
    for kind, old, new in armbands:
        if old is not None and new is not None and old != new:
            found.append(Change(kind, now=new, before=old))
    for role in ROLES:
        old, new = before.first_on_bench.get(role), after.first_on_bench.get(role)
        if old is not None and new is not None and old != new:
            found.append(Change("bench", now=new, before=old, role=role))
    return found


@dataclass(frozen=True)
class Latest:
    """What the newest reads say about one player, each with when it was read."""

    official: OfficialStatus | None = None
    official_at: dt.datetime | None = None
    out: str | None = None
    """Why the injured or suspended page has him out."""
    banned: bool = False
    out_at: dt.datetime | None = None


CauseKind = Literal["official", "ban", "injury", "outlets"]
_STRENGTH: tuple[CauseKind, ...] = ("official", "ban", "injury", "outlets")
_SUBTITLE: dict[CauseKind | None, str] = {
    "official": "Official lineup out",
    "ban": "Ban news",
    "injury": "Injury news",
    "outlets": "Probable lineups moved",
    None: "Your call changed",
}
_OFFICIAL: dict[OfficialStatus, str] = {
    "starter": "the official lineup starts {name}",
    "bench": "the official lineup has {name} on the bench",
    "not listed": "the official lineup leaves {name} out of the squad",
}


@dataclass(frozen=True)
class Cause:
    kind: CauseKind
    text: str


def _name(names: Mapping[int, str], player: int) -> str:
    return names.get(player, f"player {player}")


def _cause_of(
    player: int, before: Call, after: Call, latest: Mapping[int, Latest], names: Mapping[int, str]
) -> Cause | None:
    name, heard = _name(names, player), latest.get(player, Latest())
    if heard.official is not None and heard.official_at is not None and heard.official_at > before.at:
        return Cause("official", _OFFICIAL[heard.official].format(name=name))
    if heard.out is not None and heard.out_at is not None and heard.out_at > before.at:
        if heard.banned:
            return Cause("ban", f"{name} is banned")
        return Cause("injury", f"the injury page has {name} out: {heard.out}")
    was, now = before.chances.get(player), after.chances.get(player)
    if was is not None and now is not None and round(was * 100) != round(now * 100):
        return Cause("outlets", f"the probable lineups give {name} {now:.0%} to start, from {was:.0%}")
    return None


def cause(
    change: Change, before: Call, after: Call, latest: Mapping[int, Latest], names: Mapping[int, str]
) -> Cause | None:
    """Why it changed, from the facts read after the call compared: of the player who lost his place, then
    the one who took it, the first with an official lineup, then the injured or suspended page, then the
    probable lineups. None when none of them says (C2)."""
    for player in (change.before, change.now):
        if player is not None:
            found = _cause_of(player, before, after, latest, names)
            if found is not None:
                return found
    return None


@dataclass(frozen=True)
class Alert:
    title: str
    subtitle: str
    text: str
    shown: int
    """How many changes are written out; the rest are counted."""


_ROLE_WORD: dict[Role, str] = {"P": "keeper", "D": "defender", "C": "midfielder", "A": "forward"}


def _action(change: Change, names: Mapping[int, str]) -> tuple[str, bool]:
    """The change in words, and whether a cause may follow it."""
    now = _name(names, change.now) if change.now is not None else ""
    before = _name(names, change.before) if change.before is not None else ""
    match change.kind:
        case "swap":
            return f"Start {now} instead of {before}", True
        case "in":
            return f"Start {now}", True
        case "out":
            return f"Bench {before}", True
        case "formation":
            was, new = change.formations or ("", "")
            return f"Play {new} instead of {was}", False
        case "captain":
            return f"Captain {now} instead of {before}", True
        case "vice":
            return f"Make {now} vice-captain instead of {before}", False
        case "bench":
            return f"{now} is now your first {_ROLE_WORD[change.role or 'D']} off the bench", False


def _more(count: int) -> str:
    return f" And {count} more change{'s' if count > 1 else ''}: ask for your lineup." if count else ""


def alert_text(
    round: int,
    found: Sequence[Change],
    causes: Sequence[Cause | None],
    names: Mapping[int, str],
    *,
    limit: int = ALERT_CHARACTERS,
) -> Alert:
    """One notification for a changed call: each change's action, then its cause the first time it's said;
    what doesn't fit in `limit` characters is counted (C3)."""
    said: set[str] = set()
    full: list[str] = []
    for change, why in zip(found, causes, strict=True):
        action, may_say = _action(change, names)
        if why is not None and may_say and why.text not in said:
            said.add(why.text)
            full.append(f"{action}: {why.text}.")
        elif change.kind == "swap":
            full.append(f"{action}, on the newest lineups and odds.")
        else:
            full.append(f"{action}.")
    text, shown = "", 0
    for sentence in full:
        longer = f"{text} {sentence}".strip()
        if len(longer + _more(len(full) - shown - 1)) > limit:
            break
        text, shown = longer, shown + 1
    if shown == 0:  # the first change alone, its cause dropped, cut if it must be
        text = f"{_action(found[0], names)[0]}."
        shown = 1
        tail = _more(len(full) - 1)
        if len(text + tail) > limit:
            text = text[: limit - len(tail) - 1] + "…"
    strongest = next((kind for kind in _STRENGTH if any(why and why.kind == kind for why in causes)), None)
    return Alert(f"Fantadamus · Round {round}", _SUBTITLE[strongest], text + _more(len(full) - shown), shown)
