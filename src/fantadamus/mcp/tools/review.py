"""`review_round`: after a round, what the user fielded against the advice, each choice's expected cost and
what it really did, and whether overrides pay off over the season (mvp-review design C8; R1 to R5).

It reads only what a round leaves behind: the decision log, the statistics page before and after the round
(read once more if no read after it is stored), and the facts stored before the lock. What the user fielded
and every review stay in private storage.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from typing import Literal

from mcp.server.mcpserver import MCPServer
from pydantic import AwareDatetime, BaseModel

from fantadamus.contracts.xy.league import LineupRules
from fantadamus.domains.calibration import round_frame
from fantadamus.domains.facts import read_silver
from fantadamus.domains.fixtures.silver import FIXTURES
from fantadamus.domains.players.resolve import KnownPlayer
from fantadamus.domains.review import (
    Advice,
    Read,
    RealScore,
    Record,
    Reviewed,
    Round,
    Unknown,
    advice_for,
    last_advice,
    logged,
    player_round,
    real_score,
    record,
    review_choices,
)
from fantadamus.domains.season.silver import PlayerSeasonRow
from fantadamus.engine.constants import SIMULATIONS
from fantadamus.engine.lineup import Arrangement
from fantadamus.engine.simulate import SimPlayer, Simulated, plan, simulate
from fantadamus.lake.review_log import ReviewLog
from fantadamus.league.fielded import Choose, FieldedLineup, FieldedStore, Refused, as_advised, fielded_lineup
from fantadamus.league.rules import StoredRules
from fantadamus.league.squads import MINE, SquadStore, StoredSquad
from fantadamus.mcp.advisor import ROME, Advisor
from fantadamus.mcp.calibrate import Calibrator
from fantadamus.mcp.tools.lineup import SquadAt, replayed_lineup, squad_at

APP_GAP = 0.5
"""A user's own total from their league's app that differs by more than this is worth a word (R2.4)."""
_BEFORE_THE_LOCK = dt.timedelta(seconds=1)
_EVENTS = {
    "decisive_goal": "decisive goals",
    "set_piece_assist": "set-piece assists",
    "own_goal": "own goals",
    "red_card": "red cards",
    "penalty_saved": "saved penalties",
    "goal_conceded": "goals conceded",
    "clean_sheet": "clean sheets",
}


class ReviewChoice(BaseModel):
    kind: Literal["player", "formation", "bench", "captain"]
    fielded: list[str]
    """Who the user picked: the player, the players, the first substitute, or the captain and vice."""
    advised: list[str]
    """Whom that replaced; for the bench and the captain, the advice's for the eleven fielded."""
    expected_cost: float
    """Expected points given up at the lock: positive costs, negative gains."""
    real_gain: float | None
    """What it really gave this round."""
    judged: Literal["cost", "even", "gain"]
    """By the expected cost: the real result is one round's outcome."""
    mattered: bool | None = None
    """The bench only: whether a substitute really came on for that role."""
    unknown: list[str] = []
    """Whose round isn't known, so the real result isn't either."""


class RecordLine(BaseModel):
    rounds: int
    overrides: int
    expected_cost: float
    real_gain: float
    counted: int
    margin: float | None
    verdict: Literal["too early", "mostly luck", "paid off", "cost"]


class Review(BaseModel):
    round: int
    team: str
    replayed: bool
    """The advice was replayed at the lock, because none was asked for before it."""
    expected: float
    low: float
    high: float
    """Eight rounds out of ten were expected to fall from `low` to `high`."""
    real: float | None
    fantasy_goals: int | None
    position: Literal["below", "inside", "above"] | None
    app_total: float | None = None
    """The user's own total from their league's app."""
    app_differs: bool | None = None
    advice_expected: float
    advice_real: float | None
    total_cost: float
    total_gain: float | None
    choices: list[ReviewChoice]
    record: RecordLine
    not_counted: list[str]
    """What the reads couldn't count, by name: a player's round, or a kind of event."""


class ReviewResult(BaseModel):
    status: Literal["fielded", "choose", "refused", "not_ready", "review"]
    message: str
    unresolved: dict[str, list[KnownPlayer]] = {}
    review: Review | None = None


