"""Many sources, compared (mvp-collect design C12; R5.1 to R5.3).

Fixtures and the table have one true value. The highest-ranked source wins (Fantacalcio.it, then
Fantacalcio-Online, then Wikipedia, then any other), each with its newest read, and `disagreement` lists the
sources' values when they differ, for the answer's notes (R5.1).

Every published probability carries a `Confidence`: how many sources gave it, how far apart they were, and a
label. A player's chance of starting comes from the outlets, unless the official lineup has settled it; his
team's win chance and xG from the odds pages; his chance of scoring takes the weaker of the two (R5.3).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from fantadamus.core.urls import url_host
from fantadamus.domains.availability.consensus import Availability
from fantadamus.domains.facts import SilverRow
from fantadamus.domains.odds.gold import TeamXg
from fantadamus.engine.constants import ODDS_DISPUTED_SPREAD

_RANKED = (
    ("fantacalcio.it", "Fantacalcio.it"),
    ("fantacalcio-online.com", "Fantacalcio-Online"),
    ("wikipedia.org", "Wikipedia"),
)

Label = Literal["official", "agree", "disputed", "one source"]
_STRENGTH: dict[Label, int] = {"disputed": 0, "one source": 1, "agree": 2, "official": 3}


def _ranked(source_url: str) -> tuple[int, str]:
    """The source's rank (0 is best) and the name the answer gives it."""
    host = url_host(source_url) or source_url
    for position, (domain, name) in enumerate(_RANKED):
        if host == domain or host.endswith("." + domain):
            return position, name
    return len(_RANKED), host


def best_by[R: SilverRow, K](rows: Iterable[R], as_of: dt.datetime, key: Callable[[R], K]) -> dict[K, R]:
    """For each key, the row from the highest-ranked source, its newest read at or before `as_of`; ties go to
    the higher content hash."""
    best: dict[K, R] = {}

    def order(row: R) -> tuple[int, dt.datetime, str]:
        return -_ranked(row.source_url)[0], row.captured_at, row.content_sha256

    for row in rows:
        if row.captured_at <= as_of:
            current = best.get(key(row))
            if current is None or order(row) > order(current):
                best[key(row)] = row
    return best


def disagreement[R: SilverRow](
    rows: Iterable[R], as_of: dt.datetime, what: str, show: Callable[[R], str]
) -> str | None:
    """When the sources' newest values for one fact differ: `what` and each source's value, the one used
    first, e.g. "Alfa v Beta kickoff: Fantacalcio.it 20:45, Fantacalcio-Online 20:30"."""
    newest = best_by(rows, as_of, key=lambda row: _ranked(row.source_url)[1])
    values = sorted((_ranked(row.source_url)[0], name, show(row)) for name, row in newest.items())
    if len({value for _, _, value in values}) <= 1:
        return None
    return f"{what}: " + ", ".join(f"{name} {value}" for _, name, value in values)


class Confidence(BaseModel):
    """How sure a probability is: how many sources gave it, how far apart they were, and in a word."""

    model_config = ConfigDict(frozen=True)

    sources: int
    spread: float
    label: Label


def of_outlets(present: Availability) -> Confidence:
    """A chance of starting: settled by the official lineup, or the outlets' agreement."""
    if present.official is not None:
        return Confidence(sources=1, spread=0.0, label="official")
    sources = len(present.outlets)
    label: Label = "one source" if sources == 1 else "disputed" if present.disputed else "agree"
    return Confidence(sources=sources, spread=present.spread, label=label)


def of_odds(xg: TeamXg) -> Confidence:
    """A team's win chance and xG: the odds pages' agreement; team form alone is one source."""
    if not xg.from_odds:
        return Confidence(sources=1, spread=0.0, label="one source")
    sources = len(xg.sources)
    label: Label = (
        "one source" if sources == 1 else "disputed" if xg.spread >= ODDS_DISPUTED_SPREAD else "agree"
    )
    return Confidence(sources=sources, spread=xg.spread, label=label)


def weaker(first: Confidence, second: Confidence) -> Confidence:
    """The less sure of two: disputed, then one source, then agree, then official."""
    return first if _STRENGTH[first.label] <= _STRENGTH[second.label] else second
