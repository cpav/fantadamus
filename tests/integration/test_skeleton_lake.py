"""Task 8.3: the skeleton pipeline on a real Parquet lake (R16.2 to R16.5, R16.11)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.core.clock import fixed_clock
from fantadamus.domains.skeleton import bronze, pipeline
from fantadamus.lake.duckdb_store import LakeStore

T0 = dt.datetime(2026, 10, 25, 10, 0, tzinfo=dt.UTC)
ALLOWED = ("example.org",)
ROWS: list[object] = [
    {"player_id": 1, "name": "Giocatore Uno", "club": "Squadra Alfa", "role": "A"},
    {"player_id": 2, "name": "Giocatore Due", "club": "Squadra Alfa", "role": "A"},
]


def _submit(
    store: LakeStore, rows: list[object], url: str = "https://example.org/x", **extra: object
) -> pipeline.SubmitResult:
    submission = pipeline.Submission.model_validate(
        {"rows": rows, "source_url": url, "captured_at": T0} | extra
    )
    return pipeline.submit(
        store, submission, allowed_hosts=ALLOWED, clock=fixed_clock(T0), submitted_by="user-1"
    )


def test_submit_writes_bronze_silver_and_gold(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    result = _submit(store, ROWS, published_at=T0 - dt.timedelta(days=1))
    assert result == pipeline.SubmitResult(accepted=2, rejected=[], bronze_id=result.bronze_id)
    assert result.bronze_id is not None
    assert result.bronze_id.startswith("20261025T100000000000Z-")
    (record,) = store.read_bronze(bronze.SOURCE)
    assert record.envelope.published_at == T0 - dt.timedelta(days=1)
    assert record.envelope.captured_at == T0
    assert record.envelope.payload == ROWS
    silver = store.read_table("silver", "skeleton_players")
    assert [row["player_id"] for row in silver] == [1, 2]
    assert silver[0]["captured_at"] == T0
    summary = pipeline.summary(store)
    assert [(row.club, row.role, row.n_players, row.source_urls) for row in summary] == [
        ("Squadra Alfa", "A", 2, ["https://example.org/x"])
    ]


def test_same_payload_twice_adds_a_file_and_keeps_silver(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    first, second = _submit(store, ROWS), _submit(store, ROWS)
    assert second.bronze_id == f"{first.bronze_id}-1"
    assert len(store.bronze_files(bronze.SOURCE)) == 2
    assert len(store.read_table("silver", "skeleton_players")) == 2


def test_rejections_are_reported_per_row(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    rows: list[object] = [*ROWS, {"player_id": 0, "name": "x", "club": "y", "role": "P"}, "oops", ROWS[0]]
    result = _submit(store, rows)
    assert result.accepted == 1
    assert [(item.index, item.reason) for item in result.rejected] == [
        (0, "player_id 1 appears 2 times in one payload"),
        (2, "player_id: Input should be greater than 0"),
        (3, "row: Input should be a valid dictionary or instance of SkeletonPlayer"),
        (4, "player_id 1 appears 2 times in one payload"),
    ]
    assert [row["player_id"] for row in store.read_table("silver", "skeleton_players")] == [2]


@pytest.mark.parametrize(
    ("url", "rows", "extra", "reason"),
    [
        (
            "https://fantacalcio.it.evil.example/x",
            ROWS,
            {},
            "source_url host fantacalcio.it.evil.example is not on the allowlist",
        ),
        (
            "https://example.org@evil.example/x",
            ROWS,
            {},
            "source_url is not an http(s) URL with a valid host and no user-info",
        ),
        ("https://example.org/x", [], {}, "no rows submitted"),
        (
            "https://example.org/x",
            ROWS,
            {"captured_at": dt.datetime(2026, 10, 25)},
            "captured_at: Input should have timezone info",
        ),
    ],
)
def test_refused_submissions_write_nothing(
    tmp_path: Path, url: str, rows: list[object], extra: dict[str, object], reason: str
) -> None:
    store = LakeStore(tmp_path)
    result = _submit(store, rows, url, **extra)
    assert result == pipeline.SubmitResult(
        accepted=0, rejected=[pipeline.RowRejection(index=None, reason=reason)], bronze_id=None
    )
    assert not any(tmp_path.rglob("*"))


def test_empty_lake_reads_nothing(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    assert store.read_bronze(bronze.SOURCE) == []
    assert pipeline.summary(store) == []
