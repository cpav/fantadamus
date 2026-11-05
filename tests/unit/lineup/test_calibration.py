"""mvp-lineup tasks 7.1 and 7.2: scoring a finished round, by hand (design C10; R7.2 to R7.4)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import pytest

from fantadamus.domains.availability.gold import availability
from fantadamus.domains.availability.silver import LineupViewRow, OfficialLineupRow
from fantadamus.domains.calibration import (
    FINISHED_AFTER,
    Bucket,
    CalibrationStore,
    ClubSheet,
    Outcome,
    RoundFrame,
    RoundReport,
    SetReport,
    StatsLine,
    Tally,
    add_outcomes,
    brier,
    club_sheet,
    finished_round,
    last_told,
    outcome_of,
    render,
    scored_chance,
    statistics_reads,
    summary_line,
)
from fantadamus.domains.fixtures.silver import FixtureRow
from fantadamus.domains.players.resolve import KnownPlayer
from fantadamus.lake.decision_log import Decision, LoggedPlayer
from fantadamus.league.rules import CLASSIC, StoredRules

T0 = dt.datetime(2026, 11, 6, 19, 45, tzinfo=dt.UTC)


def _fixture(round: int, home: str, away: str, kickoff: dt.datetime) -> FixtureRow:
    return FixtureRow(
        source_url="https://example.org/f",
        captured_at=T0 - dt.timedelta(days=9),
        content_sha256="x",
        round=round,
        home=home,
        away=away,
        kickoff_at=kickoff,
    )


LAST = T0 + dt.timedelta(days=3)
FIXTURES = [
    _fixture(11, "alfa", "beta", T0),
    _fixture(11, "gamma", "delta", LAST),
    _fixture(12, "alfa", "gamma", T0 + dt.timedelta(days=7)),
]


def test_when_a_round_has_finished() -> None:
    """Twelve hours after its last kickoff, so the statistics page has had time to update."""
    assert dt.timedelta(hours=12) == FINISHED_AFTER
    assert finished_round(FIXTURES, T0) is None
    assert finished_round(FIXTURES, LAST + dt.timedelta(hours=11, minutes=59)) is None
    assert finished_round(FIXTURES, LAST + dt.timedelta(hours=12)) == 11
    assert finished_round(FIXTURES, T0 + dt.timedelta(days=30)) == 12  # the newest one that has finished
    assert finished_round([], T0) is None


def test_hand_worked_scores() -> None:
    pairs = [(0.9, True), (0.9, True), (0.9, False), (0.2, False)]
    assert brier(pairs) == pytest.approx((0.01 + 0.01 + 0.81 + 0.04) / 4)
    chance = scored_chance("Starting", pairs)
    assert chance.count == 4
    assert chance.brier == pytest.approx(0.2175)
    assert chance.baseline == pytest.approx(0.25)  # always guessing the average, 50%
    [low, high] = chance.buckets
    assert low == Bucket(low=0.2, high=0.3, count=1, said=0.2, happened=0.0)
    assert high.model_dump() == pytest.approx(
        {"low": 0.9, "high": 1.0, "count": 3, "said": 0.9, "happened": 2 / 3}, abs=0.001
    )


def test_a_certain_chance_falls_in_the_top_bucket() -> None:
    [top] = scored_chance("Starting", [(1.0, True)]).buckets
    assert (top.low, top.high) == (0.9, 1.0)


def test_unscored_named_with_the_reason() -> None:
    tally = Tally()
    tally.add("Starting", 0.9, True)
    tally.add("Starting", 0.9, "no official lineup stored")
    tally.add("Starting", 0.5, "no official lineup stored")
    tally.add("Scoring, if he started", 0.2, "no statistics read after the round")
    report = tally.report()
    assert [(chance.chance, chance.count) for chance in report.scored] == [("Starting", 1)]
    assert {(entry.reason, entry.count) for entry in report.unscored} == {
        ("Starting: no official lineup stored", 2),
        ("Scoring, if he started: no statistics read after the round", 1),
    }


def _report() -> RoundReport:
    tally = Tally()
    for chance, outcome in ((0.9, True), (0.9, True), (0.2, False), (0.2, True)):
        tally.add("Starting", chance, outcome)
    tally.add("Starting", 0.5, "no official lineup stored")
    return RoundReport(
        round=11,
        scored_at=T0,
        told=SetReport(scored=[], unscored=[]),
        model=tally.report(),
        overrides=2,
        override_cost=1.5,
    )


def test_the_report_reads_as_aggregates() -> None:
    text = render(_report())
    assert "Round 11" in text
    assert "The model on everyone" in text
    assert "What users were told" in text
    assert "Starting: Brier 0.175 over 4, against 0.188 for always guessing the average" in text
    assert "no official lineup stored: 1" in text
    assert "Overrides: 2, at a stated cost of 1.50 points" in text


def test_the_line_for_the_next_lineup() -> None:
    assert summary_line(_report()) == (
        "Round 11's forecasts: chances of starting scored 0.175 over 4 players, against 0.188 for "
        "always guessing the average. Lower is better."
    )
    empty = RoundReport(
        round=11,
        scored_at=T0,
        told=SetReport(scored=[], unscored=[]),
        model=SetReport(scored=[], unscored=[]),
    )
    assert summary_line(empty) is None


def test_a_round_is_stored_once_per_round(tmp_path: Path) -> None:
    store = CalibrationStore(tmp_path)
    assert store.get(11) is None
    assert store.latest() is None
    store.set(_report())
    stored = store.get(11)
    assert stored is not None
    assert stored.round == 11
    assert (tmp_path / "round-11.json").is_file()
    store.set(_report().model_copy(update={"round": 9}))
    latest = store.latest()
    assert latest is not None
    assert latest.round == 11


def _logged(player_id: int, p_start: float) -> LoggedPlayer:
    return LoggedPlayer(player_id=player_id, name=f"P{player_id}", p_start=p_start, p_cameo=0.0, key=6.0)


def _decision(
    at: dt.datetime, *players: LoggedPlayer, round: int = 11, logged_at: dt.datetime | None = None
) -> Decision:
    return Decision(
        as_of=at,
        logged_at=logged_at or at,
        user="u",
        round=round,
        players=list(players),
        rules=StoredRules(user="u", saved_at=T0, rules=CLASSIC),
        content_hashes=[],
    )


def _last(decisions: Sequence[Decision], kickoff: dt.datetime = T0) -> dict[int, float]:
    return {
        player_id: logged.p_start for player_id, logged in last_told(decisions, 11, lambda _: kickoff).items()
    }


def test_what_users_were_told_is_the_last_before_kickoff() -> None:
    early, late = T0 - dt.timedelta(days=2), T0 - dt.timedelta(hours=1)
    after = T0 + dt.timedelta(minutes=1)
    decisions = [
        _decision(late, _logged(1, 0.7)),
        _decision(early, _logged(1, 0.5), _logged(2, 0.4)),
        _decision(after, _logged(1, 0.99), _logged(3, 0.8)),  # after his kickoff: not a forecast
        _decision(early, _logged(4, 0.3), round=10),  # another round
    ]
    assert _last(decisions) == {1: 0.7, 2: 0.4}


def test_a_replay_logged_after_kickoff_doesnt_count() -> None:
    """An earlier as-of asked later isn't what the user was told in time."""
    replay = _decision(T0 - dt.timedelta(hours=1), _logged(1, 0.9), logged_at=T0 + dt.timedelta(hours=1))
    assert _last([replay]) == {}
    ahead = _decision(T0 + dt.timedelta(hours=1), _logged(1, 0.9), logged_at=T0 - dt.timedelta(hours=1))
    assert _last([ahead]) == {}  # logged in time, but about a moment after his kickoff


