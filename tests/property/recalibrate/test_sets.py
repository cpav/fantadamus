"""P4: a round's calibration set is the same whatever order its rows come in, and reads back as it was kept
(mvp-recalibrate design C1; R1.3)."""

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.calibration import CalibrationSet, Outcome, SetRow, Tally
from fantadamus.lake.calibration_store import CalibrationStore

SCORED_AT = dt.datetime(2026, 11, 1, 5, 0, tzinfo=dt.UTC)
_CHANCE = st.floats(min_value=0.0, max_value=1.0)
_RESULT = st.one_of(
    st.booleans(), st.sampled_from(["no official lineup stored", "no statistics read after the round"])
)
_CLUBS = ("Alfa", "Beta", "Gamma", "Delta")


@st.composite
def _rows(draw: st.DrawFn) -> list[SetRow]:
    ids = draw(st.lists(st.integers(min_value=1, max_value=9999), unique=True, max_size=30))
    found = []
    for player_id in ids:
        home, away = draw(st.sampled_from([("Alfa", "Beta"), ("Gamma", "Delta")]))
        found.append(
            SetRow(
                round=10,
                home=home,
                away=away,
                club=draw(st.sampled_from((home, away))),
                player_id=player_id,
                role=draw(st.sampled_from(["P", "D", "C", "A", None])),
                consensus=draw(_CHANCE),
                p_start=draw(_CHANCE),
                p_rating=draw(st.none() | _CHANCE),
                p_scores=draw(st.none() | _CHANCE),
                p_scores_cameo=draw(st.none() | _CHANCE),
                p_clean_sheet=draw(st.none() | _CHANCE),
                outcome=Outcome(draw(_RESULT), draw(_RESULT), draw(_RESULT), draw(_RESULT)),
            )
        )
    return found


def _kept(rows: list[SetRow]) -> list[SetRow]:
    tally = Tally()
    for row in rows:
        tally.keep(row)
    return tally.rows()


@given(rows=_rows(), data=st.data())
def test_p4_same_set(rows: list[SetRow], data: st.DataObject) -> None:
    kept = _kept(rows)
    assert _kept(data.draw(st.permutations(rows))) == kept
    assert sorted(kept, key=lambda row: row.player_id) == sorted(rows, key=lambda row: row.player_id)
    with tempfile.TemporaryDirectory() as folder:
        store = CalibrationStore(Path(folder))
        store.keep_set(CalibrationSet(round=10, scored_at=SCORED_AT, rows=kept))
        again = store.calibration_set(10)
    assert again is not None
    assert again.rows == kept
