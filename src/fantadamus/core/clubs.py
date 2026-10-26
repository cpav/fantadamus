"""The league's clubs and the spellings outlets use for them, from `config/clubs.toml` (design C1).

Every submit tool maps club names through `Clubs.key`, so each club has one canonical key, and an unknown
name is rejected with the list of known clubs.
"""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass

from fantadamus.core.names import name_key

_KEY = re.compile(r"[a-z]+")


class UnknownClubError(ValueError):
    """A club name that is no spelling of a known club."""


@dataclass(frozen=True)
class Clubs:
    names: Mapping[str, str]
    """Canonical key → the name shown in answers."""
    spellings: Mapping[str, str]
    """`name_key` of every accepted spelling → canonical key."""

    @classmethod
    def from_toml(cls, text: str) -> Clubs:
        """Parse `[clubs.<key>]` tables, each with a `name` and optional `aliases`."""
        table = tomllib.loads(text).get("clubs")
        if not isinstance(table, dict) or not table:
            raise ValueError("clubs: expected [clubs.<key>] tables")
        names: dict[str, str] = {}
        spellings: dict[str, str] = {}
        for key, club in table.items():
            name, aliases = club.get("name"), club.get("aliases", [])
            if not _KEY.fullmatch(key) or not isinstance(name, str) or not name_key(name):
                raise ValueError(f"clubs: [clubs.{key}] needs a lower-case key and a name")
            if not isinstance(aliases, list) or not all(isinstance(a, str) and name_key(a) for a in aliases):
                raise ValueError(f"clubs: [clubs.{key}] aliases must be non-empty names")
            names[key] = name
            for spelling in {name_key(s) for s in (key, name, *aliases)}:
                if spellings.setdefault(spelling, key) != key:
                    raise ValueError(
                        f"clubs: {spelling!r} is a spelling of both {spellings[spelling]} and {key}"
                    )
        return cls(names=names, spellings=spellings)

    def key(self, name: str) -> str:
        """The canonical key for any accepted spelling of a club."""
        try:
            return self.spellings[name_key(name)]
        except KeyError:
            known = ", ".join(sorted(self.names.values()))
            raise UnknownClubError(f"unknown club {name!r}; known clubs: {known}") from None
