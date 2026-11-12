"""AT-5 and AT-6: a value is proposed only with enough evidence and only if it helps where it wasn't fitted;
everything else waits, with what it needs (mvp-recalibrate R5.1, R5.2, R6.1, R6.2; design C6)."""

from __future__ import annotations

import pytest

from fantadamus.contracts.types import Role
from fantadamus.domains.calibration import Outcome, SetRow
from fantadamus.domains.recalibration import (
    Fitted,
    check_cameos,
    check_start_map,
    rerated,
    season_checks,
    waiting,
)
from fantadamus.engine import constants
from fantadamus.engine.recalibrate import counted

STARTER = 0.25
SURE = 0.95
GOOD = 15 / 220
"""What the map makes of 25% fitted on 200 players of whom 10 started: (10 + 20 x 0.25) / 220."""


def _row(
    round: int,
    match: int,
    player_id: int,
    *,
    consensus: float = STARTER,
    started: bool | str = False,
    role: Role = "D",
    p_start: float = 0.2,
    p_rating: float | None = None,
    rated: bool | str = False,
    priced: bool = False,
    scored: bool | str = False,
    clean_sheet: bool | str = False,
    p_scores: float | None = None,
    p_clean_sheet: float | None = None,
    p_scores_cameo: float | None = None,
) -> SetRow:
    return SetRow(
        round=round,
        home=f"club{match}",
        away=f"other{match}",
        club=f"club{match}",
        player_id=player_id,
        role=role,
        consensus=consensus,
        p_start=p_start,
        p_rating=p_rating,
        p_scores=p_scores,
        p_scores_cameo=p_scores_cameo,
        p_clean_sheet=p_clean_sheet,
        priced_cameo=priced,
        outcome=Outcome(started=started, rated=rated, scored=scored, clean_sheet=clean_sheet),
    )


def _players(round: int, raw: float, count: int, started: int, *, first: int = 0) -> list[SetRow]:
    """`count` players at `raw`, the first `started` of them starting, over two matches."""
    return [
        _row(round, index % 2, first + index, consensus=raw, started=index < started)
        for index in range(count)
    ]


def _brier(chance: float, happened: int, of: int) -> float:
    return happened * (1 - chance) ** 2 + (of - happened) * chance**2


def test_at6_held_out_by_round() -> None:
    """Each round held out in turn: fitted on the other, the map takes 25% to 15 / 220 and leaves 95% where it
    is, and the held-out round's Brier score falls from 0.0675."""
    sets = {
        round: [*_players(round, STARTER, 200, 10), *_players(round, SURE, 200, 190, first=1000)]
        for round in (10, 11)
    }
    check = check_start_map(sets)
    assert check.name == "START_MAP"
    assert [fold.held_out for fold in check.folds] == ["round 10", "round 11"]
    for fold in check.folds:
        assert fold.before.count == fold.after.count == 400
        assert fold.before.brier == pytest.approx((_brier(STARTER, 10, 200) + _brier(SURE, 190, 200)) / 400)
        assert fold.after.brier == pytest.approx((_brier(GOOD, 10, 200) + _brier(SURE, 190, 200)) / 400)
        assert [bucket.said for bucket in fold.after.buckets] == pytest.approx([GOOD, SURE])
    assert (check.count, check.minimum) == (800, 300)
    assert check.proposed
    assert check.why == "it improves the Brier score wherever it wasn't fitted"


def _benched(match: int, player_id: int, *, rated: bool) -> SetRow:
    """A defender who didn't start, at 20% to start: 0.2 + 0.5 x 0.8 to get a rating."""
    return _row(11, match, player_id, p_start=0.2, p_rating=0.6, rated=rated)


