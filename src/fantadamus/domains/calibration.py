"""Scoring a finished round's forecasts against what happened (mvp-lineup design C10; R7; method §A8).

Pure: this module knows what a score is, what happened to a player, and how a report reads. `mcp/calibrate.py`
reads the pages and runs the model. A report holds aggregates only, so that it can go in a committed report;
no player is named in it."""

from __future__ import annotations

import bisect
import datetime as dt
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from fantadamus.contracts.types import UtcDatetime
from fantadamus.core.files import temporary_beside
from fantadamus.domains.availability.silver import OfficialLineupRow
from fantadamus.domains.fixtures.gold import matches
from fantadamus.domains.fixtures.silver import FixtureRow
from fantadamus.domains.players.resolve import KnownPlayer, resolve, same_surname
from fantadamus.lake.decision_log import Decision, LoggedPlayer

FINISHED_AFTER = dt.timedelta(hours=12)
"""*(start)* How long after a round's last kickoff it counts as finished: the statistics page must update."""
STARTING = "Starting"
RATING = "Getting a rating"
SCORING = "Scoring, if he started"
CLEAN_SHEET = "Clean sheet, if he started"
THE_REST = "Chances other than starting"
_BUCKETS = 10
DEFAULT_ROOT = Path("data/local/calibration")

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
                said=sum(chance for chance, _ in group) / len(group),
                happened=sum(happened for _, happened in group) / len(group),
            )
            for index, group in sorted(groups.items())
        ],
    )


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

    def add(self, name: str, chance: float, outcome: Result) -> None:
        if isinstance(outcome, str):
            self.note(name, outcome)
        else:
            self._pairs.setdefault(name, []).append((chance, outcome))

    def note(self, name: str, reason: str) -> None:
        self._unscored[f"{name}: {reason}"] += 1

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


class CalibrationStore:
    """One file per round, derived and so recomputable: it isn't part of the decision log."""

    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def _path(self, round: int) -> Path:
        return self.root / f"round-{round}.json"

    def get(self, round: int) -> RoundReport | None:
        path = self._path(round)
        return RoundReport.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None

    def set(self, report: RoundReport) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(report.round)
        temporary = temporary_beside(path)
        temporary.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    def latest(self) -> RoundReport | None:
        rounds = [int(path.stem.removeprefix("round-")) for path in self.root.glob("round-*.json")]
        return self.get(max(rounds)) if rounds else None


@dataclass(frozen=True)
class RoundFrame:
    """A round's matches and the times that matter for scoring it."""

    round: int
    matches: list[FixtureRow]
    first_kickoff: dt.datetime
    last_kickoff: dt.datetime
    next_kickoff: dt.datetime | None
    """The next round's first kickoff, if it's known."""

    @property
    def finished_at(self) -> dt.datetime:
        return self.last_kickoff + FINISHED_AFTER


def round_frame(fixtures: Sequence[FixtureRow], round: int, as_of: dt.datetime) -> RoundFrame | None:
    known = matches(fixtures, as_of)
    played = [row for row in known if row.round == round]
    if not played:
        return None
    later = [row.kickoff_at for row in known if row.round > round]
    return RoundFrame(
        round=round,
        matches=played,
        first_kickoff=min(row.kickoff_at for row in played),
        last_kickoff=max(row.kickoff_at for row in played),
        next_kickoff=min(later, default=None),
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


def statistics_reads(
    stored: Iterable[dt.datetime], frame: RoundFrame, *, worked: Iterable[dt.datetime] = ()
) -> tuple[dt.datetime | None, dt.datetime | None]:
    """The last stored read of the statistics page before the round, and the stored read that shows what the
    page held once it had finished, before the next. `worked` adds the reads that found the page unchanged:
    they store nothing, and show that it still held what the last stored read did. A page that hasn't moved
    since before the round hasn't updated yet."""
    times = sorted(set(stored))
    start = bisect.bisect_left(times, frame.first_kickoff)
    before = times[start - 1] if start else None
    for when in sorted({*times, *worked}):
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
    started: Result
    if sheet is None:
        started = "no official lineup stored"
    elif player_id in sheet.starters:
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
