"""P4: an as-of read never sees a fact captured after its time, for every gold view (design C6; R7.4)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.availability import gold as availability
from fantadamus.domains.availability.silver import LineupViewRow, OfficialLineupRow
from fantadamus.domains.facts import SilverRow
from fantadamus.domains.fixtures import gold as fixtures
from fantadamus.domains.fixtures.silver import FixtureRow
from fantadamus.domains.odds import gold as odds
from fantadamus.domains.odds.silver import OddsRow
from fantadamus.domains.players.resolve import KnownPlayer
from fantadamus.domains.season import gold as season
from fantadamus.domains.season.silver import PenaltyTakerRow, PlayerSeasonRow, TeamSeasonRow

BASE = dt.datetime(2026, 10, 26, tzinfo=dt.UTC)
CLUBS = st.sampled_from(["alfa", "beta"])
NAMES = st.sampled_from(["Alfa Nove", "Alfa Dieci", "Beta Nove"])
NOVE = KnownPlayer(player_id=9, name="Alfa Nove", club="alfa")

provenance = {
    "source_url": st.sampled_from(["https://example.org/a", "https://example.org/b"]),
    "captured_at": st.integers(min_value=0, max_value=96).map(lambda hours: BASE + dt.timedelta(hours=hours)),
    "content_sha256": st.sampled_from(["a" * 64, "b" * 64, "c" * 64]),
}
share = st.floats(min_value=0.05, max_value=0.9)
count = st.integers(min_value=0, max_value=20)

ROWS: dict[str, st.SearchStrategy[Any]] = {
    "fixtures": st.builds(
        FixtureRow,
        **provenance,
        round=st.integers(1, 2),
        home=st.just("alfa"),
        away=st.just("beta"),
        kickoff_at=st.just(BASE + dt.timedelta(days=5)),
    ),
    "players": st.builds(
        PlayerSeasonRow,
        **provenance,
        player_id=st.integers(8, 10),
        name=NAMES,
        club=CLUBS,
        role=st.just("A"),
        mantra_role=st.none(),
        appearances=count,
        rated_appearances=st.just(0),
        average_rating=st.none(),
        goals=count,
        assists=count,
        yellow_cards=count,
        penalties_scored=st.just(0),
        penalties_taken=st.just(0),
    ),
    "teams": st.builds(
        TeamSeasonRow,
        **provenance,
        club=CLUBS,
        played=st.integers(1, 10),
        goals_for=count,
        goals_against=count,
    ),
    "takers": st.builds(PenaltyTakerRow, **provenance, club=CLUBS, rank=st.integers(1, 3), name=NAMES),
    "views": st.builds(
        LineupViewRow,
        **provenance,
        home=st.just("alfa"),
        away=st.just("beta"),
        outlet=st.sampled_from(["Uno", "Due"]),
        club=CLUBS,
        name=NAMES,
        status=st.sampled_from(["starter", "ballottaggio", "bench", "unavailable"]),
        share=st.just(50.0),
    ),
    "officials": st.builds(
        OfficialLineupRow,
        **provenance,
        home=st.just("alfa"),
        away=st.just("beta"),
        club=CLUBS,
        name=NAMES,
        status=st.sampled_from(["starter", "bench"]),
    ),
    "odds": st.builds(
        OddsRow,
        **provenance,
        home=st.just("alfa"),
        away=st.just("beta"),
        bookmaker=st.just("Banco"),
        p_home=share,
        p_draw=share,
        p_away=share,
        p_over=share,
        p_btts=st.none() | share,
    ),
}


Read = Callable[[Mapping[str, Sequence[Any]], dt.datetime], object]
VIEWS: dict[str, tuple[tuple[str, ...], Read]] = {
    "matches": (("fixtures",), lambda rows, as_of: fixtures.matches(rows["fixtures"], as_of)),
    "deadline": (("fixtures",), lambda rows, as_of: fixtures.deadline(rows["fixtures"], 1, as_of)),
    "known_players": (("players",), lambda rows, as_of: season.known_players(rows["players"], as_of)),
    "player_form": (("players",), lambda rows, as_of: season.player_form(rows["players"], 9, as_of)),
    "team_season": (("teams",), lambda rows, as_of: season.team_season(rows["teams"], "alfa", as_of)),
    "penalty_order": (("takers",), lambda rows, as_of: season.penalty_order(rows["takers"], "alfa", as_of)),
    "team_xg": (
        ("odds", "teams"),
        lambda rows, as_of: odds.team_xg(rows["odds"], rows["teams"], home="alfa", away="beta", as_of=as_of),
    ),
    "availability": (
        ("views", "officials"),
        lambda rows, as_of: availability.availability(
            NOVE,
            home="alfa",
            away="beta",
            views=rows["views"],
            officials=rows["officials"],
            players=[NOVE],
            as_of=as_of,
        ),
    ),
}


@pytest.mark.parametrize("view", sorted(VIEWS))
@given(data=st.data(), hours=st.integers(min_value=0, max_value=96))
def test_p4_as_of_never_sees_later_facts(view: str, data: st.DataObject, hours: int) -> None:
    tables, read = VIEWS[view]
    lake: dict[str, list[SilverRow]] = data.draw(
        st.fixed_dictionaries({table: st.lists(ROWS[table], max_size=6) for table in tables})
    )
    as_of = BASE + dt.timedelta(hours=hours)
    known = {table: [row for row in rows if row.captured_at <= as_of] for table, rows in lake.items()}
    assert read(lake, as_of) == read(known, as_of)
