"""A finished round scores itself, with nothing for the player to do (mvp-lineup design C10; R7.2 to R7.6).

At the next scheduled run or question, it reads the finished round's page for who really started, reads the
statistics page if it hasn't since the round, and scores both sets. It's skipped in the last hour before a
deadline, and it never stops an answer. The pure part is in `domains/calibration.py`."""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from fantadamus.contracts.types import Role
from fantadamus.core.clock import Clock
from fantadamus.domains.availability.consensus import Availability
from fantadamus.domains.availability.gold import availability
from fantadamus.domains.availability.silver import (
    OFFICIAL_LINEUPS,
    OUTLET_VIEWS,
    OutletViewRow,
)
from fantadamus.domains.calibration import (
    STARTING,
    THE_REST,
    CalibrationSet,
    ClubSheet,
    Outcome,
    RoundFrame,
    RoundReport,
    SetRow,
    StatsLine,
    Tally,
    add_outcomes,
    club_sheet,
    final_overrides,
    finished_round,
    last_told,
    outcome_of,
    round_frame,
    statistics_reads,
)
from fantadamus.domains.facts import latest_by, latest_submissions, read_silver
from fantadamus.domains.fixtures.gold import deadline, next_round
from fantadamus.domains.fixtures.silver import FIXTURES, FixtureRow
from fantadamus.domains.freshness import FACTS_WINDOW
from fantadamus.domains.odds.gold import team_xg
from fantadamus.domains.players.resolve import KnownPlayer, resolve, same_surname
from fantadamus.domains.season.gold import (
    known_players,
    league_goals_per_match,
    penalty_order,
    penalty_share,
    team_season,
)
from fantadamus.domains.season.silver import PLAYER_SEASONS, SEASON_STATS, PlayerSeasonRow
from fantadamus.engine.keepers import KeeperValue
from fantadamus.engine.outfield import OutfieldValue
from fantadamus.lake.calibration_store import CalibrationStore
from fantadamus.lake.collect_log import WORKED, CollectLog
from fantadamus.lake.decision_log import DecisionLog
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.league.rules import CLASSIC, scoring_for
from fantadamus.league.squads import MINE
from fantadamus.mcp.advisor import Facts, PlayerFacts, model_inputs, model_value
from fantadamus.web.cadence import may_read, may_read_page
from fantadamus.web.collector import Collector, CollectReport

_QUIET_BEFORE_DEADLINE = dt.timedelta(hours=1)


