"""Recalibrating the method's starting values from scored rounds (mvp-recalibrate design C4 to C8).

Pure. It picks the evidence from the calibration sets and the season's own figures, counts and fits it with
`engine/recalibrate.py`, checks each fitted value where it wasn't fitted, and says what waits. Nothing here
changes a number: the owner approves a proposal first."""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Iterable, Mapping, Sequence

from pydantic import BaseModel

from fantadamus.contracts.types import UtcDatetime
from fantadamus.domains.calibration import RATING, STARTING, Pair, Scored, SetRow, scored_chance
from fantadamus.domains.season.silver import PlayerSeasonRow, TeamSeasonRow
from fantadamus.engine.constants import (
    CAMEO_RATED,
    CAMEO_SHARE,
    MINIMUM_SAMPLE,
    PENALTY_CONVERSION,
    PENALTY_RATE,
    PENALTY_SAVED_SHARE,
    RED_RATE,
    START_MAP,
    YELLOW_PRIOR,
)
from fantadamus.engine.recalibrate import (
    IDENTITY,
    Rate,
    StartMap,
    cameo_rated,
    cameo_share,
    counted,
    fit_start_map,
    mapped,
)


class Fitted(BaseModel):
    """Rates counted from the evidence, and each one that couldn't be, with why (mvp-recalibrate C4, C5)."""

    rates: list[Rate]
    missing: list[str]


def _benched(rows: Iterable[SetRow]) -> list[SetRow]:
    """Players who didn't start, whose rating is known, and to whom the model gave a chance of coming on."""
    return [
        row
        for row in rows
        if row.outcome.started is False
        and isinstance(row.outcome.rated, bool)
        and row.p_rating is not None
        and row.p_rating > row.p_start
    ]


def cameo_rates(rows: Sequence[SetRow]) -> Fitted:
    """`CAMEO_SHARE` from the defenders and midfielders whose cameo is flat, then `CAMEO_RATED` with it from
    those whose cameo is priced: forwards and attacking midfielders (C4)."""
    benched = _benched(rows)
    share = cameo_share(
        [row.outcome.rated is True for row in benched if row.priced_cameo is False and row.role in ("D", "C")]
    )
    if share is None:
        return Fitted(
            rates=[],
            missing=[
                "CAMEO_SHARE: no defender or midfielder who didn't start and could have come on",
                "CAMEO_RATED: needs CAMEO_SHARE",
            ],
        )
    attackers = [
        (row.p_scores_cameo, row.outcome.rated is True)
        for row in benched
        if row.priced_cameo is True and row.p_scores_cameo is not None
    ]
    rated = cameo_rated(attackers, share.value)
    if rated is None:
        reason = (
            "no attacker who didn't start and could have come on"
            if not attackers
            else "the evidence can't tell"
        )
        return Fitted(rates=[share], missing=[f"CAMEO_RATED: {reason}"])
    return Fitted(rates=[share, rated], missing=[])