def test_a_player_with_no_match_is_left_out() -> None:
    decisions = [_decision(T0 - dt.timedelta(hours=1), _logged(1, 0.7), _logged(2, 0.5))]
    told = last_told(decisions, 11, lambda player_id: T0 if player_id == 1 else None)
    assert set(told) == {1}


FINISHED = LAST + FINISHED_AFTER
NEXT = T0 + dt.timedelta(days=7)
FRAME = RoundFrame(round=11, matches=[], first_kickoff=T0, last_kickoff=LAST, next_kickoff=NEXT)


def test_which_statistics_reads_count() -> None:
    """The last before the round's first kickoff, and the first once it has finished, before the next."""
    long_before, before = T0 - dt.timedelta(days=3), T0 - dt.timedelta(days=1)
    during, after = T0 + dt.timedelta(hours=1), FINISHED + dt.timedelta(hours=1)
    reads = [after + dt.timedelta(hours=1), during, long_before, after, before, NEXT + dt.timedelta(hours=1)]
    assert statistics_reads(reads, FRAME) == (before, after)
    assert statistics_reads([before, during], FRAME) == (before, None)
    assert statistics_reads([before, NEXT], FRAME) == (before, None)  # the next round has started
    assert statistics_reads([FINISHED], FRAME) == (None, FINISHED)
    assert statistics_reads([T0], FRAME) == (None, None)  # at the kickoff is too late to be "before"
    unknown = RoundFrame(round=11, matches=[], first_kickoff=T0, last_kickoff=LAST, next_kickoff=None)
    assert statistics_reads([before, NEXT], unknown) == (before, NEXT)


def _official(name: str, status: Literal["starter", "bench"], unnamed: int = 0) -> OfficialLineupRow:
    return OfficialLineupRow(
        source_url="https://example.org/p",
        captured_at=T0,
        content_sha256="x",
        home="alfa",
        away="beta",
        club="alfa",
        name=name,
        status=status,
        unnamed_starters=unnamed,
    )


