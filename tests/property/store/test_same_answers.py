"""P4 of mvp-store: for any history of submissions and any time asked about, each player's availability, each
match's team xG and each player's season figures are the same from the reduced read as from the full one
(design C5; R3.2, R3.5). The reduced read is `newest_submissions` with each domain's own `newest_by`, which P5
holds DuckDB's read to; this property needs no file, so it runs with the fast tests."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.availability.gold import availability
from fantadamus.domains.availability.silver import (
    LINEUP_VIEWS,
    OFFICIAL_LINEUPS,
    OUTLET_VIEWS,
    LineupViewRow,
    OfficialLineupRow,
    OutletViewRow,
)
from fantadamus.domains.facts import Domain, SilverRow, latest_by
from fantadamus.domains.freshness import FACTS_WINDOW
from fantadamus.domains.odds.gold import team_xg
from fantadamus.domains.odds.silver import ODDS, OddsRow
from fantadamus.domains.players.resolve import KnownPlayer
from fantadamus.domains.season.gold import known_players
from fantadamus.domains.season.silver import PLAYER_SEASONS, SEASON_STATS, PlayerSeasonRow
from fantadamus.mcp.advisor import _fresh
from tests.store_lake import newest_submissions

START = dt.datetime(2026, 11, 1, tzinfo=dt.UTC)
STEP = dt.timedelta(hours=6)
PAGES = ("https://example.org/a", "https://example.org/b")
OUTLETS = ("Gazzetta", "gazzetta", "Sky")
"""Two spellings of one outlet: the read groups by spelling, the answer by the outlet's normalised name."""
BOOKMAKERS = ("Book", "book", "Other")
MATCHES = (("alfa", "beta"), ("gamma", "delta"))
KICKOFFS = (START + dt.timedelta(days=12), START + dt.timedelta(days=12, hours=3))
PLAYERS = [
    KnownPlayer(player_id=10 * number + index, name=f"{club.title()} {word}", club=club)
    for number, club in enumerate(("alfa", "beta", "gamma", "delta"), 1)
    for index, word in enumerate(("Uno", "Due"), 1)
]
PLAYING = [[player for player in PLAYERS if player.club in match] for match in MATCHES]

times = st.integers(0, 60)
"""When a page was read, in six-hour steps: fifteen days, so that some rows fall outside a window."""
provenance = st.tuples(st.sampled_from(PAGES), times, st.integers(0, 3))
"""A page, a time and a content hash: few of each, so that ties and the same content come back."""


def _source(found: tuple[str, int, int]) -> dict[str, Any]:
    page, step, content = found
    return {"source_url": page, "captured_at": START + step * STEP, "content_sha256": f"{content:064x}"}


@dataclass(frozen=True)
class History:
    outlet_views: list[OutletViewRow]
    views: list[LineupViewRow]
    officials: list[OfficialLineupRow]
    odds: list[OddsRow]
    profiles: list[PlayerSeasonRow]
    statistics: list[PlayerSeasonRow]


def _season(source: dict[str, Any], player: KnownPlayer, goals: int) -> PlayerSeasonRow:
    return PlayerSeasonRow(
        **source,
        player_id=player.player_id,
        name=player.name,
        club=player.club,
        role="A",
        mantra_role=None,
        appearances=9,
        rated_appearances=8,
        average_rating=6.0,
        goals=goals,
        assists=1,
        yellow_cards=0,
        penalties_scored=0,
        penalties_taken=0,
    )