def review_for(
    advisor: Advisor,
    squads: SquadStore,
    fielded: FieldedStore,
    reviews: ReviewLog,
    calibrator: Calibrator,
    *,
    round: int,
    team: str = MINE,
    as_advised: bool = False,
    starters: Sequence[str] = (),
    bench: Sequence[str] = (),
    captain: str | None = None,
    vice: str | None = None,
    app_total: float | None = None,
    as_of: dt.datetime | None = None,
    rounds: int = SIMULATIONS,
) -> ReviewResult:
    """The review of one round for one team. Given what the user fielded, it's stored first; a replay of an
    earlier `as_of` stores and logs nothing."""
    now = (as_of or advisor.clock()).astimezone(dt.UTC)
    stored = advisor.rules.get(advisor.user)
    squad = squads.get(advisor.user, team)
    if stored is None or stored.rules.lineup is None or squad is None:
        return ReviewResult(status="refused", message=f"No league rules or squad stored for {team}.")
    rules = stored.rules.lineup
    frame = round_frame(read_silver(advisor.lake, FIXTURES), round, now)
    if frame is None:
        return ReviewResult(status="not_ready", message=f"No fixtures are stored for round {round}.")
    if now < frame.finished_at:
        when = frame.finished_at.astimezone(ROME)
        return ReviewResult(
            status="not_ready",
            message=f"Round {round} finishes about {when:%a %d %b %H:%M}: ask again after.",
        )
    lock = frame.first_kickoff
    decisions = advisor.log.read()
    told = last_advice(decisions, user=advisor.user, team=team, round=round, lock=lock)
    # At the lock, on the newest facts stored before it, and the advice's own players too, in case the squad
    # has changed since. A replayed advice is worked out from the same facts.
    also = [*told.starters, *told.bench] if told is not None else []
    at_lock = squad_at(advisor, stored, squad, lock - _BEFORE_THE_LOCK, also=also)
    if at_lock is None:
        return ReviewResult(
            status="refused", message=f"The facts stored before round {round}'s lock don't say enough."
        )
    advice = advice_for(
        decisions,
        user=advisor.user,
        team=team,
        round=round,
        lock=lock,
        replay=lambda: _replayed(advisor, stored, squad, at_lock, rounds),
    )
    if advice is None:
        return ReviewResult(
            status="refused", message=f"No advice for round {round} could be found or replayed."
        )
    lineup = _fielded(
        advisor, squad, rules, fielded, advice, round, starters, bench, captain, vice, as_advised, now
    )
    if not isinstance(lineup, FieldedLineup):
        return lineup
    if as_of is None and (as_advised or starters):
        fielded.set(advisor.user, lineup)
    names = {candidate.player_id: candidate.name for candidate in at_lock.candidates}
    missing = sorted({*lineup.starters, *lineup.bench} - names.keys())
    if missing:
        known = _names(squad)
        return ReviewResult(
            status="refused",
            message="These players weren't known before the lock, so their choices can't be priced: "
            + ", ".join(known.get(player, str(player)) for player in missing),
        )
    before, after = calibrator.bracketing_reads(frame, now, read=as_of is None)
    if after is None:
        return ReviewResult(
            status="not_ready",
            message=f"No statistics read after round {round} is stored yet: ask again later.",
        )
    played = _rounds(names, before, after)
    conceded = _conceded(names, before, after)
    reviewed = review_choices(
        advice.picked(),
        lineup.picked(),
        at_lock.candidates,
        rules,
        price=lambda arrangements: _price(
            at_lock.players, at_lock.matches, arrangements, rules, stored, rounds
        ),
        score=lambda arranged, wearing, covering: real_score(
            played, plan(arranged, rules), stored.rules, conceded=conceded, captain=wearing, vice=covering
        ),
        replayed=advice.replayed,
    )
    line = logged(
        reviewed,
        user=advisor.user,
        team=team,
        round=round,
        as_of=lock,
        logged_at=advisor.clock(),
        content_hashes=at_lock.content_hashes,
    )
    if as_of is None:
        reviews.append(line)
        kept = reviews.read()
    else:
        kept = [*reviews.read(), line]
    found = record(kept, user=advisor.user, team=team)
    return ReviewResult(
        status="review",
        message=_message(round, reviewed),
        review=_review(round, team, names, reviewed, found, played, app_total),
    )


