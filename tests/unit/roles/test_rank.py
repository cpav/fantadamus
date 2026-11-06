"""mvp-roles task 4.4: two keepers of the same club cover each other exactly (design C8; method §A6; R3.6)."""

from __future__ import annotations

import pytest

from fantadamus.engine import keepers, rank
from fantadamus.engine.rank import Scoring
from tests.roles_data import keeper

CLASSIC = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)


@pytest.mark.parametrize(("starts", "waits"), [("Alfa Uno", "Zeta Due"), ("Zeta Due", "Alfa Uno")])
def test_same_club_keepers_covered(starts: str, waits: str) -> None:
    """The likelier starter goes first, however their names sort and however the other is rated."""
    starter = keeper(name=starts, p_start=0.9)
    backup = keeper(name=waits, p_start=0.08, average_rating=7.0)  # better rated, rarely plays
    covered = keepers.compare(backup, starter, CLASSIC)
    assert covered.flip_opponent_xg is None  # one match, one opponent: only who starts decides
    verdict = covered.verdict
    assert (verdict.first, verdict.second) == (starts, waits)
    assert (verdict.label, verdict.margin) == ("covered", 0.0)
    assert not verdict.no_cover_differs
    elsewhere = keepers.compare(backup.model_copy(update={"club": "beta"}), starter, CLASSIC).verdict
    assert elsewhere.label != "covered"
    assert elsewhere.first == waits  # with no cameo, the key is his value if he plays


def test_no_cover_by_hand() -> None:
    assert rank.no_cover(0.5, 7.0, 0.3, 5.5) == pytest.approx(5.15)


def test_the_bench_can_change_the_call() -> None:
    """With the bench covering, X's higher key wins; with nobody to cover, Y's more certain rating does."""
    x = rank.Option(name="X", p_start=0.55, p_cameo=0.35, e_start=7.6, e_cameo=5.5)
    y = rank.Option(name="Y", p_start=0.90, p_cameo=0.05, e_start=6.6, e_cameo=5.5)
    result = rank.verdict(x, y)
    assert (result.first, result.no_cover_first, result.no_cover_differs) == ("X", "Y", True)
    sure = y.model_copy(update={"e_start": 8.0})
    result = rank.verdict(x, sure)
    assert (result.first, result.no_cover_first, result.no_cover_differs) == ("Y", "Y", False)


def test_who_of_a_covered_pair_plays() -> None:
    plays = rank.Option(name="A", p_start=0.9, p_cameo=0.0, e_start=6.0, e_cameo=0.0)
    out = rank.Option(name="B", p_start=0.0, p_cameo=0.0, e_start=6.0, e_cameo=0.0)
    result = rank.covering(out, plays)
    assert (result.first, result.first_plays, result.second_plays) == ("A", True, False)
    both = rank.covering(plays, out.model_copy(update={"p_start": 0.1}))
    assert (both.first_plays, both.second_plays) == (True, True)


def test_what_would_flip_it_doesnt_depend_on_who_is_asked_first() -> None:
    strong = keeper(name="Strong", p_start=0.97, average_rating=6.6)
    weak = keeper(name="Weak", club="beta", p_start=0.97, average_rating=5.6)
    one, other = keepers.compare(strong, weak, CLASSIC), keepers.compare(weak, strong, CLASSIC)
    assert one.verdict.first == other.verdict.first == "Strong"
    assert one.model_dump(exclude={"values", "verdict"}) == other.model_dump(exclude={"values", "verdict"})


def test_a_keeper_without_rated_games_is_an_average_one() -> None:
    average = keepers.skill(keeper(rated_appearances=0, average_rating=None))
    assert keepers.skill(keeper(rated_appearances=0, average_rating=8.0)) == average
    assert keepers.skill(keeper(rated_appearances=8, average_rating=None)) == average