@dataclass(frozen=True)
class Calibrator:
    lake: LakeStore
    log: DecisionLog
    store: CalibrationStore
    clock: Clock
    collector: Collector | None = None
    collect_log: CollectLog | None = None

    def if_due(self, now: dt.datetime) -> RoundReport | None:
        """Score the newest finished round if it hasn't been, and if now is a good time. Otherwise nothing."""
        fixtures = read_silver(self.lake, FIXTURES)
        round = finished_round(fixtures, now)
        if round is None or self.store.get(round) is not None or self._deadline_is_close(fixtures, now):
            return None
        frame = round_frame(fixtures, round, now)
        if frame is None or not self._statistics_ready(frame, now):
            return None
        if not self._read_finished_page(round, now):
            return None
        return self.score(round, self.clock())

    def report(self, round: int, *, again: bool = False) -> RoundReport | None:
        """`fantadamus calibrate`: the round's report, scored now if it hasn't been or if asked to; None if
        the round hasn't finished."""
        now = self.clock()
        stored = self.store.get(round)
        if stored is not None and not again:
            return stored
        fixtures = read_silver(self.lake, FIXTURES)
        frame = round_frame(fixtures, round, now)
        if frame is None or now < frame.finished_at:
            return None
        self._read_finished_page(round, now, wait=False)
        self._statistics_ready(frame, now)
        return self.score(round, self.clock())

    @staticmethod
    def _deadline_is_close(fixtures: Sequence[FixtureRow], now: dt.datetime) -> bool:
        round = next_round(fixtures, now)
        kickoff = deadline(fixtures, round, now) if round is not None else None
        return kickoff is not None and kickoff - now < _QUIET_BEFORE_DEADLINE

    def _has_a_read_after(self, frame: RoundFrame, now: dt.datetime) -> bool:
        rows = read_silver(self.lake, SEASON_STATS, frame.first_kickoff - FACTS_WINDOW, now)
        changed, same = changed_reads(rows)
        return statistics_reads(changed, frame, worked=[*same, *self._worked(now)])[1] is not None

    def _worked(self, now: dt.datetime) -> list[dt.datetime]:
        return self.collect_log.worked("statistics", now) if self.collect_log is not None else []

    def _statistics_ready(self, frame: RoundFrame, now: dt.datetime) -> bool:
        """Whether scoring can go ahead: a read of the statistics page after the round, read now if need be,
        or no chance of one, because the next round has begun."""
        if self._read_after(frame, now):
            return True
        return frame.next_kickoff is not None and now >= frame.next_kickoff

    def _read_after(self, frame: RoundFrame, now: dt.datetime) -> bool:
        """Whether a read of the statistics page after the round is stored, reading it now if need be."""
        if self._has_a_read_after(frame, now):
            return True
        if self.collector is not None and self.collector.reads("player_season"):
            if may_read("player_season", self.collect_log, now):
                report = self.collector.collect(facts=["player_season"])
                self._logged(report)
            return self._has_a_read_after(frame, self.clock())
        return False

    def bracketing_reads(
        self, frame: RoundFrame, now: dt.datetime, *, read: bool = True
    ) -> tuple[Mapping[int, PlayerSeasonRow] | None, Mapping[int, PlayerSeasonRow] | None]:
        """Each player's row in the statistics read before the round and in the read after it, as stored by
        `now`; with `read`, the page is read now if no read after the round is stored (mvp-review C8). A
        replay of an earlier time doesn't read."""
        if read:
            self._read_after(frame, now)
            now = self.clock()
        rows = read_silver(self.lake, SEASON_STATS, frame.first_kickoff - FACTS_WINDOW, now)
        changed, same = changed_reads(rows)
        before, after = statistics_reads(changed, frame, worked=[*same, *self._worked(now)])

        def at(when: dt.datetime | None) -> Mapping[int, PlayerSeasonRow] | None:
            return None if when is None else {row.player_id: row for row in rows if row.captured_at == when}

        return at(before), at(after)

    def _read_finished_page(self, round: int, now: dt.datetime, *, wait: bool = True) -> bool:
        """Whether the round's page gave who started: it's asked again later if not (R7.2)."""
        if self.collector is None:
            return True
        if wait and not may_read_page("finished_round", self.collect_log, now):
            return False
        report = self.collector.collect_finished(round)
        self._logged(report)
        return all(page.outcome in WORKED for page in report.pages)

    def _logged(self, report: CollectReport) -> None:
        if self.collect_log is not None:
            self.collect_log.append(report)

    def score(self, round: int, now: dt.datetime) -> RoundReport:
        """Both sets, against what happened, stored (R7.4), with the model set's rows kept first, so that a
        report is never stored without them (mvp-recalibrate R1.1)."""
        fixtures = read_silver(self.lake, FIXTURES)
        frame = round_frame(fixtures, round, now)
        if frame is None:
            raise ValueError(f"round {round} has no fixtures")
        since = frame.first_kickoff - FACTS_WINDOW
        stats = read_silver(self.lake, SEASON_STATS, since, now)
        # Names are matched among everyone known now, which says nothing about the match.
        known = known_players([*read_silver(self.lake, PLAYER_SEASONS, since, now), *stats], now)
        by_id = {player.player_id: player for player in known}
        sheets = self._sheets(frame, known, now)
        before, after = _statistics(stats, frame, self._worked(now))

        kickoffs = {club: row.kickoff_at for row in frame.matches for club in (row.home, row.away)}

        def kickoff_of(player_id: int) -> dt.datetime | None:
            player = by_id.get(player_id)
            return kickoffs.get(player.club) if player else None

        decisions = self.log.read()
        told = Tally()
        for player_id, logged in last_told(decisions, round, kickoff_of).items():
            player = by_id[player_id]
            add_outcomes(
                told,
                outcome_of(player_id, sheets.get(player.club), before, after),
                p_start=logged.p_start,
                p_rating=logged.p_rating,
                p_scores=logged.p_scores,
                p_clean_sheet=logged.p_clean_sheet,
            )
        overrides = final_overrides(decisions, round, frame.first_kickoff, MINE)
        model = self._model_on_everyone(frame, known, sheets, before, after, now)
        report = RoundReport(
            round=round,
            scored_at=now,
            told=told.report(),
            model=model.report(),
            overrides=len(overrides),
            override_cost=sum(overrides),
        )
        self.store.keep_set(CalibrationSet(round=round, scored_at=now, rows=model.rows()))
        self.store.set(report)
        return report

    def _sheets(
        self, frame: RoundFrame, known: Sequence[KnownPlayer], now: dt.datetime
    ) -> dict[str, ClubSheet]:
        rows = read_silver(self.lake, OFFICIAL_LINEUPS, frame.first_kickoff - FACTS_WINDOW, now)
        latest = latest_submissions(rows, now, key=lambda row: (row.home, row.away))
        sheets: dict[str, ClubSheet] = {}
        for match in frame.matches:
            sheet = latest.get((match.home, match.away))
            if sheet is None:
                continue
            for club in (match.home, match.away):
                mates = [player for player in known if player.club == club]
                sheets[club] = club_sheet([row for row in sheet if row.club == club], mates)
        return sheets

    def _model_on_everyone(
        self,
        frame: RoundFrame,
        known: list[KnownPlayer],
        sheets: Mapping[str, ClubSheet],
        before: Mapping[int, StatsLine] | None,
        after: Mapping[int, StatsLine] | None,
        now: dt.datetime,
    ) -> Tally:
        """Every player the page lists, by the current model, on the facts held before his kickoff. Official
        lineups stay out: this scores the forecast, not the answer. Chances don't depend on a league's
        bonuses, so Classic's do. Starting needs no model: with nothing held then, it's the page's own
        percentages (design C10)."""
        facts = Facts.read(self.lake, frame.last_kickoff)
        listed = read_silver(self.lake, OUTLET_VIEWS, frame.first_kickoff - FACTS_WINDOW, now)
        tally = Tally()
        for match in frame.matches:
            on_page = [row for row in listed if (row.home, row.away) == (match.home, match.away)]
            _score_match(tally, match, facts, on_page, known, sheets, before, after, now)
        return tally


