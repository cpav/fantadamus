"""Scoring a finished round's forecasts against what happened (mvp-lineup design C10; R7; method §A8).

Pure: this module knows what a score is, what happened to a player, and how a report reads. `mcp/calibrate.py`
reads the pages and runs the model. A report holds aggregates only, so that it can go in a committed report;
no player is named in it. Its calibration set, kept beside it for a later fit, names players by their ids and
stays private (mvp-recalibrate design C1)."""

from __future__ import annotations

import bisect
import datetime as dt
import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass

from pydantic import BaseModel

from fantadamus.contracts.types import Role, UtcDatetime
from fantadamus.core.names import name_key
from fantadamus.domains.availability.silver import OfficialLineupRow
from fantadamus.domains.fixtures.gold import matches
from fantadamus.domains.fixtures.silver import FixtureRow
from fantadamus.domains.players.resolve import KnownPlayer, resolve, same_surname
from fantadamus.domains.season.silver import PlayerSeasonRow, TeamSeasonRow
from fantadamus.engine.recalibrate import Rate, cameo_rated, cameo_share, counted
from fantadamus.lake.decision_log import Decision, LoggedPlayer

FINISHED_AFTER = dt.timedelta(hours=12)
"""*(start)* How long after a round's last kickoff it counts as finished: the statistics page must update."""
STARTING = "Starting"
RATING = "Getting a rating"
SCORING = "Scoring, if he started"
CLEAN_SHEET = "Clean sheet, if he started"
THE_REST = "Chances other than starting"
_BUCKETS = 10

Pair = tuple[float, bool]
"""A chance, and whether it happened."""
Result = bool | str
"""Whether it happened, or why that isn't known."""


def brier(pairs: Iterable[Pair]) -> float:
    """The mean squared gap between each chance and what happened: 0 is perfect."""
    gaps = [(chance - (1.0 if happened else 0.0)) ** 2 for chance, happened in pairs]
    return sum(gaps) / len(gaps)


class Bucket(BaseModel):
    low: float
    high: float
    count: int
    said: float
    """The mean chance given."""
    happened: float
    """How often it happened."""


class Scored(BaseModel):
    chance: str
    count: int
    brier: float
    baseline: float
    """The score of always guessing the set's average, the bar to beat."""
    buckets: list[Bucket]


def scored_chance(name: str, pairs: Sequence[Pair]) -> Scored:
    rate = sum(happened for _, happened in pairs) / len(pairs)
    groups: dict[int, list[Pair]] = {}
    for pair in pairs:
        groups.setdefault(min(int(pair[0] * _BUCKETS), _BUCKETS - 1), []).append(pair)
    return Scored(
        chance=name,
        count=len(pairs),
        brier=brier(pairs),
        baseline=brier([(rate, happened) for _, happened in pairs]),
        buckets=[
            Bucket(
                low=index / _BUCKETS,
                high=(index + 1) / _BUCKETS,
                count=len(group),
                said=_within(math.fsum(chance for chance, _ in group) / len(group), index),
                happened=sum(happened for _, happened in group) / len(group),
            )
            for index, group in sorted(groups.items())
        ],
    )


def _within(mean: float, index: int) -> float:
    """A bucket's mean chance, kept inside the bucket: every chance in it is, but the mean of three 0.7s comes
    out a hair under 0.7 in floats."""
    return min(max(mean, index / _BUCKETS), (index + 1) / _BUCKETS)


class Unscored(BaseModel):
    reason: str
    count: int


class SetReport(BaseModel):
    scored: list[Scored]
    unscored: list[Unscored]


class Tally:
    """The chances of one set, as they're scored or found to be unscorable."""

    def __init__(self) -> None:
        self._pairs: dict[str, list[Pair]] = {}
        self._unscored: Counter[str] = Counter()
        self._rows: list[SetRow] = []

    def add(self, name: str, chance: float, outcome: Result) -> None:
        if isinstance(outcome, str):
            self.note(name, outcome)
        else:
            self._pairs.setdefault(name, []).append((chance, outcome))

    def note(self, name: str, reason: str) -> None:
        self._unscored[f"{name}: {reason}"] += 1

    def keep(self, row: SetRow) -> None:
        """A player's row for the set: it scores nothing on its own."""
        self._rows.append(row)

    def rows(self) -> list[SetRow]:
        """By match and player: the set doesn't depend on the order the facts were stored in (R1.3)."""
        return sorted(self._rows, key=lambda row: (row.home, row.away, row.player_id))

    def report(self) -> SetReport:
        return SetReport(
            scored=[scored_chance(name, pairs) for name, pairs in self._pairs.items()],
            unscored=[
                Unscored(reason=reason, count=count) for reason, count in sorted(self._unscored.items())
            ],
        )


