"""Calibration sets, kept and read back (mvp-recalibrate design C1; R1.1 to R1.3)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from fantadamus.domains.calibration import CalibrationSet, Outcome, RoundReport, SetReport, SetRow, Tally
from fantadamus.lake.calibration_store import CalibrationStore

SCORED_AT = dt.datetime(2026, 11, 1, 5, 0, tzinfo=dt.UTC)
NO_SHEET = "no official lineup stored"


def _row(player_id: int, *, home: str = "Alfa", away: str = "Beta", club: str = "Alfa") -> SetRow:
    return SetRow(
        round=10,
        home=home,
        away=away,
        club=club,
        player_id=player_id,
        role="D",
        consensus=0.4,
        p_start=0.4,
        p_rating=0.7,
        p_scores=0.05,
        p_scores_cameo=0.01,
        p_clean_sheet=None,
        outcome=Outcome(started=False, rated=True, scored=False, clean_sheet=False),
    )


def _report(round: int) -> RoundReport:
    empty = SetReport(scored=[], unscored=[])
    return RoundReport(round=round, scored_at=SCORED_AT, told=empty, model=empty)


def test_rows_by_match_and_player() -> None:
    tally = Tally()
    for row in (
        _row(3, home="Gamma", away="Delta", club="Delta"),
        _row(2, club="Beta"),
        _row(9),
        _row(1, home="Gamma", away="Delta", club="Gamma"),
        _row(4),
    ):
        tally.keep(row)
    assert [row.player_id for row in tally.rows()] == [2, 4, 9, 1, 3]
    assert tally.report() == SetReport(scored=[], unscored=[])  # keeping a row scores nothing on its own


def test_a_row_keeps_what_isnt_known() -> None:
    unknown = _row(1).model_copy(
        update={"role": None, "p_rating": None, "outcome": Outcome(True, NO_SHEET, NO_SHEET, NO_SHEET)}
    )
    again = SetRow.model_validate_json(unknown.model_dump_json())
    assert again == unknown
    assert again.outcome.started is True
    assert again.outcome.rated == NO_SHEET


def test_kept_beside_the_report(tmp_path: Path) -> None:
    store = CalibrationStore(tmp_path)
    assert store.calibration_set(10) is None
    kept = CalibrationSet(round=10, scored_at=SCORED_AT, rows=[_row(1), _row(2)])
    store.keep_set(kept)
    store.set(_report(10))
    assert sorted(path.name for path in tmp_path.iterdir()) == ["round-10.json", "round-10.set.json"]
    assert store.calibration_set(10) == kept
    assert store.calibration_set(11) is None


def test_the_latest_report_isnt_a_set(tmp_path: Path) -> None:
    store = CalibrationStore(tmp_path)
    store.set(_report(10))
    store.keep_set(CalibrationSet(round=11, scored_at=SCORED_AT, rows=[]))  # a set without its report
    latest = store.latest()
    assert latest is not None
    assert latest.round == 10
    assert CalibrationStore(tmp_path / "none").latest() is None