def season_rates(players: Sequence[PlayerSeasonRow], teams: Sequence[TeamSeasonRow]) -> Fitted:
    """The rates the season counts itself, league-wide, from one statistics read and the table (C5): penalties
    per team match, how many are scored, how many of the missed ones were saved, yellow cards per outfield
    appearance, and red cards per rated game by role."""
    rates: list[Rate] = []
    missing: list[str] = []
    taken = sum(row.penalties_taken for row in players)
    scored = sum(row.penalties_scored for row in players)
    matches = sum(row.played for row in teams)
    if matches:
        rates.append(counted("PENALTY_RATE", taken, matches))
    else:
        missing.append("PENALTY_RATE: no team matches in the table")
    if taken:
        rates.append(counted("PENALTY_CONVERSION", scored, taken))
    else:
        missing.append("PENALTY_CONVERSION: no penalty taken")
    if any(row.penalties_saved is None for row in players):
        missing.append("PENALTY_SAVED_SHARE: the statistics read doesn't count saved penalties")
    elif taken > scored:
        saved = sum(row.penalties_saved or 0 for row in players)
        rates.append(counted("PENALTY_SAVED_SHARE", saved, taken - scored))
    else:
        missing.append("PENALTY_SAVED_SHARE: no penalty missed")
    outfield = [row for row in players if row.role != "P"]
    appearances = sum(row.appearances for row in outfield)
    if appearances:
        rates.append(counted("YELLOW_PRIOR", sum(row.yellow_cards for row in outfield), appearances))
    else:
        missing.append("YELLOW_PRIOR: no outfield appearance")
    if any(row.red_cards is None for row in players):
        missing.append("RED_RATE: the statistics read doesn't count red cards")
        return Fitted(rates=rates, missing=missing)
    for role in ("P", "D", "C", "A"):
        mine = [row for row in players if row.role == role]
        games = sum(row.rated_appearances for row in mine)
        name = f'RED_RATE["{role}"]'
        if games:
            rates.append(counted(name, sum(row.red_cards or 0 for row in mine), games))
        else:
            missing.append(f"{name}: no rated game")
    return Fitted(rates=rates, missing=missing)


class Fold(BaseModel):
    """One held-out check (C6): what was held out, and its chances scored before and after the change."""

    held_out: str
    before: Scored
    after: Scored


class Check(BaseModel):
    """A value checked before it's proposed (C6): its sample against its minimum and, where it's fitted, each
    held-out check. It's proposed only with enough evidence and only if it helps wherever it wasn't fitted."""

    name: str
    count: int
    minimum: int
    folds: list[Fold]
    proposed: bool
    why: str


def held_out(sets: Mapping[int, Sequence[SetRow]]) -> list[tuple[str, list[SetRow], list[SetRow]]]:
    """What's held out, what's fitted on and what's scored: each round in turn or, with one round, each half
    of its matches, alternating in the set's order."""
    rounds = sorted(sets)
    if len(rounds) > 1:
        return [
            (
                f"round {round}",
                [row for other in rounds if other != round for row in sets[other]],
                [*sets[round]],
            )
            for round in rounds
        ]
    rows = [row for round in rounds for row in sets[round]]
    if not rows:
        return []
    matches = sorted({(row.home, row.away) for row in rows})
    splits = []
    for half in (1, 2):
        out = set(matches[half - 1 :: 2])
        splits.append(
            (
                f"half {half} of round {rounds[0]}'s matches",
                [row for row in rows if (row.home, row.away) not in out],
                [row for row in rows if (row.home, row.away) in out],
            )
        )
    return splits


def _decided(name: str, count: int, minimum: int, folds: list[Fold]) -> Check:
    missed = [fold.held_out for fold in folds if not fold.after.brier < fold.before.brier]
    if count < minimum:
        proposed, why = False, f"below its minimum sample: {count} of {minimum}"
    elif not folds:
        proposed, why = False, "nothing to check it on where it wasn't fitted"
    elif missed:
        proposed, why = False, "it doesn't improve where it wasn't fitted: " + ", ".join(missed)
    else:
        proposed, why = True, "it improves the Brier score wherever it wasn't fitted"
    return Check(name=name, count=count, minimum=minimum, folds=folds, proposed=proposed, why=why)


def start_pairs(rows: Iterable[SetRow]) -> list[Pair]:
    """Each player's consensus and whether he started, where that's known: what the starting map fits on."""
    return [(row.consensus, row.outcome.started) for row in rows if isinstance(row.outcome.started, bool)]


