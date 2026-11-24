"""The rates' edges: no evidence, no rate (mvp-recalibrate design C4)."""

from __future__ import annotations

from fantadamus.engine.recalibrate import cameo_share, cameo_share_priced, counted


def test_no_evidence_no_rate() -> None:
    """The priced share took `CAMEO_RATED`'s place (mvp-cameos R1.4): no evidence, no share, and none where
    more of them got a rating than one who comes on is ever rated."""
    assert cameo_share([]) is None
    assert cameo_share_priced([]) is None
    assert cameo_share_priced([(0.1, True)] * 7 + [(0.1, False)] * 3) is None  # 0.7 rated, above 0.64
    every = cameo_share_priced([(1.0, True)])  # every cameo scores: rated whenever he comes on
    assert every is not None
    assert every.value == 1.0


def test_a_rate_with_nothing_or_everything() -> None:
    none, every = counted("A", 0, 10), counted("A", 10, 10)
    assert (none.value, none.low) == (0.0, 0.0)
    assert 0.0 < none.high < 0.3
    assert (every.value, every.high) == (1.0, 1.0)
    assert 0.7 < every.low < 1.0
    assert counted("A", 15, 10).value == 1.0  # more events than chances is counted as all of them
