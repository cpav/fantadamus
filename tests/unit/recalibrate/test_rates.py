"""The rates' edges: no evidence, no rate (mvp-recalibrate design C4)."""

from __future__ import annotations

from fantadamus.engine.recalibrate import cameo_rated, cameo_share, counted


def test_no_evidence_no_rate() -> None:
    assert cameo_share([]) is None
    assert cameo_rated([], 0.5) is None
    assert cameo_rated([(0.1, True)], 0.0) is None  # a share of none says nothing about a cameo's rating
    assert cameo_rated([(1.0, True)], 0.5) is None  # every cameo scores: the rest can't be told
    assert cameo_rated([(0.1, True)] * 6 + [(0.1, False)] * 4, 0.2) is None  # rated more often than the share
    assert cameo_rated([(0.8, True)] + [(0.8, False)] * 9, 0.5) is None  # less often than their goals alone


def test_a_rate_with_nothing_or_everything() -> None:
    none, every = counted("A", 0, 10), counted("A", 10, 10)
    assert (none.value, none.low) == (0.0, 0.0)
    assert 0.0 < none.high < 0.3
    assert (every.value, every.high) == (1.0, 1.0)
    assert 0.7 < every.low < 1.0
    assert counted("A", 15, 10).value == 1.0  # more events than chances is counted as all of them