def changed_reads(rows: Sequence[PlayerSeasonRow]) -> tuple[list[dt.datetime], list[dt.datetime]]:
    """The reads that changed the figures, and those that stored the same ones again: a page unchanged for
    longer than an answer's window is stored again, which says nothing has moved."""
    changed: list[dt.datetime] = []
    same: list[dt.datetime] = []
    last = None
    for captured_at, content in sorted({(row.captured_at, row.content_sha256) for row in rows}):
        (changed if content != last else same).append(captured_at)
        last = content
    return changed, same


def _statistics(
    rows: Sequence[PlayerSeasonRow], frame: RoundFrame, worked: Sequence[dt.datetime]
) -> tuple[Mapping[int, StatsLine] | None, Mapping[int, StatsLine] | None]:
    """His figures in the read before the round and in the read after it."""

    def read_at(when: dt.datetime | None) -> Mapping[int, StatsLine] | None:
        if when is None:
            return None
        return {
            row.player_id: StatsLine(
                rated_appearances=row.rated_appearances, goals=row.goals, goals_conceded=row.goals_conceded
            )
            for row in rows
            if row.captured_at == when
        }

    changed, same = changed_reads(rows)
    before, after = statistics_reads(changed, frame, worked=[*same, *worked])
    return read_at(before), read_at(after)


