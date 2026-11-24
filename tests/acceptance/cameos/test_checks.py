"""AT-4 (mvp-cameos R2.3, R2.4): each share is checked on its own: fitted without each round or half,
scored on the held-out players of its kind only, and decided against its own minimum of 200."""

from __future__ import annotations

import pytest

from fantadamus.domains.calibration import SetRow
from fantadamus.domains.recalibration import Check, check_cameos
from tests.cameos_rows import FLAT_RATING, PRICED_RATING, brier, flat, priced

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