def register(
    server: MCPServer,
    advisor: Advisor,
    squads: SquadStore,
    calibrator: Calibrator,
    reviews: ReviewLog,
    *,
    rounds: int = SIMULATIONS,
) -> None:
    """Add `review_round` to `server`."""
    fielded = FieldedStore(squads.root)

    @server.tool(
        description="After a round, review the user's lineup: what they fielded against the advice, each "
        "choice's expected cost at the lock and what it really did, and whether their overrides pay off "
        "over the season. Pass the round. The first time, pass what they fielded (starters, the bench in "
        "order, captain and vice, by name) or as_advised if they followed the advice; it's kept, so later "
        "calls need only the round. app_total is their real total from their league's app, to check against. "
        "It returns 'fielded' when it needs the lineup, 'choose' for a name that could be two players, "
        "'refused' with the reason, 'not_ready' with when to ask again, or the review."
    )
    def review_round(
        round: int,
        team: str = MINE,
        as_advised: bool = False,
        starters: list[str] | None = None,
        bench: list[str] | None = None,
        captain: str | None = None,
        vice: str | None = None,
        app_total: float | None = None,
        as_of: AwareDatetime | None = None,
    ) -> ReviewResult:
        return review_for(
            advisor,
            squads,
            fielded,
            reviews,
            calibrator,
            round=round,
            team=team,
            as_advised=as_advised,
            starters=starters or (),
            bench=bench or (),
            captain=captain,
            vice=vice,
            app_total=app_total,
            as_of=as_of,
            rounds=rounds,
        )


def _replayed(
    advisor: Advisor, stored: StoredRules, squad: StoredSquad, at_lock: SquadAt, rounds: int
) -> Advice | None:
    """The lineup Fantadamus would have advised at the lock, from the facts stored by then however old: by
    the lock the round's lineups and odds are usually past their freshness targets (R3.5)."""
    result = replayed_lineup(advisor, stored, squad, at_lock, rounds=rounds)
    if result.lineup is None:
        return None
    advised = result.lineup
    ids = {player.name: player.player_id for player in [*advised.starters, *advised.bench]}
    return Advice(
        formation=advised.formation,
        starters=[player.player_id for player in advised.starters],
        bench=[player.player_id for player in advised.bench],
        captain=ids.get(advised.captain) if advised.captain else None,
        vice=ids.get(advised.vice) if advised.vice else None,
        as_of=at_lock.when,
    )


def _fielded(
    advisor: Advisor,
    squad: StoredSquad,
    rules: LineupRules,
    store: FieldedStore,
    advice: Advice,
    round: int,
    starters: Sequence[str],
    bench: Sequence[str],
    captain: str | None,
    vice: str | None,
    followed: bool,
    now: dt.datetime,
) -> FieldedLineup | ReviewResult:
    """What the user fielded: as they say now, as advised, or as stored before."""
    if followed:
        return as_advised(advice, round=round, team=squad.team, at=now)
    if starters:
        found = fielded_lineup(
            squad, rules, round=round, starters=starters, bench=bench, captain=captain, vice=vice, at=now
        )
        if isinstance(found, Refused):
            return ReviewResult(status="refused", message=found.reason)
        if isinstance(found, Choose):
            return ReviewResult(
                status="choose",
                message="A name matches more than one player of this squad: ask which.",
                unresolved=found.unresolved,
            )
        return found
    kept = store.get(advisor.user, squad.team, round)
    if kept is None:
        return ReviewResult(
            status="fielded",
            message=f"Ask what they fielded in round {round}: the eleven, the bench in order, and the "
            "captain and vice if the league has one, then call review_round with them; or, if they "
            "followed the advice, with as_advised.",
        )
    return kept


def _price(
    players: Sequence[SimPlayer],
    matches: Sequence[tuple[float, float]],
    arrangements: Sequence[Arrangement],
    rules: LineupRules,
    stored: StoredRules,
    rounds: int,
) -> list[Simulated]:
    return simulate(
        players, matches, arrangements, rules, formula_rules=stored.rules.formula_rules, rounds=rounds
    )