class RoundReport(BaseModel):
    round: int
    scored_at: UtcDatetime
    told: SetReport
    """What users were told: each player's last logged chances before his kickoff."""
    model: SetReport
    """The current model on every listed player, from the facts held before his kickoff."""
    overrides: int = 0
    override_cost: float = 0.0
    """Their costs as stated at the time. Whether they paid off is the review of a user's lineup, not this."""


def _set_lines(title: str, report: SetReport) -> list[str]:
    lines = [title]
    for chance in report.scored:
        lines.append(
            f"  {chance.chance}: Brier {chance.brier:.3f} over {chance.count}, against "
            f"{chance.baseline:.3f} for always guessing the average"
        )
        lines += [
            f"    said {bucket.low:.0%}-{bucket.high:.0%}: {bucket.said:.1%} on average, "
            f"{bucket.happened:.1%} happened, {bucket.count} players"
            for bucket in chance.buckets
        ]
    if not report.scored:
        lines.append("  Nothing scored.")
    if report.unscored:
        lines.append("  Couldn't score:")
        lines += [f"    {entry.reason}: {entry.count}" for entry in report.unscored]
    return lines


def render(report: RoundReport) -> str:
    return "\n".join(
        [
            f"Round {report.round}, scored {report.scored_at:%Y-%m-%d %H:%M} UTC",
            *_set_lines("The model on everyone", report.model),
            *_set_lines("What users were told", report.told),
            f"Overrides: {report.overrides}, at a stated cost of {report.override_cost:.2f} points",
        ]
    )


def summary_line(report: RoundReport) -> str | None:
    """One line for the next lineup, or None with nothing scored (R7.6)."""
    chance = next(
        (found for found in (*report.model.scored, *report.told.scored) if found.chance == STARTING), None
    )
    if chance is None:
        return None
    return (
        f"Round {report.round}'s forecasts: chances of starting scored {chance.brier:.3f} over "
        f"{chance.count} players, against {chance.baseline:.3f} for always guessing the average. "
        "Lower is better."
    )


@dataclass(frozen=True)
class RoundFrame:
    """A round's matches and the times that matter for scoring it."""

    round: int
    matches: list[FixtureRow]
    first_kickoff: dt.datetime
    last_kickoff: dt.datetime
    next_kickoff: dt.datetime | None
    """The next round's first kickoff, if it's known."""
    previous_kickoff: dt.datetime | None = None
    """The last kickoff before this round began, if it's known."""

    @property
    def finished_at(self) -> dt.datetime:
        return self.last_kickoff + FINISHED_AFTER


def round_frame(fixtures: Sequence[FixtureRow], round: int, as_of: dt.datetime) -> RoundFrame | None:
    known = matches(fixtures, as_of)
    played = [row for row in known if row.round == round]
    if not played:
        return None
    first_kickoff = min(row.kickoff_at for row in played)
    later = [row.kickoff_at for row in known if row.round > round]
    earlier = [row.kickoff_at for row in known if row.round < round and row.kickoff_at < first_kickoff]
    return RoundFrame(
        round=round,
        matches=played,
        first_kickoff=first_kickoff,
        last_kickoff=max(row.kickoff_at for row in played),
        next_kickoff=min(later, default=None),
        previous_kickoff=max(earlier, default=None),
    )


def finished_round(fixtures: Sequence[FixtureRow], as_of: dt.datetime) -> int | None:
    """The newest round that has finished, or None."""
    last: dict[int, dt.datetime] = {}
    for row in matches(fixtures, as_of):
        last[row.round] = max(last.get(row.round, row.kickoff_at), row.kickoff_at)
    done = [round for round, kickoff in last.items() if as_of >= kickoff + FINISHED_AFTER]
    return max(done, default=None)