def check_start_map(
    sets: Mapping[int, Sequence[SetRow]], *, minimum: int = MINIMUM_SAMPLE["starting"]
) -> Check:
    """The starting map (C2), fitted without each round or half and scored on it against today's map."""
    folds = []
    for label, fitted_on, scored_on in held_out(sets):
        test = start_pairs(scored_on)
        if not test:
            continue
        knots = fit_start_map(start_pairs(fitted_on))
        folds.append(
            Fold(
                held_out=label,
                before=scored_chance(STARTING, [(mapped(raw, START_MAP), started) for raw, started in test]),
                after=scored_chance(STARTING, [(mapped(raw, knots), started) for raw, started in test]),
            )
        )
    count = len(start_pairs(row for rows in sets.values() for row in rows))
    return _decided("START_MAP", count, minimum, folds)


def rerated(row: SetRow, rating: float, share: float, rated: float) -> float:
    """His chance of a rating with these cameo rates instead of today's: his cameo's part of it scales with
    the share and, if his cameo is priced, with how often one without a goal gets a rating."""
    factor = share / CAMEO_SHARE
    if row.priced_cameo is True and row.p_scores_cameo is not None:
        goal = row.p_scores_cameo
        factor *= (goal + (1 - goal) * rated) / (goal + (1 - goal) * CAMEO_RATED)
    return min(max(rating + (rating - row.p_start) * (factor - 1), 0.0), 1.0)


def check_cameos(sets: Mapping[int, Sequence[SetRow]], *, minimum: int = MINIMUM_SAMPLE["cameos"]) -> Check:
    """The cameo rates (C4), fitted without each round or half, and every known chance of a rating there
    scored with them against today's."""
    folds = []
    for label, fitted_on, scored_on in held_out(sets):
        fitted = {rate.name: rate.value for rate in cameo_rates(fitted_on).rates}
        test = [
            (row, row.p_rating, row.outcome.rated)
            for row in scored_on
            if row.p_rating is not None and isinstance(row.outcome.rated, bool)
        ]
        if "CAMEO_SHARE" not in fitted or not test:
            continue
        share, rated = fitted["CAMEO_SHARE"], fitted.get("CAMEO_RATED", CAMEO_RATED)
        folds.append(
            Fold(
                held_out=label,
                before=scored_chance(RATING, [(rating, happened) for _, rating, happened in test]),
                after=scored_chance(
                    RATING, [(rerated(row, rating, share, rated), happened) for row, rating, happened in test]
                ),
            )
        )
    count = len(_benched(row for rows in sets.values() for row in rows))
    return _decided("CAMEO_SHARE and CAMEO_RATED", count, minimum, folds)


def season_checks(fitted: Fitted) -> list[Check]:
    """The season's rates (C5) are counts, not forecasts: no held-out check, only their minimum sample."""
    checks = []
    for rate in fitted.rates:
        minimum = MINIMUM_SAMPLE["penalties" if rate.name.startswith("PENALTY") else "cards"]
        enough = rate.count >= minimum
        why = (
            "counted, not forecast: no held-out check"
            if enough
            else f"below its minimum sample: {rate.count} of {minimum}"
        )
        checks.append(
            Check(name=rate.name, count=rate.count, minimum=minimum, folds=[], proposed=enough, why=why)
        )
    return checks


class Wait(BaseModel):
    """Starting values this slice doesn't fit, and the evidence they need (R5.1)."""

    names: list[str]
    needs: str
    have: int | None = None
    """How much of it the calibration sets hold; None when no source gives it yet."""
    minimum: int | None = None


def _scoring(row: SetRow) -> bool:
    return row.outcome.started is True and isinstance(row.outcome.scored, bool) and row.p_scores is not None


def _clean_sheet(row: SetRow) -> bool:
    return (
        row.outcome.started is True
        and isinstance(row.outcome.clean_sheet, bool)
        and row.p_clean_sheet is not None
    )