def test_at6_held_out_by_matches() -> None:
    """With one round, half its matches are held out at a time, alternating. One in five benched defenders
    got a rating, so fitted on either half the share is 0.2, and the other half's chance of a rating falls
    from 0.6 to 0.2 + 0.2 x 0.8."""
    rows = [_benched(index % 4, index, rated=index % 5 == 0) for index in range(240)]
    rows += [  # neither is scored: no chance of a rating was given, or what happened isn't known
        _row(11, 0, 900, rated=True),
        _row(11, 1, 901, p_rating=0.6, rated="no statistics read after the round"),
    ]
    check = check_cameos({11: rows})
    assert check.name == "CAMEO_SHARE and CAMEO_RATED"
    assert [fold.held_out for fold in check.folds] == [
        "half 1 of round 11's matches",
        "half 2 of round 11's matches",
    ]
    for fold in check.folds:
        assert fold.before.count == 120
        assert fold.before.brier == pytest.approx(_brier(0.6, 24, 120) / 120)
        assert fold.after.brier == pytest.approx(_brier(0.36, 24, 120) / 120)
    assert (check.count, check.minimum) == (240, 200)
    assert check.proposed
    assert check_cameos({11: rows}, minimum=240).proposed  # exactly enough is enough


def test_at6_no_help_no_proposal() -> None:
    """Round 10's quarter-chances started 5% of the time, round 11's 45%: each fit misleads the other round.
    Cameos already as often as the model says change nothing, which isn't help either."""
    sets = {10: _players(10, STARTER, 200, 10), 11: _players(11, STARTER, 200, 90)}
    check = check_start_map(sets)
    assert not check.proposed
    assert check.why == "it doesn't improve where it wasn't fitted: round 10, round 11"
    assert all(fold.after.brier > fold.before.brier for fold in check.folds)

    even = [_benched(index % 4, index, rated=(index // 4) % 2 == 0) for index in range(240)]  # half
    cameos = check_cameos({11: even})
    assert [fold.after.brier for fold in cameos.folds] == [fold.before.brier for fold in cameos.folds]
    assert not cameos.proposed


def test_at5_below_its_minimum() -> None:
    small = check_start_map({10: _players(10, STARTER, 50, 2)})
    assert not small.proposed
    assert small.why == "below its minimum sample: 50 of 300"
    assert [fold.held_out for fold in small.folds] == [  # still shown
        "half 1 of round 10's matches",
        "half 2 of round 10's matches",
    ]
    few = check_cameos({11: [_benched(index % 4, index, rated=index % 5 == 0) for index in range(100)]})
    assert few.why == "below its minimum sample: 100 of 200"
    assert not few.proposed
    assert check_start_map({}).why == "below its minimum sample: 0 of 300"

    season = season_checks(
        Fitted(
            rates=[
                counted("PENALTY_SAVED_SHARE", 7, 8),
                counted("YELLOW_PRIOR", 300, 2000),
                counted('RED_RATE["P"]', 1, 220),
                counted("PENALTY_RATE", 33, 220),
                counted("PENALTY_CONVERSION", 24, 30),
            ],
            missing=[],
        )
    )
    assert [(check.name, check.proposed, check.why) for check in season] == [
        ("PENALTY_SAVED_SHARE", False, "below its minimum sample: 8 of 30"),
        ("YELLOW_PRIOR", True, "counted, not forecast: no held-out check"),
        ('RED_RATE["P"]', False, "below its minimum sample: 220 of 300"),
        ("PENALTY_RATE", True, "counted, not forecast: no held-out check"),
        ("PENALTY_CONVERSION", True, "counted, not forecast: no held-out check"),  # exactly enough
    ]
    assert all(check.folds == [] for check in season)
    sparse = season_checks(
        Fitted(rates=[counted("PENALTY_RATE", 22, 200)], missing=[])
    )  # 200 matches, 22 penalties
    assert [(check.count, check.proposed, check.why) for check in sparse] == [
        (22, False, "below its minimum sample: 22 of 30")
    ]


FITTED_HERE = {
    "START_MAP",
    "CAMEO_SHARE",
    "CAMEO_RATED",
    "PENALTY_RATE",
    "PENALTY_CONVERSION",
    "PENALTY_SAVED_SHARE",
    "YELLOW_PRIOR",
    "RED_RATE",
}
SETTINGS = {
    "CONTESTED_PERCENT",
    "DISPUTED_SPREAD",
    "ODDS_DISPUTED_SPREAD",
    "MAX_GOALS",
    "XG_RANGE",
    "USUAL_MANTRA_ROLE",
    "SIMULATIONS",
    "SIMULATION_SEED",
    "CAPTAIN_CANDIDATES",
    "THRESHOLDS_SHOWN",
    "DOUBTFUL_BELOW",
    "COIN_FLIP",
    "CLEAR",
    "FRESH_FOR_HOURS",
    "FRESH_NEAR_MATCH_HOURS",
    "NEAR_MATCH_HOURS",
    "USUAL_SHARE",
    "ROTATION_P_START",
    "SCORERS",
}
"""How the answers are worked out and shown, not estimates: nothing to calibrate."""


def test_at5_what_waits() -> None:
    """Every starting value this slice doesn't fit is listed with the evidence it needs and how much there
    is."""
    rows = [
        *(_row(10, 0, index, started=True, role="A", scored=index == 0, p_scores=0.3) for index in range(3)),
        _row(10, 0, 3, started=True, role="C", scored="no statistics read after the round", p_scores=0.1),
        _row(10, 0, 4, started=False, role="A", p_scores=0.3),  # scoring counts if he started
        _row(10, 0, 5, started=True, role="P", clean_sheet=True, p_clean_sheet=0.3),
        _row(10, 1, 6, started=True, role="P", clean_sheet=False),  # no chance of a clean sheet was given
    ]
    waits = {name: wait for wait in waiting(rows) for name in wait.names}
    scoring, clean, ratings = waits["SHARE_WEIGHT"], waits["KEEPER_SKILL_WEIGHT"], waits["VOTE_NOISE"]
    assert (scoring.have, scoring.minimum) == (3, 500)
    assert scoring.needs == "started outfield players whose goals are known"
    assert (clean.have, clean.minimum) == (1, 100)
    assert (ratings.have, ratings.minimum) == (None, None)
    assert {wait.names[0]: wait.needs for wait in waiting(rows)} == {
        "ROLE_PRIORS": "started outfield players whose goals are known",
        "KEEPER_SKILL_WEIGHT": "started keepers whose clean sheet is known",
        "VOTE_BASELINE": "each player's rating and cards in each match, which come with the new sources",
        "P_START_STARTER": "each outlet's own views against who started, which the sets don't keep yet",
        "OWN_GOAL_RATE": "own goals, which the statistics page doesn't count",
        "START_MAP_WEIGHT": "how this slice's proposals hold up on the rounds after them",
    }

    every = {name for name in vars(constants) if name.isupper()}
    assert not FITTED_HERE & set(waits)
    assert not SETTINGS & set(waits)
    assert every == FITTED_HERE | set(waits) | SETTINGS


def test_at6_a_chance_of_a_rating_rerated_by_hand() -> None:
    """What the held-out check scores: each chance of a rating with the fitted cameo rates instead of today's
    0.5 and 0.6. A forward at 20% to start, with a 10% chance of scoring as a cameo, had 0.2 + 0.5 x 0.8 x
    (0.1 + 0.9 x 0.6); at 0.25 and 0.3 he has 0.2 + 0.25 x 0.8 x (0.1 + 0.9 x 0.3)."""
    forward = _row(11, 0, 1, role="A", priced=True).model_copy(update={"p_scores_cameo": 0.1})
    assert rerated(forward, 0.2 + 0.4 * 0.64, 0.25, 0.3) == pytest.approx(0.2 + 0.2 * 0.37)
    defender = _row(11, 0, 2, p_scores_cameo=0.05)
    assert rerated(defender, 0.6, 0.25, 0.3) == pytest.approx(0.2 + 0.25 * 0.8)  # flat: the share only
    keeper = _row(11, 0, 3, role="P", p_start=0.9)
    assert rerated(keeper, 0.9, 0.25, 0.3) == 0.9  # no cameo, nothing to rescale
    assert rerated(defender, 0.9, 1.0, 0.3) == 1.0  # never past certain


def _attacker(match: int, player_id: int, *, rated: bool) -> SetRow:
    """A forward who didn't start, at 20% to start, with a 10% chance of scoring as a cameo: 0.2 + 0.5 x 0.8 x
    (0.1 + 0.9 x 0.6) to get a rating."""
    return _row(11, match, player_id, role="A", p_rating=0.456, rated=rated, priced=True, p_scores_cameo=0.1)


def test_at6_the_fitted_cameo_rating_is_what_is_checked() -> None:
    """Half the benched defenders and a quarter of the benched forwards got a rating: the share stays 0.5, and
    CAMEO_RATED is fitted at (0.25 / 0.5 - 0.1) / 0.9, which takes a forward's chance to 0.2 + 0.4 x 0.5."""
    rows = []
    for match in range(4):
        rows += [_benched(match, 1000 * match + index, rated=index % 2 == 0) for index in range(60)]
        rows += [_attacker(match, 1000 * match + 100 + index, rated=index % 4 == 0) for index in range(40)]
    check = check_cameos({11: rows})
    for fold in check.folds:
        assert fold.before.brier == pytest.approx((_brier(0.6, 60, 120) + _brier(0.456, 20, 80)) / 200)
        assert fold.after.brier == pytest.approx((_brier(0.6, 60, 120) + _brier(0.4, 20, 80)) / 200)
    assert check.proposed


def test_at6_a_part_with_nothing_to_score_is_skipped() -> None:
    """A part that can't be fitted or scored isn't a check, and the parts after it still are; with nothing
    to check at all, nothing is proposed."""
    unknown = [_row(10, 0, index, started="no official lineup stored") for index in range(10)]
    eleven = [
        *(_row(11, 0, 500 + index, started="no official lineup stored") for index in range(10)),
        *(_row(11, 1, index, started=index < 10) for index in range(200)),
    ]
    check = check_start_map(
        {10: unknown, 11: eleven}, minimum=0
    )  # round 10 knows no start: no fold of its own
    assert [fold.held_out for fold in check.folds] == [
        "half 2 of round 11's matches"
    ]  # half 1 knows none either

    defenders = [_benched(0, index, rated=index % 5 == 0) for index in range(40)]
    forwards = [_attacker(0, 100 + index, rated=index % 4 == 0) for index in range(40)]
    cameos = check_cameos({10: defenders, 11: forwards}, minimum=0)  # without round 10, no share to fit
    assert [fold.held_out for fold in cameos.folds] == ["round 11"]

    alone = check_cameos({11: defenders}, minimum=0)  # one match: half 1 holds all of it, fitted on nothing
    assert alone.folds == []
    assert alone.why == "nothing to check it on where it wasn't fitted"
    assert not alone.proposed


def test_at6_folds_where_the_evidence_is() -> None:
    """Only round 11 knows who got a rating: the cameo check splits its matches, as with one round, while the
    starting map, known in both rounds, holds out each round in turn."""
    cameos = [_benched(index % 4, 5000 + index, rated=index % 5 == 0) for index in range(240)]
    sets = {10: _players(10, STARTER, 200, 10), 11: [*_players(11, STARTER, 200, 10), *cameos]}
    assert [fold.held_out for fold in check_cameos(sets).folds] == [
        "half 1 of round 11's matches",
        "half 2 of round 11's matches",
    ]
    assert [fold.held_out for fold in check_start_map(sets).folds] == ["round 10", "round 11"]
