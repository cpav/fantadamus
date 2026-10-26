"""Task 3.2: each outlet's view and their consensus (design C5; R3.2 to R3.4, R4.2)."""

from __future__ import annotations

import datetime as dt

import pytest

from fantadamus.domains.availability.consensus import OfficialView, Status, combine, outlet_view
from fantadamus.domains.facts import Source

SOURCE = Source(
    source_url="https://example.org/a",
    captured_at=dt.datetime(2026, 10, 31, tzinfo=dt.UTC),
    content_sha256="0" * 64,
)


@pytest.mark.parametrize(
    ("status", "share", "p_start"),
    [
        ("starter", None, 0.90),
        ("ballottaggio", 60.0, 0.60),
        ("bench", None, 0.05),
        ("unavailable", None, 0.0),
    ],
)
def test_outlet_views(status: Status, share: float | None, p_start: float) -> None:
    view = outlet_view("Uno", status, share, SOURCE)
    assert view.p_start == p_start
    alone = combine([view])
    assert (alone.p_start, alone.spread, alone.disputed) == (p_start, 0.0, False)


def test_unmentioned_player_counts_bench() -> None:
    assert outlet_view("Uno", "not listed", None, SOURCE).p_start == 0.05
    mixed = combine(
        [outlet_view("Uno", "starter", None, SOURCE), outlet_view("Due", "not listed", None, SOURCE)]
    )
    assert mixed.p_start == pytest.approx(0.475)
    assert mixed.p_cameo == pytest.approx(0.2625)
    assert mixed.disputed


def test_unavailable_has_no_cameo() -> None:
    out = combine(
        [outlet_view("Uno", "bench", None, SOURCE), outlet_view("Due", "unavailable", None, SOURCE)]
    )
    assert out.p_start == pytest.approx(0.025)
    assert out.p_cameo == 0.0
    official = combine([], OfficialView(status="not listed", source=SOURCE))
    assert (official.p_start, official.p_cameo) == (0.0, 0.0)
    starter = combine([], OfficialView(status="starter", source=SOURCE))
    assert (starter.p_start, starter.p_cameo) == (1.0, 0.0)