def waiting(rows: Sequence[SetRow]) -> list[Wait]:
    """Every starting value of the method this slice doesn't fit, with what it needs and how much there is."""
    return [
        Wait(
            names=[
                "ROLE_PRIORS",
                "SHARE_WEIGHT",
                "DEFENDER_SHARE_WEIGHT",
                "MINUTES_CAMEO",
                "DECISIVE_GOAL_SHARE",
                "SET_PIECE_ASSIST_SHARE",
            ],
            needs="started outfield players whose goals are known",
            have=sum(_scoring(row) for row in rows),
            minimum=MINIMUM_SAMPLE["scoring"],
        ),
        Wait(
            names=["KEEPER_SKILL_WEIGHT", "DIXON_COLES_RHO", "TEAM_FORM_WEIGHT", "LEAGUE_GOALS_PER_MATCH"],
            needs="started keepers whose clean sheet is known",
            have=sum(_clean_sheet(row) for row in rows),
            minimum=MINIMUM_SAMPLE["clean_sheets"],
        ),
        Wait(
            names=[
                "VOTE_BASELINE",
                "VOTE_WEIGHT",
                "FIXTURE_EFFECT",
                "KEEPER_BETA",
                "VOTE_NOISE",
                "KEEPER_VOTE_NOISE",
                "GOAL_VOTE_LIFT",
                "CAMEO_GOAL_VOTE",
                "CAMEO_RATING",
                "CAMEO_FLAT",
                "YELLOW_WEIGHT",
            ],
            needs="each player's rating and cards in each match, which come with the new sources",
        ),
        Wait(
            names=["P_START_STARTER", "P_START_BENCH"],
            needs="each outlet's own views against who started, which the sets don't keep yet",
        ),
        Wait(names=["OWN_GOAL_RATE"], needs="own goals, which the statistics page doesn't count"),
        Wait(
            names=["START_MAP_WEIGHT", "MINIMUM_SAMPLE"],
            needs="how this slice's proposals hold up on the rounds after them",
        ),
    ]


Value = float | StartMap
"""A constant's value: a rate, or the starting map's knots."""
_TODAY: dict[str, float] = {
    "CAMEO_SHARE": CAMEO_SHARE,
    "CAMEO_RATED": CAMEO_RATED,
    "PENALTY_RATE": PENALTY_RATE,
    "PENALTY_CONVERSION": PENALTY_CONVERSION,
    "PENALTY_SAVED_SHARE": PENALTY_SAVED_SHARE,
    "YELLOW_PRIOR": YELLOW_PRIOR,
    **{f'RED_RATE["{role}"]': rate for role, rate in RED_RATE.items()},
}
_EVIDENCE = {
    "START_MAP": "players whose start is known",
    "CAMEO_SHARE and CAMEO_RATED": "players who didn't start and could have come on",
    "PENALTY_RATE": "team matches",
    "PENALTY_CONVERSION": "penalties taken",
    "PENALTY_SAVED_SHARE": "penalties missed",
    "YELLOW_PRIOR": "outfield appearances",
}
"""What each check counts; a red-card rate counts rated games."""


class Proposed(BaseModel):
    """One value (C8): today's, the fitted one, its count and interval if it's a rate, and its check."""

    name: str
    old: Value
    new: Value
    rate: Rate | None = None
    check: Check


class Proposal(BaseModel):
    """What `fantadamus recalibrate` proposes (C8). It changes nothing: the owner approves each value."""

    made_at: UtcDatetime
    rounds: list[int]
    missing_rounds: list[int]
    """Rounds asked for without a calibration set stored: fitted on the rest."""
    read_at: UtcDatetime | None
    """The statistics read the season's rates were counted from."""
    fitted: list[Proposed]
    season: list[Proposed]
    not_counted: list[str]
    waits: list[Wait]


