"""Properties P1, P4, P5 and P6: the skeleton's bronze → silver → gold flow (R16.3 to R16.6)."""

from __future__ import annotations

import datetime as dt
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from fantadamus.domains.skeleton import bronze, gold, pipeline, silver
from fantadamus.lake.duckdb_store import BronzeRecord, LakeStore

ALLOWED = ("example.org",)
T0 = dt.datetime(2026, 10, 25, 10, 0, tzinfo=dt.UTC)

valid_rows = st.fixed_dictionaries(
    {
        "player_id": st.integers(1, 30),
        "name": st.text(min_size=1, max_size=60),
        "club": st.sampled_from(["Squadra Alfa", "Squadra Beta", "Squadra Gamma"]),
        "role": st.sampled_from(["P", "D", "C", "A"]),
    }
)
invalid_rows = st.one_of(
    valid_rows.map(lambda row: row | {"player_id": 0}),
    valid_rows.map(lambda row: row | {"role": "X"}),
    valid_rows.map(lambda row: row | {"name": ""}),
    valid_rows.map(lambda row: {key: value for key, value in row.items() if key != "club"}),
    st.integers(),
    st.text(max_size=5),
)
submissions = st.lists(
    st.tuples(
        st.lists(valid_rows | invalid_rows, min_size=1, max_size=5),
        st.sampled_from(["https://example.org/a", "https://www.example.org/b"]),
        st.integers(0, 3).map(lambda hours: T0 - dt.timedelta(hours=hours)),
    ),
    min_size=1,
    max_size=4,
)


# These properties write Parquet files, whose timing varies with the disk: no per-example deadline.
# The example count still comes from the profile.
io_bound = settings(deadline=None)


@contextmanager
def _store() -> Iterator[LakeStore]:
    with tempfile.TemporaryDirectory() as root:
        yield LakeStore(Path(root))


def _record(index: int, rows: list[Any], source_url: str, captured_at: dt.datetime) -> BronzeRecord:
    envelope = bronze.build_envelope(
        rows,
        source_url=source_url,
        captured_at=captured_at,
        published_at=None,
        received_at=T0 + dt.timedelta(minutes=index),
        submitted_by="user-1",
    )
    return BronzeRecord(bronze_id=f"b{index}", envelope=envelope)


@io_bound
@given(batch=submissions, repeat=st.booleans())
def test_bronze_append_only(batch: list[tuple[list[Any], str, dt.datetime]], repeat: bool) -> None:
    with _store() as store:
        written: dict[Path, bytes] = {}
        for rows, source_url, captured_at in batch + (batch[:1] if repeat else []):
            # Every record gets the same received_at, so file names collide and must still never overwrite.
            envelope = _record(0, rows, source_url, captured_at).envelope
            bronze_id = store.append_bronze(envelope)
            files = store.bronze_files(bronze.SOURCE)
            assert {path: path.read_bytes() for path in written} == written
            assert len(files) == len(written) + 1
            assert bronze_id in {path.stem for path in files}
            written.update({path: path.read_bytes() for path in files})
        pipeline.refresh(store)  # rebuilding silver and gold leaves bronze untouched
        assert {path: path.read_bytes() for path in written} == written


@io_bound
@given(rows=st.lists(valid_rows, min_size=1, max_size=8, unique_by=lambda row: row["player_id"]))
def test_valid_rows_roundtrip(rows: list[dict[str, Any]]) -> None:
    with _store() as store:
        store.append_bronze(_record(0, rows, "https://example.org/a", T0).envelope)
        promoted = silver.promote(store.read_bronze(bronze.SOURCE))
    fields = ("player_id", "name", "club", "role")
    got = sorted((tuple(getattr(row, name) for name in fields) for row in promoted.rows), key=lambda t: t[0])
    assert got == sorted((tuple(row[name] for name in fields) for row in rows), key=lambda t: t[0])
    assert promoted.rejections == []


@given(
    rows=st.lists(
        st.tuples(st.booleans(), valid_rows, invalid_rows),
        min_size=1,
        max_size=8,
        unique_by=lambda t: t[1]["player_id"],
    )
)
def test_invalid_rows_excluded(rows: list[tuple[bool, dict[str, Any], Any]]) -> None:
    payload = [good if is_valid else bad for is_valid, good, bad in rows]
    promoted = silver.promote([_record(0, payload, "https://example.org/a", T0)])
    valid_ids = {good["player_id"] for is_valid, good, _ in rows if is_valid}
    assert {row.player_id for row in promoted.rows} == valid_ids
    invalid = {index for index, (is_valid, _, _) in enumerate(rows) if not is_valid}
    assert {(rejection.bronze_id, rejection.index) for rejection in promoted.rejections} == {
        ("b0", index) for index in invalid
    }
    assert all(rejection.reason for rejection in promoted.rejections)


@io_bound
@given(batch=submissions, order=st.randoms(use_true_random=False))
def test_gold_order_invariant(batch: list[tuple[list[Any], str, dt.datetime]], order: Any) -> None:
    shuffled = list(batch)
    order.shuffle(shuffled)
    first = gold.role_counts(silver.promote([_record(i, *item) for i, item in enumerate(batch)]).rows)
    second = gold.role_counts(silver.promote([_record(i, *item) for i, item in enumerate(shuffled)]).rows)
    assert first == second