def _score_match(
    tally: Tally,
    match: FixtureRow,
    facts: Facts,
    on_page: Sequence[OutletViewRow],
    known: list[KnownPlayer],
    sheets: Mapping[str, ClubSheet],
    before: Mapping[int, StatsLine] | None,
    after: Mapping[int, StatsLine] | None,
    now: dt.datetime,
) -> None:
    as_of = match.kickoff_at - dt.timedelta(microseconds=1)
    forms = latest_by(facts.players, as_of, key=lambda row: row.player_id)
    views = [row for row in facts.views if (row.home, row.away) == (match.home, match.away)]
    xg = team_xg(facts.odds, facts.teams, home=match.home, away=match.away, as_of=as_of)
    league = league_goals_per_match(facts.teams, as_of)
    names: dict[tuple[str, str], KnownPlayer | None] = {}

    def chances(player: KnownPlayer, when: dt.datetime) -> Availability | None:
        return availability(
            player,
            home=match.home,
            away=match.away,
            views=views,
            officials=(),
            players=known,
            as_of=when,
            outlet_views=on_page,
            names=names,
        )

    def starts(mate: KnownPlayer) -> float:
        present = chances(mate, as_of)
        return present.p_start if present is not None else 1.0

    seen: set[int] = set()
    for club, name in sorted({(row.club, row.name) for row in on_page}):
        mates = [player for player in known if player.club == club]
        player = resolve(name, mates).player or same_surname(name, mates)
        if player is None:
            tally.note("Everything", "on the round's page but not on the statistics page")
            continue
        if player.player_id in seen:
            continue
        seen.add(player.player_id)
        present = chances(player, as_of)
        outcome = outcome_of(player.player_id, sheets.get(club), before, after)
        form, table = forms.get(player.player_id), team_season(facts.teams, club, as_of)
        order = penalty_order(facts.takers, club, as_of)
        if present is None or form is None or table is None or order is None:
            page = present or chances(player, now)
            if page is not None:
                tally.add(STARTING, page.p_start, outcome.started)
                tally.keep(_set_row(match, club, player.player_id, outcome, page))
            tally.note(THE_REST, "no facts held before his kickoff")
            continue
        share = penalty_share(player, order, mates, starts)
        inputs = model_inputs(PlayerFacts(player, form, table, order, match, present, xg, [], share), league)
        value = model_value(inputs, scoring_for(CLASSIC, form.role))
        row = _set_row(match, club, player.player_id, outcome, present, role=form.role, value=value)
        tally.keep(row)
        add_outcomes(
            tally,
            outcome,
            p_start=row.p_start,
            p_rating=row.p_rating,
            p_scores=row.p_scores,
            p_clean_sheet=row.p_clean_sheet,
        )


def _set_row(
    match: FixtureRow,
    club: str,
    player_id: int,
    outcome: Outcome,
    present: Availability,
    *,
    role: Role | None = None,
    value: OutfieldValue | KeeperValue | None = None,
) -> SetRow:
    """His row in the model set, with the outlets' consensus before the map. Without a value, only his chance
    of starting was known."""
    outfield = value if isinstance(value, OutfieldValue) else None
    keeper = value if isinstance(value, KeeperValue) else None
    return SetRow(
        round=match.round,
        home=match.home,
        away=match.away,
        club=club,
        player_id=player_id,
        role=role,
        consensus=present.raw_p_start,
        p_start=value.p_start if value is not None else present.p_start,
        p_rating=value.p_rating if value is not None else None,
        p_scores=outfield.p_scores if outfield is not None else None,
        p_scores_cameo=outfield.p_scores_cameo if outfield is not None else None,
        p_clean_sheet=keeper.p_clean_sheet if keeper is not None else None,
        outcome=outcome,
    )
