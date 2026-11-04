"""mvp-roles task 4.4: two keepers of the same club cover each other exactly (design C8; method §A6; R3.6)."""

from __future__ import annotations

import pytest

from fantadamus.engine import keepers
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
