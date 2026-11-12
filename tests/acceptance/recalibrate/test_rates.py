"""AT-3 and AT-4: the cameo rates from invented outcomes, and the season's rates from an invented statistics
read, by hand, each with its sample and a 90% interval (mvp-recalibrate R3.1, R4.1; design C4, C5)."""

from __future__ import annotations

import math

import pytest

from fantadamus.contracts.types import Role
from fantadamus.domains.calibration import Outcome, SetRow, cameo_rates, season_rates
from fantadamus.domains.season.silver import PlayerSeasonRow
from fantadamus.engine.recalibrate import Rate
from tests.cards_data import source, table_row

Z = 1.6448536269514722
"""A 90% interval's: the normal distribution's 95th percentile."""
NO_SHEET = "no official lineup stored"


def _wilson(events: int, count: int) -> tuple[float, float]:
    """The Wilson score interval, written out."""
    share = events / count
    middle = (share + Z * Z / (2 * count)) / (1 + Z * Z / count)
    half = Z / (1 + Z * Z / count) * math.sqrt(share * (1 - share) / count + Z * Z / (4 * count * count))
    return middle - half, middle + half


def _check(rate: Rate, name: str, value: float, count: int, interval: tuple[float, float]) -> None:
    assert rate.name == name
    assert rate.value == pytest.approx(value)
    assert rate.count == count
    assert [rate.low, rate.high] == pytest.approx(list(interval))


def _row(
    player_id: int,
    role: Role,
    *,
    rated: bool | str,
    started: bool = False,
    p_start: float = 0.3,
    p_rating: float | None = 0.65,
    p_scores_cameo: float | None = None,
) -> SetRow:
    return SetRow(
        round=10,
        home="alfa",
        away="beta",
        club="alfa",
        player_id=player_id,
        role=role,
        consensus=p_start,
        p_start=p_start,
        p_rating=p_rating,
        p_scores=None,
        p_scores_cameo=p_scores_cameo,
        p_clean_sheet=None,
        outcome=Outcome(started=started, rated=rated, scored=False, clean_sheet=False),
    )


def test_at3_cameos_by_hand() -> None:
    """CAMEO_SHARE from the defenders and midfielders who didn't start and could have come on: how often they
    got a rating. CAMEO_RATED from the forwards, given that share: a forward's cameo is rated if he scores, or
    this often if not, so 9 of 60 at a share of 0.3 and a 10% chance of a goal is (0.15 / 0.3 - 0.1) / 0.9."""
    rows = [
        *(_row(index, "D" if index % 2 else "C", rated=index < 3) for index in range(10)),
        _row(20, "D", rated=True, started=True, p_start=0.9, p_rating=0.95),  # he started
        _row(21, "C", rated=False, p_start=0.0, p_rating=0.0),  # out: no chance of a cameo
        _row(22, "D", rated=NO_SHEET),  # what happened isn't known
        _row(23, "P", rated=True),  # a keeper's cameo isn't the model's
        *(_row(100 + index, "A", rated=index < 9, p_scores_cameo=0.1) for index in range(60)),
        _row(200, "A", rated=True),  # no cameo chance of scoring priced: nothing held before kickoff
    ]
    fitted = cameo_rates(rows)
    share, rated = fitted.rates
    _check(share, "CAMEO_SHARE", 0.3, 10, _wilson(3, 10))
    solved = [(chance / 0.3 - 0.1) / 0.9 for chance in (0.15, *_wilson(9, 60))]
    _check(rated, "CAMEO_RATED", 4 / 9, 60, (solved[1], solved[2]))
    assert fitted.missing == []


def test_at3_cameos_without_evidence() -> None:
    fitted = cameo_rates([_row(1, "A", rated=True, p_scores_cameo=0.1)])
    assert fitted.rates == []
    assert fitted.missing == [
        "CAMEO_SHARE: no defender or midfielder who didn't start and could have come on",
        "CAMEO_RATED: needs CAMEO_SHARE",
    ]
    benched = [_row(1, "D", rated=True), _row(2, "C", rated=False)]
    no_forward = cameo_rates(benched)
    assert [rate.name for rate in no_forward.rates] == ["CAMEO_SHARE"]
    assert no_forward.missing == ["CAMEO_RATED: no forward who didn't start and could have come on"]
    scorers = cameo_rates([*benched, _row(3, "A", rated=True, p_scores_cameo=1.0)])  # every cameo scores
    assert [rate.name for rate in scorers.rates] == ["CAMEO_SHARE"]
    assert scorers.missing == ["CAMEO_RATED: the evidence can't tell"]