def test_a_clubs_sheet() -> None:
    mates = [
        KnownPlayer(player_id=n, name=f"Alfa {word}", club="alfa") for n, word in enumerate(("Uno", "Due"))
    ]
    sheet = club_sheet([_official("Alfa Uno", "starter"), _official("Alfa Due", "bench")], mates)
    assert sheet == ClubSheet(frozenset({0}), frozenset({0, 1}), False)
    assert club_sheet([_official("Alfa Uno", "starter", unnamed=1)], mates).unnamed_starters
    assert club_sheet([_official("Nobody Here", "starter")], mates).named == frozenset()


def test_what_happened_to_a_player() -> None:
    sheet = ClubSheet(frozenset({1}), frozenset({1, 2}), False)
    assert outcome_of(1, sheet, None, None).started is True
    assert outcome_of(2, sheet, None, None).started is False
    assert outcome_of(3, sheet, None, None).started is False  # not on a sheet that names everyone
    partial = ClubSheet(frozenset({1}), frozenset({1, 2}), True)
    assert outcome_of(1, partial, None, None).started is True
    assert outcome_of(2, partial, None, None).started is False
    assert outcome_of(3, partial, None, None).started == "his club's lineup doesn't name every starter"
    assert outcome_of(1, None, None, None).started == "no official lineup stored"

    before = {1: StatsLine(rated_appearances=8, goals=2, goals_conceded=5)}
    assert outcome_of(1, sheet, None, before).rated == "no statistics read before the round"
    assert outcome_of(1, sheet, before, None).scored == "no statistics read after the round"
    assert outcome_of(1, sheet, before, {}).rated == "not on the statistics page before and after the round"
    same = outcome_of(1, sheet, before, before)
    assert (same.rated, same.scored, same.clean_sheet) == (False, False, True)
    moved = {1: StatsLine(rated_appearances=9, goals=3, goals_conceded=6)}
    gained = outcome_of(1, sheet, before, moved)
    assert (gained.rated, gained.scored, gained.clean_sheet) == (True, True, False)
    outfield = {1: StatsLine(rated_appearances=8, goals=2, goals_conceded=None)}
    assert outcome_of(1, sheet, outfield, outfield).clean_sheet == "his goals conceded aren't known"


def test_chances_if_he_started() -> None:
    """They count only if he did. If that isn't known, neither is whether they count: they're named."""

    def scored_with(started: bool | str) -> SetReport:
        tally = Tally()
        add_outcomes(
            tally,
            Outcome(started, rated=True, scored=True, clean_sheet=True),
            p_start=0.9,
            p_rating=0.95,
            p_scores=0.3,
            p_clean_sheet=None,
        )
        return tally.report()

    assert [chance.chance for chance in scored_with(True).scored] == [
        "Starting",
        "Getting a rating",
        "Scoring, if he started",
    ]
    no = scored_with(False)
    assert [chance.chance for chance in no.scored] == ["Starting", "Getting a rating"]
    assert no.unscored == []
    unknown = scored_with("no official lineup stored")
    assert [chance.chance for chance in unknown.scored] == ["Getting a rating"]
    assert {entry.reason for entry in unknown.unscored} == {
        "Starting: no official lineup stored",
        "Scoring, if he started: no official lineup stored",
    }


def test_the_line_uses_the_model_on_everyone_first() -> None:
    told = SetReport(scored=[scored_chance("Starting", [(0.9, True)])], unscored=[])
    model = SetReport(scored=[scored_chance("Starting", [(0.5, True), (0.5, False)])], unscored=[])
    both = RoundReport(round=11, scored_at=T0, told=told, model=model)
    assert "scored 0.250 over 2 players" in (summary_line(both) or "")
    only_told = both.model_copy(update={"model": SetReport(scored=[], unscored=[])})
    assert "scored 0.010 over 1 players" in (summary_line(only_told) or "")


def test_names_shared_over_a_match_keep_its_clubs_apart() -> None:
    """Both clubs can have an "A. Rossi": sharing the matches of names mustn't make them one player."""
    home = KnownPlayer(player_id=1, name="A. Rossi", club="alfa")
    away = KnownPlayer(player_id=2, name="A. Rossi", club="beta")
    other = KnownPlayer(player_id=3, name="B. Rossi", club="beta")

    def row(club: str, status: str) -> LineupViewRow:
        return LineupViewRow(
            source_url="https://example.org/p",
            captured_at=T0,
            content_sha256="x",
            home="alfa",
            away="beta",
            outlet="Uno",
            club=club,
            name="A. Rossi",
            status=status,
            share=None,
        )

    views = [row("alfa", "bench"), row("beta", "starter")]
    shared: dict[tuple[str, str], KnownPlayer | None] = {}

    def p_start(player: KnownPlayer, names: dict[tuple[str, str], KnownPlayer | None] | None) -> float:
        found = availability(
            player,
            home="alfa",
            away="beta",
            views=views,
            officials=(),
            players=[home, away, other],
            as_of=T0,
            names=names,
        )
        assert found is not None
        return found.p_start

    assert p_start(home, shared) == pytest.approx(p_start(home, None))
    assert p_start(away, shared) == pytest.approx(p_start(away, None))
    assert p_start(away, shared) > p_start(home, shared)