@st.composite
def histories(draw: st.DrawFn) -> History:
    """Submissions of every kind, each about one match, and each holding some of its players."""
    found = History([], [], [], [], [], [])
    for _ in range(draw(st.integers(0, 12))):
        kind = draw(st.sampled_from(["sheet", "lineup", "official", "odds", "profile", "statistics"]))
        source = _source(draw(provenance))
        match = draw(st.integers(0, 1))
        home, away = MATCHES[match]
        some = draw(st.lists(st.sampled_from(PLAYING[match]), min_size=1, unique=True))
        if kind == "sheet":
            outlet = draw(st.sampled_from(OUTLETS))
            for player in some:
                percent = draw(st.sampled_from([None, 5.0, 45.0, 90.0]))
                found.outlet_views.append(
                    OutletViewRow(
                        **source,
                        home=home,
                        away=away,
                        outlet=outlet,
                        club=player.club,
                        name=player.name,
                        role=None,
                        percent=percent,
                        unavailable=percent is None,
                    )
                )
        elif kind == "lineup":
            outlet = draw(st.sampled_from(OUTLETS))
            for player in some:
                status = draw(st.sampled_from(["starter", "bench", "ballottaggio", "unavailable"]))
                found.views.append(
                    LineupViewRow(
                        **source,
                        home=home,
                        away=away,
                        outlet=outlet,
                        club=player.club,
                        name=player.name,
                        status=status,
                        share=50.0 if status == "ballottaggio" else None,
                        contest=0 if status == "ballottaggio" else None,
                    )
                )
        elif kind == "official":
            unnamed = draw(st.sampled_from([0, 1]))
            found.officials.extend(
                OfficialLineupRow(
                    **source,
                    home=home,
                    away=away,
                    club=player.club,
                    name=player.name,
                    status=draw(st.sampled_from(["starter", "bench"])),
                    unnamed_starters=unnamed,
                )
                for player in some
            )
        elif kind == "odds":
            chance = draw(st.floats(0.2, 0.6))
            level = draw(st.floats(0.15, 0.3))
            found.odds.append(
                OddsRow(
                    **source,
                    home=home,
                    away=away,
                    bookmaker=draw(st.sampled_from(BOOKMAKERS)),
                    p_home=chance,
                    p_draw=level,
                    p_away=1 - chance - level,
                    p_over=draw(st.sampled_from([None, 0.55])),
                    p_btts=None,
                )
            )
        else:  # a profile holds one player; a read of the statistics page, many
            chosen = some[:1] if kind == "profile" else some
            rows = [_season(source, player, draw(st.integers(0, 9))) for player in chosen]
            (found.profiles if kind == "profile" else found.statistics).extend(rows)
    return found


def _read(found: History, since: dt.datetime, until: dt.datetime, *, reduced: bool) -> History:
    """What an answer reads: every row of the window, or each page's newest submission for each value of the
    domain's own `newest_by`."""

    def read[R: SilverRow](rows: Sequence[R], domain: Domain[Any, Any]) -> list[R]:
        if reduced:
            return newest_submissions(rows, domain.newest_by, since, until)
        return [row for row in rows if since <= row.captured_at <= until]

    return History(
        read(found.outlet_views, OUTLET_VIEWS),
        read(found.views, LINEUP_VIEWS),
        read(found.officials, OFFICIAL_LINEUPS),
        read(found.odds, ODDS),
        read(found.profiles, PLAYER_SEASONS),
        read(found.statistics, SEASON_STATS),
    )


def _numbers(
    read: History, as_of: dt.datetime, confirmed: dict[str, dt.datetime], any_age: bool
) -> list[Any]:
    """Everything an answer takes from these tables, as `gather` and `_match_facts` take it."""
    said: list[Any] = []
    for (home, away), kickoff, playing in zip(MATCHES, KICKOFFS, PLAYING, strict=True):
        views = _fresh(read.views, "probable_lineups", as_of, kickoff, confirmed, any_age=any_age)
        sheets = _fresh(read.outlet_views, "probable_lineups", as_of, kickoff, confirmed, any_age=any_age)
        for player in playing:
            fresh, stale = (
                availability(
                    player,
                    home=home,
                    away=away,
                    views=lineups,
                    outlet_views=percentages,
                    officials=read.officials,
                    players=PLAYERS,
                    as_of=as_of,
                )
                for lineups, percentages in ((views, sheets), (read.views, read.outlet_views))
            )
            said += [fresh, stale is not None]  # stale or missing: is there a lineup, whatever its age
        odds = _fresh(read.odds, "match_odds", as_of, kickoff, confirmed, any_age=any_age)
        said += [
            team_xg(odds, [], home=home, away=away, as_of=as_of),
            any(row.home == home and row.captured_at <= as_of for row in read.odds),
        ]
    seasons = [*read.profiles, *read.statistics]
    forms = latest_by(seasons, as_of, key=lambda row: row.player_id)
    said += [forms, known_players(seasons, as_of)]
    said += [  # by player: answers look a player's figures up, and never go through them in order
        (player, bool(_fresh([form], "player_season", as_of, confirmed=confirmed, any_age=any_age)))
        for player, form in sorted(forms.items())
    ]
    return said


@given(
    found=histories(),
    asked=times,
    confirmed=st.dictionaries(st.sampled_from(PAGES), times),
    any_age=st.booleans(),
)
def test_p4_the_same_numbers_both_ways(
    found: History, asked: int, confirmed: dict[str, int], any_age: bool
) -> None:
    as_of = START + asked * STEP
    since = as_of - FACTS_WINDOW
    seen = {page: START + step * STEP for page, step in confirmed.items() if START + step * STEP <= as_of}
    full = _numbers(_read(found, since, as_of, reduced=False), as_of, seen, any_age)
    assert _numbers(_read(found, since, as_of, reduced=True), as_of, seen, any_age) == full