def last_told(
    decisions: Iterable[Decision], round: int, kickoff_of: Callable[[int], dt.datetime | None]
) -> dict[int, LoggedPlayer]:
    """Each player's last chances logged before his kickoff, in this round (R7.4). A replay asked after his
    kickoff wasn't a forecast, whatever time it asks about."""
    told: dict[int, tuple[dt.datetime, LoggedPlayer]] = {}
    for decision in decisions:
        if decision.round != round:
            continue
        for logged in decision.players:
            kickoff = kickoff_of(logged.player_id)
            if kickoff is None or decision.as_of >= kickoff or decision.logged_at >= kickoff:
                continue
            seen = told.get(logged.player_id)
            if seen is None or decision.as_of >= seen[0]:
                told[logged.player_id] = decision.as_of, logged
    return {player_id: logged for player_id, (_, logged) in told.items()}


def final_overrides(decisions: Iterable[Decision], round: int, lock: dt.datetime, team: str) -> list[float]:
    """What each user's choice was said to cost: their last lineup for `team` before the lock, if it went
    against the advice. Asking what a choice would cost isn't making it, however often it's asked."""
    last: dict[str, Decision] = {}
    for decision in decisions:
        if (
            decision.kind != "lineup"
            or decision.round != round
            or name_key(decision.team or "") != name_key(team)
            or decision.logged_at >= lock
        ):
            continue
        seen = last.get(decision.user)
        if seen is None or decision.logged_at >= seen.logged_at:
            last[decision.user] = decision
    return [decision.override_cost for decision in last.values() if decision.override_cost is not None]


@dataclass(frozen=True)
class ClubSheet:
    """Who his club's official lineup says started."""

    starters: frozenset[int]
    named: frozenset[int]
    unnamed_starters: bool


def club_sheet(rows: Iterable[OfficialLineupRow], mates: Sequence[KnownPlayer]) -> ClubSheet:
    """From one club's rows of an official lineup, each name found among his club-mates."""
    starters, named = set(), set()
    unnamed = False
    for row in rows:
        unnamed = unnamed or bool(row.unnamed_starters)
        player = resolve(row.name, mates).player or same_surname(row.name, mates)
        if player is not None:
            named.add(player.player_id)
            if row.status == "starter":
                starters.add(player.player_id)
    return ClubSheet(frozenset(starters), frozenset(named), unnamed)


@dataclass(frozen=True)
class Outcome:
    """What happened to a player in his match, or why that isn't known."""

    started: Result
    rated: Result
    scored: Result
    clean_sheet: Result


class SetRow(BaseModel):
    """One player in a round's model set: the chances the model gave him, and what happened (mvp-recalibrate
    design C1). A substitute who got a rating didn't start and was rated; one who came on without a rating
    can't be told from one who didn't come on, since the statistics page counts rated games only."""

    round: int
    home: str
    away: str
    club: str
    player_id: int
    role: Role | None
    """None when the model couldn't value him before kickoff: then only his chance of starting is known."""
    consensus: float
    """The outlets' chance of starting, before any map: a later fit doesn't compound on an earlier one."""
    p_start: float
    p_rating: float | None
    p_scores: float | None
    """An outfield player's chance of scoring if he starts."""
    p_scores_cameo: float | None
    """And if he comes on, for the fit of an attacker's cameo."""
    p_clean_sheet: float | None
    """A keeper's chance of a clean sheet if he starts."""
    outcome: Outcome


class CalibrationSet(BaseModel):
    """A round's model set, player by player, kept privately beside its report (R1.1, R1.2)."""

    round: int
    scored_at: UtcDatetime
    rows: list[SetRow]


def statistics_reads(
    stored: Iterable[dt.datetime], frame: RoundFrame, *, worked: Iterable[dt.datetime] = ()
) -> tuple[dt.datetime | None, dt.datetime | None]:
    """The stored reads that show what the page held before the round and once it had finished. `worked` adds
    the reads that found the page unchanged: they store nothing, and show that it still held what the last
    stored read did. The first must show the last round finished, or this round's gains would include some
    of its matches. A page that hasn't moved since before the round hasn't updated yet."""
    times = sorted(set(stored))
    seen = sorted({*times, *worked})
    start = bisect.bisect_left(times, frame.first_kickoff)
    settled = frame.previous_kickoff + FINISHED_AFTER if frame.previous_kickoff is not None else None
    in_time_before = settled is None or any(settled <= when < frame.first_kickoff for when in seen)
    before = times[start - 1] if start and in_time_before else None
    for when in seen:
        in_time = when >= frame.finished_at and (frame.next_kickoff is None or when < frame.next_kickoff)
        place = bisect.bisect_right(times, when)
        if in_time and place > start:
            return before, times[place - 1]
    return before, None


