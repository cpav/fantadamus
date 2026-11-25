"""AT-4 (mvp-cameos R2.3, R2.4): each share is checked on its own: fitted without each round or half,
scored on the held-out players of its kind only, and decided against its own minimum of 200."""

from __future__ import annotations

import pytest

from fantadamus.domains.calibration import SetRow
from fantadamus.domains.recalibration import Check, check_cameos
from tests.cameos_rows import FLAT_RATING, PRICED_RATING, brier, flat, priced, row

pytestmark = pytest.mark.usefixtures("start_values")  # worked out by hand on a share of 0.5

FLAT_AFTER = 0.2 + 0.4 * 0.2 / 0.5
"""A flat cameo's chance once the share is 0.2, fitted on one in five: 0.36."""
PRICED_AFTER = 0.2 + (PRICED_RATING - 0.2) * (0.25 / 0.64) / 0.5
"""A priced one's once its share is 0.25 / 0.64, fitted on one in four rated: 0.4."""


def _round(round: int, flats: int, priceds: int) -> list[SetRow]:
    return [
        *(flat(round, index % 4, index, rated=index % 5 == 0) for index in range(flats)),
        *(priced(round, index % 4, 5000 + index, rated=(index // 4) % 4 == 0) for index in range(priceds)),
    ]


def _named(checks: list[Check]) -> dict[str, Check]:
    return {check.name: check for check in checks}


def test_at4_held_out_by_round_and_half() -> None:
    by_round = _named(check_cameos({10: _round(10, 240, 240), 11: _round(11, 240, 240)}))
    assert list(by_round) == ["CAMEO_SHARE", "CAMEO_SHARE_PRICED"]
    for check, before, after, rated in (
        (by_round["CAMEO_SHARE"], FLAT_RATING, FLAT_AFTER, 48),
        (by_round["CAMEO_SHARE_PRICED"], PRICED_RATING, PRICED_AFTER, 60),
    ):
        assert [fold.held_out for fold in check.folds] == ["round 10", "round 11"]
        for fold in check.folds:  # each check scores its own kind only: 240 players a round
            assert fold.before.count == 240
            assert fold.before.brier == pytest.approx(brier(before, rated, 240) / 240)
            assert fold.after.brier == pytest.approx(brier(after, rated, 240) / 240)
        assert (check.count, check.minimum, check.proposed) == (480, 200, True)
    assert pytest.approx(0.4) == PRICED_AFTER

    by_half = _named(check_cameos({11: _round(11, 240, 240)}))
    for check in by_half.values():
        assert [fold.held_out for fold in check.folds] == [
            "half 1 of round 11's matches",
            "half 2 of round 11's matches",
        ]
        assert check.proposed


def test_at4_below_its_minimum() -> None:
    checks = _named(check_cameos({11: _round(11, 240, 120)}))
    assert checks["CAMEO_SHARE"].proposed
    few = checks["CAMEO_SHARE_PRICED"]
    assert (few.count, few.proposed) == (120, False)
    assert few.why == "below its minimum sample: 120 of 200"
    assert len(few.folds) == 2  # still shown


def test_at4_rounds_made_with_another_share() -> None:
    """Once a share is approved, the stored rounds were scored with the one before it. Today's chance, 0.2 +
    0.5 x 0.8, is worked out for each player from his own chance of starting, so a round stored with a share
    of 0.25, which gave 0.4, is checked against 0.6 like the round stored with 0.5."""
    old = [row(10, index % 4, index, rated=index % 5 == 0, p_rating=0.2 + 0.25 * 0.8) for index in range(240)]
    new = [flat(11, index % 4, 1000 + index, rated=index % 5 == 0) for index in range(240)]
    check = _named(check_cameos({10: old, 11: new}))["CAMEO_SHARE"]
    assert [fold.held_out for fold in check.folds] == ["round 10", "round 11"]
    for fold in check.folds:
        assert fold.before.brier == pytest.approx(brier(FLAT_RATING, 48, 240) / 240)
        assert fold.after.brier == pytest.approx(brier(FLAT_AFTER, 48, 240) / 240)


def test_at4_a_part_with_nothing_to_score_is_skipped() -> None:
    """Round 9 has forwards only, so nothing of the flat kind to score and nothing to fit it on without the
    others: it isn't a check of the flat share, and the rounds after it still are."""
    forwards = [priced(9, 0, 2000 + index, rated=index % 4 == 0) for index in range(40)]
    sets = {9: forwards, 10: _round(10, 240, 0), 11: _round(11, 240, 0)}
    checks = _named(check_cameos(sets))
    assert [fold.held_out for fold in checks["CAMEO_SHARE"].folds] == ["round 10", "round 11"]
    assert checks["CAMEO_SHARE_PRICED"].folds == []


def test_at4_only_the_players_it_counts() -> None:
    """A forward whose chance of scoring once on isn't known doesn't count, and neither does a defender."""
    unknown = [row(11, index % 4, 3000 + index, role="A", priced=True, rated=True) for index in range(30)]
    checks = _named(check_cameos({11: [*_round(11, 240, 120), *unknown]}))
    assert (checks["CAMEO_SHARE"].count, checks["CAMEO_SHARE_PRICED"].count) == (240, 120)