def propose(
    sets: Mapping[int, Sequence[SetRow]],
    players: Sequence[PlayerSeasonRow],
    teams: Sequence[TeamSeasonRow],
    *,
    made_at: dt.datetime,
    missing: Iterable[int] = (),
) -> Proposal:
    """The proposal from the stored sets, one statistics read and the table."""
    rows = [row for round in sorted(sets) for row in sets[round]]
    cameos, cameo_check = cameo_rates(rows), check_cameos(sets)
    season = season_rates(players, teams)
    checks = {check.name: check for check in season_checks(season)}
    start = Proposed(
        name="START_MAP", old=START_MAP, new=fit_start_map(start_pairs(rows)), check=check_start_map(sets)
    )
    return Proposal(
        made_at=made_at,
        rounds=sorted(sets),
        missing_rounds=sorted(missing),
        read_at=max((row.captured_at for row in players), default=None),
        fitted=[
            start,
            *(
                Proposed(name=rate.name, old=_TODAY[rate.name], new=rate.value, rate=rate, check=cameo_check)
                for rate in cameos.rates
            ),
        ],
        season=[
            Proposed(
                name=rate.name, old=_TODAY[rate.name], new=rate.value, rate=rate, check=checks[rate.name]
            )
            for rate in season.rates
        ],
        not_counted=[*cameos.missing, *season.missing],
        waits=waiting(rows),
    )


def reliability_gap(scored: Scored) -> float:
    """How far each bucket's mean chance is from how often it happened, weighted by its players."""
    return (
        math.fsum(bucket.count * abs(bucket.said - bucket.happened) for bucket in scored.buckets)
        / scored.count
    )


def _rounds(rounds: Sequence[int]) -> str:
    if len(rounds) == 1:
        return f"round {rounds[0]}"
    return "rounds " + ", ".join(str(round) for round in rounds[:-1]) + f" and {rounds[-1]}"


def _knots(knots: Value) -> str:
    if isinstance(knots, float):
        return f"{knots:.3f}"
    if knots == IDENTITY:
        return "the identity"
    return ", ".join(f"{raw:.0%} to {value:.1%}" for raw, value in knots[1:-1])


def _value_lines(value: Proposed) -> list[str]:
    check = value.check
    lines = [f"{value.name}: {'proposed' if check.proposed else 'not proposed'}: {check.why}"]
    if value.rate is None:
        lines += [f"  today: {_knots(value.old)}", f"  fitted: {_knots(value.new)}"]
    else:
        rate = value.rate
        lines.append(
            f"  today: {_knots(value.old)}; fitted: {rate.value:.3f}, "
            f"90% between {rate.low:.3f} and {rate.high:.3f}"
        )
    unit = _EVIDENCE.get(check.name, "rated games")
    lines.append(f"  evidence: {check.count} {unit} (its minimum: {check.minimum})")
    lines += [
        f"  held out {fold.held_out}: Brier {fold.before.brier:.3f} to {fold.after.brier:.3f}, "
        f"reliability gap {reliability_gap(fold.before):.3f} to {reliability_gap(fold.after):.3f}"
        for fold in check.folds
    ]
    return lines


def _wait_line(wait: Wait) -> str:
    line = f"  {', '.join(wait.names)}: {wait.needs}"
    if wait.minimum is not None:
        line += f": {wait.have} of the {wait.minimum} it needs"
    return line


def render_proposal(proposal: Proposal) -> str:
    """The proposal as `fantadamus recalibrate` prints it."""
    lines = [f"Recalibration proposal, {proposal.made_at:%Y-%m-%d %H:%M} UTC, on {_rounds(proposal.rounds)}"]
    lines += [
        f"Round {round} has no calibration set stored: fitted on the rest."
        for round in proposal.missing_rounds
    ]
    lines.append(
        "Nothing changes until the owner approves a value, as a pull request to engine/constants.py."
    )
    lines += [
        "",
        "Fitted on the rounds",
        *(line for value in proposal.fitted for line in _value_lines(value)),
    ]
    lines += ["", "The season's own rates: counts, not forecasts"]
    lines += [line for value in proposal.season for line in _value_lines(value)]
    if proposal.not_counted:
        lines += ["", "Not counted", *(f"  {entry}" for entry in proposal.not_counted)]
    lines += ["", "What waits", *(_wait_line(wait) for wait in proposal.waits)]
    return "\n".join(lines)
