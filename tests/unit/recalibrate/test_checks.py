"""The held-out folds (mvp-recalibrate design C6): which rows each one fits on and scores."""

from __future__ import annotations

from fantadamus.domains.calibration import Outcome, SetRow
from fantadamus.domains.recalibration import held_out


def _row(round: int, match: int, player_id: int) -> SetRow:
    return SetRow(
        round=round,
        home=f"club{match}",
        away=f"other{match}",
        club=f"club{match}",
        player_id=player_id,
        role="D",
        consensus=0.5,
        p_start=0.5,
        p_rating=None,
        p_scores=None,
        p_scores_cameo=None,
        p_clean_sheet=None,
        outcome=Outcome(True, True, False, False),
    )


def test_each_round_held_out_in_turn() -> None:
    ten, eleven = [_row(10, 0, 1)], [_row(11, 0, 2), _row(11, 1, 3)]
    assert held_out({11: eleven, 10: ten}) == [("round 10", eleven, ten), ("round 11", ten, eleven)]
    assert held_out({}) == []


def test_with_one_round_its_matches_alternate() -> None:
    rows = [_row(11, match, 10 * match + player) for match in (3, 1, 0, 2) for player in range(2)]
    (first, fitted_1, scored_1), (second, fitted_2, scored_2) = held_out({11: rows})
    assert (first, second) == ("half 1 of round 11's matches", "half 2 of round 11's matches")
    assert {row.home for row in scored_1} == {row.home for row in fitted_2} == {"club0", "club2"}
    assert {row.home for row in scored_2} == {row.home for row in fitted_1} == {"club1", "club3"}
    assert len(scored_1) == len(scored_2) == 4
