"""Name resolution (design C4; R1.2, R1.3).

Names match ignoring case, accents, spacing and punctuation. A name resolves to a player when it equals his
name, or when one name's words all appear in the other's: "Rossi" finds "Marco Rossi" if no other Rossi is
known, and "Giorgio Bianchi" finds a profile written "Bianchi". A single letter is an initial, so "Rossi M."
and "Marco R." both find "Marco Rossi". But an initial never stands in for a whole name: of the two names,
the one with fewer whole words must have each of them in the other. So an outlet's "SKORUPSKI L" finds
Skorupski and not Libra, whom the initial would pair with once every listed player is known (mvp-roles task
2.2). The two sites' spellings meet too: a hyphen splits a name ("MILINKOVIC V" finds "Milinkovic-Savic V."),
and whole words may run together ("DEL PRATO E" finds "Delprato"). More than one match gives the candidates
instead of a guess.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict

from fantadamus.core.names import name_key


class KnownPlayer(BaseModel):
    """A player the lake has a profile for."""

    model_config = ConfigDict(frozen=True)

    player_id: int
    name: str
    club: str


class Resolution(BaseModel):
    player: KnownPlayer | None
    """The player, when exactly one matches."""
    candidates: list[KnownPlayer]
    """Every match when more than one does; empty when exactly one or none does."""


_SEPARATORS = re.compile(r"[\s\-]+")


def _words(name: str) -> list[str]:
    return [key for key in map(name_key, _SEPARATORS.split(name)) if key]


def _whole(words: list[str]) -> list[str]:
    return [word for word in words if len(word) > 1]


def _spellings(words: list[str]) -> list[list[str]]:
    """The words as written, and with the whole words run together: "Del Prato" is also "Delprato"."""
    whole = _whole(words)
    return (
        [words, ["".join(whole), *(word for word in words if len(word) == 1)]] if len(whole) > 1 else [words]
    )


def _pairs(a: str, b: str) -> bool:
    """A word pairs with the same word or with its initial."""
    return a == b or ((len(a) == 1) != (len(b) == 1) and a[0] == b[0])


def _covers(small: list[str], large: list[str]) -> bool:
    """Every word of `small` pairs with its own word of `large`, whole words first."""
    free = list(large)
    for word in sorted(small, key=len, reverse=True):
        partner = next((other for other in free if other == word), None)
        partner = partner or next((other for other in free if _pairs(word, other)), None)
        if partner is None:
            return False
        free.remove(partner)
    return True


def _whole_words(a: list[str], b: list[str]) -> bool:
    """The name with fewer whole words (more than one letter) has each of them in the other."""
    small, large = sorted((_whole(a), _whole(b)), key=len)
    free = list(large)
    for word in small:
        if word not in free:
            return False
        free.remove(word)
    return True


def _match(a: list[str], b: list[str]) -> bool:
    return _whole_words(a, b) and (_covers(a, b) or _covers(b, a))


def resolve(name: str, players: Iterable[KnownPlayer]) -> Resolution:
    """The player `name` refers to, or the candidates when it could be more than one."""
    words = _words(name)
    known = sorted(set(players), key=lambda player: player.player_id)
    exact = [player for player in known if words and name_key(player.name) == name_key(name)]
    matches = exact or [
        player
        for player in known
        if words
        and any(
            _match(ours, theirs) for ours in _spellings(words) for theirs in _spellings(_words(player.name))
        )
    ]
    if len(matches) == 1:
        return Resolution(player=matches[0], candidates=[])
    return Resolution(player=None, candidates=matches)
