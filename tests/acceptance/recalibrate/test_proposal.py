"""AT-8: the proposal lists each value with today's and the fitted one, its evidence and sample, and its
held-out effect, the season's rates apart and what waits; the command changes nothing (mvp-recalibrate R8.1;
design C8)."""

from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

import pytest

from fantadamus.contracts.types import Role
from fantadamus.domains.calibration import CalibrationSet, Outcome, SetRow
from fantadamus.domains.recalibration import (
    propose,
    reliability_gap,
    render_proposal,
    start_pairs,
    waiting,
)
from fantadamus.domains.season.silver import PlayerSeasonRow
from fantadamus.engine import constants
from fantadamus.engine.recalibrate import fit_start_map
from fantadamus.lake.calibration_store import CalibrationStore
from tests.cards_data import source, table_row

MADE = dt.datetime(2026, 11, 12, 10, 0, tzinfo=dt.UTC)


def _row(
    round: int, match: int, player_id: int, *, consensus: float, started: bool, **more: object
) -> SetRow:
    fields: dict[str, object] = {
        "round": round,
        "home": f"club{match}",
        "away": f"other{match}",
        "club": f"club{match}",
        "player_id": player_id,
        "role": "D",
        "consensus": consensus,
        "p_start": consensus,
        "p_rating": None,
        "p_scores": None,
        "p_scores_cameo": None,
        "p_clean_sheet": None,
        "priced_cameo": False,
        "outcome": Outcome(started, False, False, False),
    }
    return SetRow.model_validate(fields | more)


def _round(round: int) -> list[SetRow]:
    """200 players at 25%, of whom 10 started, and 200 at 95%, of whom 190 did; and 30 benched defenders, 6
    rated."""
    rows = [_row(round, index % 2, index, consensus=0.25, started=index < 10) for index in range(200)]
    rows += [
        _row(round, index % 2, 1000 + index, consensus=0.95, started=index < 190) for index in range(200)
    ]
    rows += [
        _row(
            round,
            index % 2,
            2000 + index,
            consensus=0.2,
            started=False,
            p_rating=0.6,
            outcome=Outcome(False, index < 6, False, False),
        )
        for index in range(30)
    ]
    return rows


def _player(player_id: int, role: Role, **counts: int) -> PlayerSeasonRow:
    return PlayerSeasonRow(
        **source("https://example.org/statistiche").model_dump(),
        player_id=player_id,
        name=f"Player {player_id}",
        club="alfa",
        role=role,
        mantra_role=None,
        appearances=counts.get("appearances", 400),
        rated_appearances=counts.get("rated", 400),
        average_rating=6.0,
        goals=0,
        assists=0,
        yellow_cards=counts.get("yellow", 0),
        penalties_scored=counts.get("scored", 0),
        penalties_taken=counts.get("taken", 0),
        penalties_saved=counts.get("saved", 0),
        red_cards=counts.get("red", 0),
    )


READ = [
    _player(1, "P", saved=3, red=1),
    _player(2, "D", yellow=80, red=2),
    _player(3, "C", yellow=60),
    _player(4, "A", yellow=20, taken=40, scored=30),
]
TABLE = [table_row(club, 11, 15, 15) for club in ("alfa", "beta", "gamma", "delta")]


def test_at8_the_proposal() -> None:
    sets = {round: _round(round) for round in (10, 11)}
    proposal = propose(sets, READ, TABLE, made_at=MADE, missing=[9])
    assert (proposal.rounds, proposal.missing_rounds) == ([10, 11], [9])
    assert proposal.read_at == READ[0].captured_at
    assert proposal.table_at == TABLE[0].captured_at

    start, share = proposal.fitted  # no forward: CAMEO_RATED isn't counted, so it isn't fitted
    assert start.name == "START_MAP"
    assert start.old == constants.START_MAP
    rows = [row for rows in sets.values() for row in rows]
    assert start.new == fit_start_map(start_pairs(rows))
    assert start.check.proposed
    assert [fold.held_out for fold in start.check.folds] == ["round 10", "round 11"]
    assert (share.name, share.old, share.check.proposed) == ("CAMEO_SHARE", constants.CAMEO_SHARE, False)
    assert share.new == pytest.approx(0.2)
    assert share.rate is not None
    assert share.rate.count == 60
    assert share.check.why == "below its minimum sample: 60 of 200"

    season = {value.name: value for value in proposal.season}
    assert list(season) == [
        "PENALTY_RATE",
        "PENALTY_CONVERSION",
        "PENALTY_SAVED_SHARE",
        "YELLOW_PRIOR",
        'RED_RATE["P"]',
        'RED_RATE["D"]',
        'RED_RATE["C"]',
        'RED_RATE["A"]',
    ]
    assert (season["PENALTY_RATE"].old, season["PENALTY_RATE"].new) == (constants.PENALTY_RATE, 40 / 44)
    assert season["PENALTY_RATE"].check.proposed
    assert season["PENALTY_SAVED_SHARE"].check.why == "below its minimum sample: 10 of 30"
    assert season['RED_RATE["D"]'].old == constants.RED_RATE["D"]
    assert proposal.not_counted == ["CAMEO_RATED: no attacker who didn't start and could have come on"]
    assert proposal.waits == waiting(rows)

    bare = propose(sets, [], [], made_at=MADE)  # no statistics read, no table
    assert (bare.read_at, bare.season, bare.missing_rounds) == (None, [], [])
    assert bare.not_counted == [
        "CAMEO_RATED: no attacker who didn't start and could have come on",
        "PENALTY_RATE: no team matches in the table",
        "PENALTY_CONVERSION: no penalty taken",
        "PENALTY_SAVED_SHARE: no penalty missed",
        "YELLOW_PRIOR: no outfield appearance",
        'RED_RATE["P"]: no rated game',
        'RED_RATE["D"]: no rated game',
        'RED_RATE["C"]: no rated game',
        'RED_RATE["A"]: no rated game',
    ]


