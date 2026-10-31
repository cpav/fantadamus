"""Task 4.2: the Poisson and Dixon-Coles model, its fit, and the regressed-form fallback (design C7; R5.2,
R5.3)."""

from __future__ import annotations

import datetime as dt
import math

import pytest

from fantadamus.domains.facts import Source
from fantadamus.domains.odds import gold
from fantadamus.domains.season.silver import TeamSeasonRow
from fantadamus.engine import odds


def brute_force(home: float, away: float, rho: float) -> dict[str, float]:
    """The model cell by cell, written out as the method states it."""

    def tau(x: int, y: int) -> float:
        return {
            (0, 0): 1 - home * away * rho,
            (0, 1): 1 + home * rho,
            (1, 0): 1 + away * rho,
            (1, 1): 1 - rho,
        }.get((x, y), 1.0)

    cells = {
        (x, y): tau(x, y)
        * math.exp(-home)
        * home**x
        / math.factorial(x)
        * math.exp(-away)
        * away**y
        / math.factorial(y)
        for x in range(30)
        for y in range(30)
    }
    return {
        "home": sum(p for (x, y), p in cells.items() if x > y),
        "draw": sum(p for (x, y), p in cells.items() if x == y),
        "away": sum(p for (x, y), p in cells.items() if x < y),
        "over": sum(p for (x, y), p in cells.items() if x + y > 2),
        "btts": sum(p for (x, y), p in cells.items() if x > 0 and y > 0),
    }


def test_known_market() -> None:
    market = odds.model(1.5, 1.0)
    expected = brute_force(1.5, 1.0, rho=-0.10)
    assert market.p_home == pytest.approx(expected["home"], abs=1e-6)
    assert market.p_draw == pytest.approx(expected["draw"], abs=1e-6)
    assert market.p_away == pytest.approx(expected["away"], abs=1e-6)
    assert market.p_over == pytest.approx(expected["over"], abs=1e-9)
    assert market.p_btts == pytest.approx(expected["btts"], abs=1e-9)
    assert odds.fit(market) == pytest.approx((1.5, 1.0), abs=0.002)
    assert odds.de_margin([2.10, 3.30, 3.60]) == pytest.approx([0.4505, 0.2867, 0.2628], abs=1e-4)


def test_dixon_coles_low_scores() -> None:
    independent, corrected = odds.model(1.2, 0.9, rho=0.0), odds.model(1.2, 0.9)
    assert corrected.p_draw > independent.p_draw  # rho < 0 adds 0-0 and 1-1 draws
    assert corrected.p_over == pytest.approx(independent.p_over)  # and moves no goals between totals
    assert corrected.p_draw - independent.p_draw == pytest.approx(0.2 * 1.2 * 0.9 * math.exp(-2.1))


def test_regressed_form_fallback() -> None:
    source = Source(
        source_url="https://example.org/t",
        captured_at=dt.datetime(2026, 10, 26, tzinfo=dt.UTC),
        content_sha256="0" * 64,
    )
    table = [
        TeamSeasonRow(**source.model_dump(), club="alfa", played=8, goals_for=14, goals_against=9),
        TeamSeasonRow(**source.model_dump(), club="beta", played=8, goals_for=10, goals_against=11),
        TeamSeasonRow(**source.model_dump(), club="gamma", played=8, goals_for=6, goals_against=10),
        TeamSeasonRow(**source.model_dump(), club="delta", played=8, goals_for=10, goals_against=10),
    ]  # 40 goals in 32 team-matches: a league average of 1.25
    xg = gold.team_xg([], table, home="alfa", away="beta", as_of=source.captured_at)
    assert xg is not None
    assert not xg.from_odds
    # Weight 8 / (8 + 12) = 0.4. Alfa's attack 0.4 x 1.75 + 0.6 x 1.25 = 1.45 meets Beta's defence 1.30:
    # 1.45 x 1.30 / 1.25 = 1.508. Beta's attack 1.25 meets Alfa's defence 1.20: 1.2.
    assert xg.home_xg == pytest.approx(1.508)
    assert xg.away_xg == pytest.approx(1.2)
    assert xg.sources == [source]
    assert gold.team_xg([], table[:1], home="alfa", away="beta", as_of=source.captured_at) is None
    goalless = [row.model_copy(update={"goals_for": 0, "goals_against": 0}) for row in table]
    assert gold.team_xg([], goalless, home="alfa", away="beta", as_of=source.captured_at) is None
