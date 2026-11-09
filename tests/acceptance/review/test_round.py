"""AT-2 of mvp-review: one player's round from the statistics page read before and after it, by hand
(design C2; R2.1, R2.3)."""

from __future__ import annotations

import dataclasses

from fantadamus.domains.review import Events, Round, Unknown, player_round
from tests.review_data import read

SEASON = [6.5] * 5 + [6.0] * 4
NOTHING = Events(
    open_goals=0,
    penalties_scored=0,
    penalties_missed=0,
    assists=0,
    yellows=0,
    reds=0,
    penalties_saved=0,
    conceded=0,
    own_goals=0,
)


def test_at2_a_round_by_hand() -> None:
    """A 7 with a goal from open play and an assist; the fantasy average agrees, so no own goal."""
    before = read(SEASON, goals=3, penalties=(1, 1), assists=1, yellows=1)
    after = read([*SEASON, 7.0], goals=4, penalties=(1, 1), assists=2, yellows=1)
    assert player_round(before, after) == Round(7.0, dataclasses.replace(NOTHING, open_goals=1, assists=1))


def test_at2_a_penalty_scored_and_one_missed() -> None:
    before = read(SEASON, goals=2, penalties=(1, 1))
    after = read([*SEASON, 6.5], goals=3, penalties=(2, 3))
    found = player_round(before, after)
    assert found == Round(6.5, dataclasses.replace(NOTHING, penalties_scored=1, penalties_missed=1))


def test_at2_an_own_goal_shows_in_the_fantasy_average() -> None:
    before = read(SEASON)
    after = read([*SEASON, 5.0], own_goals=1)
    assert player_round(before, after) == Round(5.0, dataclasses.replace(NOTHING, own_goals=1))


def test_at2_a_fantasy_average_that_disagrees_otherwise_names_no_own_goal() -> None:
    """A point too many or two too many isn't an own goal: own goals are then unknown, the rating stands."""
    before, after = read(SEASON), read([*SEASON, 6.0])
    for points in (1.0, 2.0, -1.0):
        shifted = dataclasses.replace(after, fantasy=round((after.fantasy or 0.0) + points / after.rated, 2))
        assert player_round(before, shifted) == Round(6.0, dataclasses.replace(NOTHING, own_goals=None)), (
            points
        )


def test_at2_a_keeper() -> None:
    """Two conceded and a penalty saved; the fantasy average has no clean-sheet bonus to take off."""
    before = read(SEASON, keeper=True, conceded=9)
    after = read([*SEASON, 6.0], keeper=True, conceded=11, saved=1)
    assert player_round(before, after) == Round(
        6.0, dataclasses.replace(NOTHING, conceded=2, penalties_saved=1)
    )


def test_at2_a_cameo_without_a_rating() -> None:
    """No rating, so no rating to find; a yellow shown on the bench is still in his events."""
    before = read(SEASON, yellows=1)
    after = read(SEASON, yellows=2)
    assert player_round(before, after) == Round(None, dataclasses.replace(NOTHING, yellows=1))


def test_at2_late_in_the_season_the_fantasy_average_settles_it() -> None:
    """At 37 and 38 rated games the averages allow 5.5 or 6; the fantasy average allows 6 or 6.5: so 6."""
    before = dataclasses.replace(read([]), rated=37, average=6.52, fantasy=6.52)
    after = dataclasses.replace(before, rated=38, average=6.50, fantasy=6.51)
    assert player_round(before, after) == Round(6.0, NOTHING)
    unsure = player_round(dataclasses.replace(before, fantasy=None), dataclasses.replace(after, fantasy=None))
    assert unsure == Unknown("his rating could be 5.5 or 6")


def test_at2_a_read_stored_before_the_new_columns() -> None:
    """The rating still comes from the averages; red cards, saved penalties and own goals are unknown."""
    before = read(SEASON, with_new_columns=False)
    after = read([*SEASON, 6.5], with_new_columns=False)
    unknown = dataclasses.replace(NOTHING, reds=None, penalties_saved=None, own_goals=None)
    assert player_round(before, after) == Round(6.5, unknown)
    assert player_round(before, before) == Round(None, unknown)  # no rating, and no own goal known either


def test_at2_the_first_round_read_with_the_new_columns() -> None:
    """Round 12: the read before it was stored without them, the read after it with them. The rating still
    comes from the averages; what needs both reads to have them stays unknown."""
    before = read(SEASON, with_new_columns=False)
    after = read([*SEASON, 6.5])
    unknown = dataclasses.replace(NOTHING, reds=None, penalties_saved=None, own_goals=None)
    assert player_round(before, after) == Round(6.5, unknown)


def test_at2_a_player_not_yet_rated() -> None:
    """No rating before or after: nothing to read from the fantasy average, and nothing missing from it."""
    assert player_round(read([]), read([])) == Round(None, NOTHING)
    old = read([], with_new_columns=False)
    assert player_round(old, old) == Round(
        None, dataclasses.replace(NOTHING, reds=None, penalties_saved=None)
    )


def test_at2_what_cant_be_known() -> None:
    before = read(SEASON, goals=2)
    assert player_round(None, before) == Unknown("not in the read before the round")
    assert player_round(before, None) == Unknown("not in the read after the round")
    assert player_round(before, read([*SEASON, 6.0, 6.0], goals=2)) == Unknown(
        "two matches between the reads"
    )
    assert player_round(before, read([*SEASON, 6.0], goals=1)) == Unknown("the page corrected a figure")
    assert player_round(read([*SEASON, 6.0]), read(SEASON)) == Unknown("the page corrected a figure")
    odd = dataclasses.replace(
        read([*SEASON, 6.0], goals=2), average=6.29
    )  # a total 6.29 points up: 6.25 isn't a rating
    assert player_round(before, odd) == Unknown("his rating isn't on a half point")