def test_at8_the_proposal_in_words() -> None:
    sets = {round: _round(round) for round in (10, 11)}
    proposal = propose(sets, READ, TABLE, made_at=MADE, missing=[9])
    lines = render_proposal(proposal).splitlines()
    start, share = proposal.fitted
    rate = share.rate
    assert rate is not None
    fold = start.check.folds[0]
    assert lines[:3] == [
        "Recalibration proposal, 2026-11-12 10:00 UTC, on rounds 10 and 11",
        "Round 9 has no calibration set stored: fitted on the rest.",
        "Nothing changes until the owner approves a value, as a pull request to engine/constants.py.",
    ]
    assert "Fitted on the rounds" in lines
    assert "START_MAP: proposed: it improves the Brier score wherever it wasn't fitted" in lines
    assert "  today: the identity" in lines
    assert not isinstance(start.new, float)
    knots = ", ".join(f"{raw:.0%} to {value:.1%}" for raw, value in start.new[1:-1])
    assert f"  fitted: {knots}" in lines
    assert "  evidence: 860 players whose start is known (its minimum: 300)" in lines
    assert (
        f"  held out round 10: Brier {fold.before.brier:.3f} to {fold.after.brier:.3f}, "
        f"reliability gap {reliability_gap(fold.before):.3f} to {reliability_gap(fold.after):.3f}"
    ) in lines
    assert "CAMEO_SHARE: not proposed: below its minimum sample: 60 of 200" in lines
    assert (
        f"  today: 0.500; fitted: {rate.value:.3f} over 60, 90% between {rate.low:.3f} and {rate.high:.3f}"
        in lines
    )
    assert "  evidence: 60 players who didn't start and could have come on (its minimum: 200)" in lines
    assert "The season's own rates: counts, not forecasts" in lines
    read = f"{READ[0].captured_at:%Y-%m-%d %H:%M}"
    assert f"Counted from the statistics read of {read} UTC and the table of {read} UTC." in lines
    assert "PENALTY_RATE: proposed: counted, not forecast: no held-out check" in lines
    assert "Not counted" in lines
    assert "  CAMEO_RATED: no attacker who didn't start and could have come on" in lines
    assert "What waits" in lines
    for heading in (
        "Fitted on the rounds",
        "The season's own rates: counts, not forecasts",
        "Not counted",
        "What waits",
    ):
        assert lines[lines.index(heading) - 1] == ""  # each section after a blank line
    penalties = next(value for value in proposal.season if value.name == "PENALTY_RATE").rate
    assert penalties is not None
    assert (
        f"  today: 0.150; fitted: {40 / 44:.3f} over 44, "
        f"90% between {penalties.low:.3f} and {penalties.high:.3f}"
    ) in lines
    assert "  evidence: 40 penalties taken (its minimum: 30)" in lines  # the penalties, over 44 team matches
    assert "  evidence: 400 rated games (its minimum: 300)" in lines  # a red card's rate
    one = render_proposal(propose({11: _round(11)}, [], [], made_at=MADE))
    assert one.splitlines()[0].endswith("on round 11")
    assert "No statistics read is stored." in one.splitlines()
    alone = render_proposal(propose({11: _round(11)}, READ, [], made_at=MADE)).splitlines()
    assert f"Counted from the statistics read of {read} UTC, without a table." in alone
    three = render_proposal(propose({round: _round(round) for round in (9, 10, 11)}, [], [], made_at=MADE))
    assert three.splitlines()[0].endswith("on rounds 9, 10 and 11")
    assert any(
        line.startswith("  ROLE_PRIORS, SHARE_WEIGHT") and line.endswith("0 of the 500 it needs")
        for line in lines
    )
    assert any(
        line.startswith("  VOTE_BASELINE") and line.endswith("come with the new sources") for line in lines
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_at8_changes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The command reads the stored sets and facts, prints the proposal and keeps it privately; it reads no
    page, and the constants stay as they are."""
    from fantadamus.cli import __main__ as cli

    store = CalibrationStore(tmp_path / "calibration")
    for round in (10, 11):
        store.keep_set(CalibrationSet(round=round, scored_at=MADE, rows=_round(round)))
    stored = {path.name: _digest(path) for path in store.root.iterdir()}
    constants_file = Path(constants.__file__)
    before = _digest(constants_file)

    def no_page(*_: object) -> None:
        raise AssertionError("the proposal reads no page")

    monkeypatch.setattr(cli, "_collector", no_page)
    assert cli.main(["recalibrate", "--lake", str(tmp_path / "lake")]) == 0
    printed = capsys.readouterr().out
    assert printed.startswith("Recalibration proposal")
    assert "on rounds 10 and 11" in printed.splitlines()[0]
    assert _digest(constants_file) == before
    assert constants.START_MAP == ((0.0, 0.0), (1.0, 1.0))
    after = {path.name: _digest(path) for path in store.root.iterdir()}
    assert {name: digest for name, digest in after.items() if name != "proposal.json"} == stored
    kept = store.proposal()
    assert kept is not None
    assert kept.rounds == [10, 11]

    assert cli.main(["recalibrate", "--rounds", "10", "12", "--lake", str(tmp_path / "lake")]) == 0
    assert "Round 12 has no calibration set stored: fitted on the rest." in capsys.readouterr().out
    empty = tmp_path / "empty"
    assert cli.main(["recalibrate", "--lake", str(empty / "lake")]) == 1
    assert "No calibration set is stored" in capsys.readouterr().out