class StatsLine(BaseModel):
    """A player's figures in one read of the statistics page, as far as scoring needs them."""

    rated_appearances: int
    goals: int
    goals_conceded: int | None


def outcome_of(
    player_id: int,
    sheet: ClubSheet | None,
    before: Mapping[int, StatsLine] | None,
    after: Mapping[int, StatsLine] | None,
) -> Outcome:
    if sheet is None:  # a postponed match has no marks either, and nobody in it could get a rating
        reason = "no official lineup stored"
        return Outcome(reason, reason, reason, reason)
    started: Result
    if player_id in sheet.starters:
        started = True
    elif player_id not in sheet.named and sheet.unnamed_starters:
        started = "his club's lineup doesn't name every starter"
    else:
        started = False
    if before is None or after is None:
        reason = (
            "no statistics read before the round" if before is None else "no statistics read after the round"
        )
        return Outcome(started, reason, reason, reason)
    then, now = before.get(player_id), after.get(player_id)
    if then is None or now is None:
        reason = "not on the statistics page before and after the round"
        return Outcome(started, reason, reason, reason)
    clean_sheet: Result = (
        "his goals conceded aren't known"
        if then.goals_conceded is None or now.goals_conceded is None
        else now.goals_conceded == then.goals_conceded
    )
    return Outcome(
        started=started,
        rated=now.rated_appearances > then.rated_appearances,
        scored=now.goals > then.goals,
        clean_sheet=clean_sheet,
    )


def add_outcomes(
    tally: Tally,
    outcome: Outcome,
    *,
    p_start: float,
    p_rating: float | None,
    p_scores: float | None,
    p_clean_sheet: float | None,
) -> None:
    """One player's chances against what happened. Scoring and a clean sheet are chances if he starts, so they
    count only if he did."""
    tally.add(STARTING, p_start, outcome.started)
    if p_rating is None:
        tally.note(RATING, "logged before the chance of a rating was")
    else:
        tally.add(RATING, p_rating, outcome.rated)
    for name, chance, result in (
        (SCORING, p_scores, outcome.scored),
        (CLEAN_SHEET, p_clean_sheet, outcome.clean_sheet),
    ):
        if chance is None or outcome.started is False:
            continue
        if isinstance(outcome.started, str):
            tally.note(name, outcome.started)
        else:
            tally.add(name, chance, result)


class Fitted(BaseModel):
    """Rates counted from the evidence, and each one that couldn't be, with why (mvp-recalibrate C4, C5)."""

    rates: list[Rate]
    missing: list[str]


def cameo_rates(rows: Sequence[SetRow]) -> Fitted:
    """`CAMEO_SHARE` from defenders and midfielders, then `CAMEO_RATED` from forwards with it (C4). Each
    counts the players who didn't start, whose rating is known, and to whom the model gave a chance of coming
    on."""
    benched = [
        row
        for row in rows
        if row.outcome.started is False
        and isinstance(row.outcome.rated, bool)
        and row.p_rating is not None
        and row.p_rating > row.p_start
    ]
    share = cameo_share([row.outcome.rated is True for row in benched if row.role in ("D", "C")])
    if share is None:
        return Fitted(
            rates=[],
            missing=[
                "CAMEO_SHARE: no defender or midfielder who didn't start and could have come on",
                "CAMEO_RATED: needs CAMEO_SHARE",
            ],
        )
    forwards = [
        (row.p_scores_cameo, row.outcome.rated is True)
        for row in benched
        if row.role == "A" and row.p_scores_cameo is not None
    ]
    rated = cameo_rated(forwards, share.value)
    if rated is None:
        reason = (
            "no forward who didn't start and could have come on"
            if not forwards
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