def _player(
    player_id: int,
    role: Role,
    *,
    appearances: int = 10,
    rated: int = 10,
    yellow: int = 0,
    penalties: tuple[int, int] = (0, 0),
    saved: int | None = 0,
    red: int | None = 0,
) -> PlayerSeasonRow:
    return PlayerSeasonRow(
        **source("https://example.org/statistiche").model_dump(),
        player_id=player_id,
        name=f"Player {player_id}",
        club="alfa",
        role=role,
        mantra_role=None,
        appearances=appearances,
        rated_appearances=rated,
        average_rating=6.0,
        goals=0,
        assists=0,
        yellow_cards=yellow,
        penalties_scored=penalties[0],
        penalties_taken=penalties[1],
        penalties_saved=saved,
        red_cards=red,
    )


READ = [
    _player(1, "P", saved=1),
    _player(2, "P", red=1),
    _player(3, "D", rated=9, yellow=2, red=1),
    _player(4, "D", rated=9, yellow=1),
    _player(5, "D", rated=9),
    _player(6, "C", yellow=3),
    _player(7, "C", appearances=8, rated=8, yellow=2),
    _player(8, "A", rated=9, yellow=1, penalties=(4, 5)),
    _player(9, "A", yellow=1, penalties=(2, 3)),
]
TABLE = [table_row(club, 10, 12, 12) for club in ("alfa", "beta", "gamma", "delta")]


def test_at4_season_rates_by_hand() -> None:
    """Over 40 team matches, 8 penalties taken, 6 scored, and of the 2 missed 1 saved; 10 yellow cards in 68
    outfield appearances; red cards per rated game, by role."""
    fitted = season_rates(READ, TABLE)
    rates = {rate.name: rate for rate in fitted.rates}
    _check(rates["PENALTY_RATE"], "PENALTY_RATE", 0.2, 40, _wilson(8, 40))
    _check(rates["PENALTY_CONVERSION"], "PENALTY_CONVERSION", 0.75, 8, _wilson(6, 8))
    _check(rates["PENALTY_SAVED_SHARE"], "PENALTY_SAVED_SHARE", 0.5, 2, _wilson(1, 2))
    _check(rates["YELLOW_PRIOR"], "YELLOW_PRIOR", 10 / 68, 68, _wilson(10, 68))
    _check(rates['RED_RATE["P"]'], 'RED_RATE["P"]', 1 / 20, 20, _wilson(1, 20))
    _check(rates['RED_RATE["D"]'], 'RED_RATE["D"]', 1 / 27, 27, _wilson(1, 27))
    _check(rates['RED_RATE["C"]'], 'RED_RATE["C"]', 0.0, 18, _wilson(0, 18))
    _check(rates['RED_RATE["A"]'], 'RED_RATE["A"]', 0.0, 19, _wilson(0, 19))
    assert list(rates) == [
        "PENALTY_RATE",
        "PENALTY_CONVERSION",
        "PENALTY_SAVED_SHARE",
        "YELLOW_PRIOR",
        'RED_RATE["P"]',
        'RED_RATE["D"]',
        'RED_RATE["C"]',
        'RED_RATE["A"]',
    ]
    assert fitted.missing == []


def test_at4_a_read_without_the_newer_columns() -> None:
    """Rows stored before the saved penalties and red cards were read can't count them, and without the table
    nor can the penalties per match: each is named."""
    older = [row.model_copy(update={"penalties_saved": None, "red_cards": None}) for row in READ]
    fitted = season_rates(older, [])
    assert [rate.name for rate in fitted.rates] == ["PENALTY_CONVERSION", "YELLOW_PRIOR"]
    assert fitted.missing == [
        "PENALTY_RATE: no team matches in the table",
        "PENALTY_SAVED_SHARE: the statistics read doesn't count saved penalties",
        "RED_RATE: the statistics read doesn't count red cards",
    ]


def test_at4_a_read_with_little_in_it() -> None:
    """Keepers only, and nobody has taken a penalty: what has nothing to count over is named."""
    fitted = season_rates([_player(1, "P")], TABLE)
    assert [rate.name for rate in fitted.rates] == ["PENALTY_RATE", 'RED_RATE["P"]']
    assert fitted.rates[0].value == 0.0
    assert fitted.missing == [
        "PENALTY_CONVERSION: no penalty taken",
        "PENALTY_SAVED_SHARE: no penalty missed",
        "YELLOW_PRIOR: no outfield appearance",
        'RED_RATE["D"]: no rated game',
        'RED_RATE["C"]: no rated game',
        'RED_RATE["A"]: no rated game',
    ]
    scored = season_rates([_player(1, "P"), _player(2, "A", penalties=(2, 2))], TABLE)
    assert "PENALTY_SAVED_SHARE: no penalty missed" in scored.missing  # every one scored
