"""P1 and P2 of mvp-review: the rating found from two reads is the real one, and a round is never invented
(design C2; R2.1, R2.3)."""

from __future__ import annotations

import dataclasses

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.review import Round, Unknown, player_round
from tests.review_data import read

_HALF_POINTS = st.integers(min_value=8, max_value=18).map(lambda twice: twice / 2)  # 4 to 9


@given(
    season=st.lists(_HALF_POINTS, max_size=24),
    rating=_HALF_POINTS,
    goals=st.integers(0, 2),
    assists=st.integers(0, 2),
    yellows=st.integers(0, 1),
    reds=st.integers(0, 1),
    own_goals=st.integers(0, 1),
    keeper=st.booleans(),
)
def test_p1_the_rating_is_found(
    season: list[float],
    rating: float,
    goals: int,
    assists: int,
    yellows: int,
    reds: int,
    own_goals: int,
    keeper: bool,
) -> None:
    """Up to 24 rated games the averages alone pin the rating, and the fantasy average names an own goal."""
    earlier = 1 if season else 0  # a goal, or a keeper's goals conceded, come with a rating
    before = read(season, keeper=keeper, goals=earlier, conceded=3 * earlier if keeper else 0)
    after = read(
        [*season, rating],
        keeper=keeper,
        goals=earlier + goals,
        assists=assists,
        yellows=yellows,
        reds=reds,
        own_goals=own_goals,
        conceded=3 * earlier + 1 if keeper else 0,
    )
    found = player_round(before, after)
    assert isinstance(found, Round)
    assert found.rating == rating
    assert found.events.own_goals == own_goals


@given(season=st.lists(_HALF_POINTS, min_size=25, max_size=40), rating=_HALF_POINTS)
def test_p1_late_in_the_season_never_a_wrong_rating(season: list[float], rating: float) -> None:
    found = player_round(read(season), read([*season, rating]))
    assert isinstance(found, Unknown) or found.rating == rating


@given(
    season=st.lists(_HALF_POINTS, max_size=20),
    more=st.lists(_HALF_POINTS, min_size=2, max_size=3),
    field=st.sampled_from(["goals", "assists", "yellows", "penalties_scored", "penalties_taken", "conceded"]),
)
def test_p2_a_round_is_never_invented(season: list[float], more: list[float], field: str) -> None:
    before = read(season, goals=2, assists=2, yellows=2, penalties=(2, 2), conceded=2, keeper=True)
    assert isinstance(player_round(before, read([*season, *more], goals=2, keeper=True)), Unknown)
    lower = dataclasses.replace(before, **{field: getattr(before, field) - 1})
    assert player_round(before, lower) == Unknown("the page corrected a figure")
