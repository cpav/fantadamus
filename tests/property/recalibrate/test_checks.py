"""P3: a change whose held-out Brier score doesn't improve is never proposed, nor one below its minimum
sample (mvp-recalibrate design C6; R5.2, R6.2)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.calibration import Outcome, SetRow
from fantadamus.domains.recalibration import Check, check_cameos, check_start_map

_CHANCE = st.floats(min_value=0.0, max_value=1.0)


@st.composite
def _sets(draw: st.DrawFn) -> dict[int, list[SetRow]]:
    sets: dict[int, list[SetRow]] = {}
    for round in draw(st.lists(st.integers(min_value=1, max_value=38), unique=True, max_size=3)):
        rows = []
        for player_id in range(draw(st.integers(min_value=0, max_value=40))):
            role = draw(st.sampled_from(["D", "C", "A"]))
            p_start = draw(_CHANCE)
            goal = draw(st.floats(min_value=0.0, max_value=0.9))
            cameo = 0.5 * (1 - p_start) * ((goal + (1 - goal) * 0.6) if role == "A" else 1.0)
            match = draw(st.integers(min_value=0, max_value=3))
            rows.append(
                SetRow(
                    round=round,
                    home=f"club{match}",
                    away=f"other{match}",
                    club=f"club{match}",
                    player_id=player_id,
                    role=role,
                    consensus=draw(_CHANCE),
                    p_start=p_start,
                    p_rating=p_start + cameo,
                    p_scores=None,
                    p_scores_cameo=goal if role == "A" else None,
                    p_clean_sheet=None,
                    priced_cameo=role == "A",
                    outcome=Outcome(draw(st.booleans()), draw(st.booleans()), False, False),
                )
            )
        sets[round] = rows
    return sets


def _honest(check: Check) -> None:
    if check.proposed:
        assert check.count >= check.minimum
        assert check.folds
        assert all(fold.after.brier < fold.before.brier for fold in check.folds)


@given(sets=_sets(), minimum=st.integers(min_value=0, max_value=60))
def test_p3_never_proposed_without_help(sets: dict[int, list[SetRow]], minimum: int) -> None:
    _honest(check_start_map(sets, minimum=minimum))
    _honest(check_cameos(sets, minimum=minimum))
