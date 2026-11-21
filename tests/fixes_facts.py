"""Shared by the `mvp-fixes` source tests: a player's facts built from typed stand-ins, each part carrying
only the source it would show, so that what `PlayerFacts.sources()` gathers can be checked without a lake."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import cast

from fantadamus.domains.availability.consensus import Availability
from fantadamus.domains.availability.news import News
from fantadamus.domains.context import Rested
from fantadamus.domains.facts import Source
from fantadamus.domains.fixtures.silver import FixtureRow
from fantadamus.domains.odds.gold import TeamXg
from fantadamus.domains.players.resolve import KnownPlayer
from fantadamus.domains.season.gold import PenaltyOrder
from fantadamus.domains.season.silver import PlayerSeasonRow, TeamSeasonRow
from fantadamus.mcp.advisor import PlayerFacts

AT = dt.datetime(2026, 11, 21, 8, 0, tzinfo=dt.UTC)


def source(page: str) -> Source:
    return Source(source_url=f"https://site.example/{page}", captured_at=AT, content_sha256=page)


def page_names(sources: list[Source]) -> set[str]:
    return {found.source_url.rsplit("/", 1)[1] for found in sources}


def facts(
    *,
    match: bool = True,
    outlets: int = 2,
    official: bool = False,
    odds: bool = True,
    news: bool = False,
) -> PlayerFacts:
    present = SimpleNamespace(
        outlets=[SimpleNamespace(source=source(f"outlet-{index}")) for index in range(outlets)],
        official=SimpleNamespace(source=source("official")) if official else None,
    )
    return PlayerFacts(
        player=cast(KnownPlayer, SimpleNamespace(name="Uno")),
        form=cast(PlayerSeasonRow, SimpleNamespace(source=source("statistics"))),
        table=cast(TeamSeasonRow, SimpleNamespace(source=source("table"))),
        order=cast(PenaltyOrder, SimpleNamespace(source=source("takers"))),
        match=cast(FixtureRow, SimpleNamespace(source=source("round"))) if match else None,
        present=cast(Availability, present) if match else None,
        xg=cast(TeamXg, SimpleNamespace(sources=[source("odds")])) if odds else None,
        disagreements=[],
        penalty_share=0.0,
        news=cast(News, SimpleNamespace(sources=(source("injuries"),))) if news else None,
    )


def rested() -> Rested:
    return cast(Rested, SimpleNamespace(sources=[source("cup")]))
