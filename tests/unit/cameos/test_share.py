"""mvp-cameos task 1 (R1.1, R1.3): each kind of cameo has its share, and the chance of a cameo uses it."""

from __future__ import annotations

import pytest

from fantadamus.contracts.types import Role
from fantadamus.domains.availability.consensus import OfficialView, combine, outlet_view
from fantadamus.engine import constants
from fantadamus.engine.outfield import cameo_share
from tests.cards_data import OUTLETS, source


@pytest.mark.parametrize(
    ("role", "mantra", "priced"),
    [
        ("A", "Pc", True),
        ("A", "A", True),
        ("A", "W", True),
        ("C", "T", True),
        ("A", None, True),
        ("C", "C", False),
        ("C", "M", False),
        ("C", None, False),
        ("D", "Dc", False),
        ("D", None, False),
        ("P", "Por", False),  # a keeper has no cameo to price, whatever his Mantra role
        ("P", None, False),
    ],
)
def test_each_role_gets_its_kinds_share(
    monkeypatch: pytest.MonkeyPatch, role: Role, mantra: str | None, priced: bool
) -> None:
    monkeypatch.setattr(constants, "CAMEO_SHARE", 0.3)
    monkeypatch.setattr(constants, "CAMEO_SHARE_PRICED", 0.7)
    assert cameo_share(role, mantra) == (0.7 if priced else 0.3)


def test_both_shares_start_at_a_half() -> None:
    assert (constants.CAMEO_SHARE, constants.CAMEO_SHARE_PRICED) == (0.5, 0.5)


def test_combine_uses_the_share() -> None:
    views = [outlet_view(outlet, "percentage", 60, source()) for outlet in OUTLETS]
    today, shared = combine(views), combine(views, share=0.3)
    assert shared.p_start == today.p_start
    assert shared.p_cameo == pytest.approx(0.3 * (1 - today.p_start))
    assert today.p_cameo == pytest.approx(constants.CAMEO_SHARE * (1 - today.p_start))


def test_an_official_bench_gets_the_share() -> None:
    views = [outlet_view(outlet, "percentage", 60, source()) for outlet in OUTLETS]
    bench = combine(views, OfficialView(status="bench", source=source()), share=0.7)
    starter = combine(views, OfficialView(status="starter", source=source()), share=0.7)
    assert (bench.p_start, bench.p_cameo) == (0.0, 0.7)
    assert (starter.p_start, starter.p_cameo) == (1.0, 0.0)
