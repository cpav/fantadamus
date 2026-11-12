"""AT-2: the starting map, by hand: monotone, shrunk where a bucket is thin, applied where a chance of
starting is formed; an official lineup still settles it (mvp-recalibrate R2.1, R2.2; design C2, C3)."""

from __future__ import annotations

import pytest

from fantadamus.domains.availability import consensus
from fantadamus.domains.availability.consensus import OfficialView, combine, outlet_view
from fantadamus.domains.cards import lineups
from fantadamus.engine.constants import CAMEO_SHARE, START_MAP, START_MAP_WEIGHT
from fantadamus.engine.recalibrate import IDENTITY, StartMap, fit_start_map, mapped
from tests.cards_data import KICKOFF, OUTLETS, listed, source

pytestmark = pytest.mark.usefixtures("start_values")  # worked out by hand on the starting values


def _players(raw: float, count: int, started: int) -> list[tuple[float, bool]]:
    return [(raw, index < started) for index in range(count)]


def _flat(knots: StartMap) -> list[float]:
    return [value for knot in knots for value in knot]


def test_at2_a_map_by_hand() -> None:
    """Each bucket's rate is shrunk toward its mean consensus with the weight of 20 players; buckets that then
    go down are pooled; straight lines join (0, 0), each bucket and (1, 1)."""
    assert START_MAP_WEIGHT == 20
    pairs = [
        *_players(0.15, 50, 5),  # 10% started: (5 + 20 x 0.15) / 70
        *_players(0.25, 20, 10),  # 50%: (10 + 20 x 0.25) / 40 = 0.375
        *_players(0.35, 60, 6),  # 10%: (6 + 7) / 80 = 0.1625, below the bucket before: pooled, by weight,
        # (40 x 0.375 + 80 x 0.1625) / 120 = 28 / 120 for both
        *_players(0.95, 100, 95),  # 95%: (95 + 19) / 120 = 0.95
    ]
    knots = fit_start_map(pairs)
    pooled = 28 / 120
    assert _flat(knots) == pytest.approx([0, 0, 0.15, 8 / 70, 0.25, pooled, 0.35, pooled, 0.95, 0.95, 1, 1])
    assert mapped(0.2, knots) == pytest.approx(8 / 70 + (pooled - 8 / 70) / 2)
    assert mapped(0.65, knots) == pytest.approx((pooled + 0.95) / 2)  # halfway from 35% to 95%
    assert mapped(0.0, knots) == 0.0
    assert mapped(1.0, knots) == 1.0


def test_at2_the_top_bucket() -> None:
    """A chance of 100% is in the top bucket with the 90s; a bucket all at 100% puts no knot past (1, 1)."""
    pairs = [
        *_players(0.85, 10, 8),  # (8 + 17) / 30
        *_players(0.95, 10, 10),  # with the 100s: 20 players at 97.5% on average, 19 started:
        *_players(1.0, 10, 9),  # (19 + 20 x 0.975) / 40 = 0.9625
    ]
    assert _flat(fit_start_map(pairs)) == pytest.approx([0, 0, 0.85, 25 / 30, 0.975, 0.9625, 1, 1])
    assert fit_start_map(_players(1.0, 10, 9)) == IDENTITY


def test_at2_a_thin_bucket_barely_moves() -> None:
    thin = fit_start_map(_players(0.45, 2, 0))  # two players at 45%, neither started: (0 + 9) / 22
    heavy = fit_start_map(_players(0.45, 200, 0))  # two hundred: (0 + 9) / 220
    assert _flat(thin) == pytest.approx([0, 0, 0.45, 9 / 22, 1, 1])
    assert _flat(heavy) == pytest.approx([0, 0, 0.45, 9 / 220, 1, 1])
    assert fit_start_map([]) == IDENTITY  # no evidence, no change
    assert START_MAP != IDENTITY  # approved on 2026-11-12: docs/calibration-log.md has it


def test_at2_applied_where_the_chance_is_formed(monkeypatch: pytest.MonkeyPatch) -> None:
    views = [outlet_view(outlet, "percentage", 60, source()) for outlet in OUTLETS]
    unmapped = combine(views)
    assert unmapped.raw_p_start == pytest.approx(0.6)
    assert unmapped.p_start == unmapped.raw_p_start

    monkeypatch.setattr(consensus, "START_MAP", ((0.0, 0.0), (0.6, 0.45), (1.0, 1.0)))
    present = combine(views)
    assert present.raw_p_start == pytest.approx(0.6)  # what the outlets said, for a later fit
    assert present.p_start == pytest.approx(0.45)
    assert present.p_cameo == pytest.approx(CAMEO_SHARE * 0.55)  # from the mapped chance
    assert present.spread == 0.0

    # A card names the outlets that disagree against the consensus on their own scale, not the mapped one.
    monkeypatch.setattr(consensus, "START_MAP", ((0.0, 0.0), (0.75, 0.95), (1.0, 1.0)))
    lone = listed("Alfa Due", "D", (90, 90, 90, 30))
    assert lone.present.raw_p_start == pytest.approx(0.75)
    assert lone.present.p_start == pytest.approx(0.95)  # above every outlet but none
    eleven = [
        listed("Alfa Uno", "P"),
        lone,
        *(listed(f"Alfa {word}", "D") for word in ("Tre", "Quattro", "Cinque")),
        *(listed(f"Alfa {word}", "C") for word in ("Sei", "Sette", "Otto")),
        *(listed(f"Alfa {word}", "A") for word in ("Nove", "Dieci", "Undici")),
    ]
    place = lineups("alfa", eleven, KICKOFF).disputed
    assert [(c.name, c.dissent) for p in place for c in p.contenders] == [("Alfa Due", ["Sky"])]


def test_at2_the_official_lineup_still_settles_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(consensus, "START_MAP", ((0.0, 0.0), (0.6, 0.45), (1.0, 1.0)))
    views = [outlet_view(outlet, "percentage", 60, source()) for outlet in OUTLETS]
    starter = combine(views, OfficialView(status="starter", source=source()))
    assert (starter.p_start, starter.raw_p_start, starter.p_cameo) == (1.0, 1.0, 0.0)
    bench = combine(views, OfficialView(status="bench", source=source()))
    assert (bench.p_start, bench.raw_p_start, bench.p_cameo) == (0.0, 0.0, CAMEO_SHARE)