def _rounds(
    players: Iterable[int],
    before: Mapping[int, PlayerSeasonRow] | None,
    after: Mapping[int, PlayerSeasonRow],
) -> dict[int, Round | Unknown]:
    found: dict[int, Round | Unknown] = {}
    for player in players:
        then = before.get(player) if before is not None else None
        now = after.get(player)
        found[player] = player_round(
            Read.of(then) if then is not None else None, Read.of(now) if now is not None else None
        )
    return found


def _conceded(
    players: Iterable[int],
    before: Mapping[int, PlayerSeasonRow] | None,
    after: Mapping[int, PlayerSeasonRow],
) -> dict[int, int | None]:
    """Each player's team's goals against in the round, from his club's keepers' rows."""
    by_club: dict[str, int | None] = {}
    if before is not None:
        for row in after.values():
            if row.role != "P":
                continue
            then = before.get(row.player_id)
            if then is None or row.goals_conceded is None or then.goals_conceded is None:
                by_club[row.club] = None
            elif by_club.get(row.club, 0) is not None:
                by_club[row.club] = (by_club.get(row.club) or 0) + row.goals_conceded - then.goals_conceded
    clubs = {row.player_id: row.club for row in after.values()}
    return {player: by_club.get(clubs.get(player, "")) for player in players}


def _names(squad: StoredSquad) -> dict[int, str]:
    return {player.player_id: player.name for player in squad.players}


def _message(round: int, reviewed: Reviewed) -> str:
    real = reviewed.fielded_real.total
    scored = f"you scored {real:.1f}" if real is not None else "your real score isn't known"
    said = f"Round {round}: {scored}, against {reviewed.fielded.mean:.1f} expected."
    if not reviewed.choices:
        return said + " You followed the advice."
    gain = reviewed.total_gain
    did = f"this round they gained {gain:+.1f}" if gain is not None else "what they really did isn't known"
    return f"{said} Your choices were expected to cost {reviewed.total_cost:.2f}; {did}."


def _review(
    round: int,
    team: str,
    names: Mapping[int, str],
    reviewed: Reviewed,
    found: Record,
    played: Mapping[int, Round | Unknown],
    app_total: float | None,
) -> Review:
    def named(players: Sequence[int]) -> list[str]:
        return [names.get(player, str(player)) for player in players]

    real = reviewed.fielded_real.total
    involved = {
        *reviewed.fielded_real.unknown,
        *reviewed.advice_real.unknown,
        *(player for choice in reviewed.choices for player in choice.unknown),
    }
    not_counted = [
        f"{names.get(player, str(player))}: {result.reason}"
        for player in sorted(involved)
        if isinstance(result := played.get(player), Unknown)
    ]
    not_counted += [
        _EVENTS.get(event, event) for event in _not_counted(reviewed.fielded_real, reviewed.advice_real)
    ]
    return Review(
        round=round,
        team=team,
        replayed=reviewed.replayed,
        expected=round_to(reviewed.fielded.mean),
        low=round_to(reviewed.fielded.low),
        high=round_to(reviewed.fielded.high),
        real=real,
        fantasy_goals=reviewed.fielded_real.fantasy_goals,
        position=reviewed.position,
        app_total=app_total,
        app_differs=abs(app_total - real) > APP_GAP if app_total is not None and real is not None else None,
        advice_expected=round_to(reviewed.advice.mean),
        advice_real=reviewed.advice_real.total,
        total_cost=round_to(reviewed.total_cost),
        total_gain=reviewed.total_gain,
        choices=[
            ReviewChoice(
                kind=choice.kind,
                fielded=named(choice.fielded),
                advised=named(choice.advised),
                expected_cost=round_to(choice.expected_cost),
                real_gain=choice.real_gain,
                judged=choice.judged,
                mattered=choice.mattered,
                unknown=named(choice.unknown),
            )
            for choice in reviewed.choices
        ],
        record=RecordLine(
            rounds=found.rounds,
            overrides=found.overrides,
            expected_cost=round_to(found.expected_cost),
            real_gain=round_to(found.real_gain),
            counted=found.counted,
            margin=round_to(found.margin) if found.margin is not None else None,
            verdict=found.verdict,
        ),
        not_counted=not_counted,
    )


def _not_counted(*scores: RealScore) -> list[str]:
    return list(dict.fromkeys(event for score in scores for event in score.not_counted))


def round_to(value: float) -> float:
    return round(value, 2) + 0.0  # adding 0.0 turns a rounded -0.0 into 0.0
