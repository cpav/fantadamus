"""The reliability gap, by hand (mvp-recalibrate design C8)."""

from __future__ import annotations

import pytest

from fantadamus.domains.calibration import Bucket, Scored
from fantadamus.domains.recalibration import reliability_gap


def test_the_reliability_gap_by_hand() -> None:
    """30 players said 15% and 5% started; 10 said 95% and 90% did: (30 x 0.10 + 10 x 0.05) / 40."""
    scored = Scored(
        chance="Starting",
        count=40,
        brier=0.1,
        baseline=0.2,
        buckets=[
            Bucket(low=0.1, high=0.2, count=30, said=0.15, happened=0.05),
            Bucket(low=0.9, high=1.0, count=10, said=0.95, happened=0.90),
        ],
    )
    assert reliability_gap(scored) == pytest.approx((30 * 0.10 + 10 * 0.05) / 40)
