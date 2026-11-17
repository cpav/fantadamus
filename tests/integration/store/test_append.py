"""mvp-store task 2.2: a store adds its rows to their month's file, and the table is then exactly the one a
rebuild gives; bronze is only ever added to (design C3; R1.1, R1.3). P1 took over from
`tests/property/test_lake.py::test_bronze_append_only`."""

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fantadamus.contracts.xy.fixtures import FixturesPayload, OtherFixturesPayload
from fantadamus.domains import facts
from fantadamus.domains.fixtures.silver import FIXTURES, OTHER_FIXTURES
from fantadamus.lake.duckdb_store import STORING, Incoming, LakeStore
from tests.store_lake import FOUR, URL, Told, bronze_bytes, fixtures, store_one, store_page, table
from tests.xy_harness import CLUBS

T0 = dt.datetime(2026, 10, 31, 22, 0, tzinfo=dt.UTC)
OCTOBER = dt.datetime(2026, 10, 28, 9, 0, tzinfo=dt.UTC)
EARLY_NOVEMBER = dt.datetime(2026, 11, 2, 9, 0, tzinfo=dt.UTC)
LATE_NOVEMBER = dt.datetime(2026, 11, 20, 9, 0, tzinfo=dt.UTC)

payloads = st.builds(fixtures, st.integers(1, 38), st.permutations(FOUR), st.integers(24, 96))
Step = tuple[list[FixturesPayload], dt.datetime, dt.datetime, bool, str]
steps = st.tuples(
    st.lists(payloads, min_size=1, max_size=2),
    # Read on either side of midnight on 1 November, so a history has one month or two.
    st.integers(0, 4).map(lambda hours: T0 + dt.timedelta(hours=hours)),
    # Received at one of three instants: file names tie, and a clock steps back.
    st.integers(0, 2).map(lambda seconds: T0 + dt.timedelta(hours=5, seconds=seconds)),
    st.booleans(),  # a page's payloads at once, or one payload
    st.sampled_from([URL, "https://example.org/other"]),
)


def store_step(store: LakeStore, told: Told, step: Step) -> list[str]:
    """Store a step, tell `told` what went in, and return its bronze IDs."""
    payloads, captured_at, received_at, page, url = step
    if page:
        stored = store_page(store, payloads, captured_at, received_at, url=url)
        assert not stored.rejections
        ids = [receipt.bronze_id for receipt in stored.receipts]
    else:
        payloads = payloads[:1]
        ids = [store_one(store, payloads[0], captured_at, received_at, url=url).bronze_id]
    for bronze_id, payload in zip(ids, payloads, strict=True):
        told.add(bronze_id, payload, captured_at, url)
    return ids


# Each example writes Parquet files, whose timing varies with the disk: no per-example deadline. The example
# count still comes from the profile. The table is looked at once, after the last store: a history's every
# beginning is a history too, so nothing a store could break goes unseen, and an example costs a read less
# for each store.
@settings(deadline=None)
@given(history=st.lists(steps, min_size=1, max_size=3))
def test_p1_appending_gives_what_a_rebuild_gives(history: list[Step]) -> None:
    with tempfile.TemporaryDirectory() as root:
        store, told = LakeStore(Path(root)), Told()
        kept: dict[str, bytes] = {}
        for step in history:
            ids = store_step(store, told, step)
            now = bronze_bytes(store)
            assert {name: now[name] for name in kept} == kept  # no bronze file has changed
            assert sorted(Path(name).stem for name in set(now) - set(kept)) == sorted(ids)  # one file each
            kept = now
        assert table(store) == told.table()  # the rows a rebuild gives, in its order
        assert not (store.root / "silver" / "fixtures" / STORING).exists()


def test_a_rebuild_gives_what_was_told(tmp_path: Path) -> None:
    """What P1 compares with is what a rebuild gives: two months, a tie between file names, a clock set back
    and the same content twice."""
    store, told = LakeStore(tmp_path), Told()
    late, early = T0 + dt.timedelta(hours=5, seconds=2), T0 + dt.timedelta(hours=5)
    history: list[Step] = [
        ([fixtures(9), fixtures(10, FOUR[::-1])], T0 + dt.timedelta(hours=3), late, True, URL),
        ([fixtures(11)], T0, early, False, URL),  # read in October, and received before the first
        ([fixtures(9), fixtures(9)], T0 + dt.timedelta(hours=1), late, True, "https://example.org/other"),
        ([fixtures(12)], T0 + dt.timedelta(hours=4), late, False, URL),
    ]
    for step in history:
        store_step(store, told, step)
        assert table(store) == told.table()
    kept = bronze_bytes(store)
    assert len(kept) == 6
    again = [name for name in kept if name.endswith(("-1.parquet", "-2.parquet"))]
    assert len(again) == 2  # the same content at the same instant gets a number
    facts.rebuild(store, FIXTURES, CLUBS)
    rows, description = table(store)
    assert (rows, description) == told.table()
    assert [row["round"] for row in rows[:4]] == [11, 11, 9, 9]  # October's, in their files' order
    assert description is not None
    assert str(description["last_bronze"]).startswith(f"{late:%Y%m%dT%H%M%S%fZ}-")
    assert bronze_bytes(store) == kept


def test_a_store_in_step_adds_its_rows_and_rebuilds_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, told = LakeStore(tmp_path), Told()
    first = store_one(store, fixtures(9), OCTOBER)  # the first store writes the table
    told.add(first.bronze_id, fixtures(9), OCTOBER)
    written = store.description(FIXTURES.table)
    assert written is not None
    october = tmp_path / "silver" / "fixtures" / written.files["2026-10"]
    untouched = october.stat()

    def rebuilt(*args: object, **options: object) -> int:
        raise AssertionError("a table in step was rebuilt")

    monkeypatch.setattr(store, "replace_rows", rebuilt)
    for round, when in ((10, EARLY_NOVEMBER), (11, LATE_NOVEMBER)):
        receipt = store_one(store, fixtures(round), when)
        told.add(receipt.bronze_id, fixtures(round), when)
        assert receipt.rows == 2
    assert table(store) == told.table()
    assert [row["round"] for row in store.read_rows(FIXTURES.table)] == [9, 9, 10, 10, 11, 11]
    found = october.stat()
    assert (found.st_ino, found.st_mtime_ns) == (untouched.st_ino, untouched.st_mtime_ns)  # only November's
    now = store.description(FIXTURES.table)
    assert now is not None
    assert now.files["2026-10"] == written.files["2026-10"]
    assert sorted(path.name for path in october.parent.iterdir()) == sorted(
        [*now.files.values(), "_table.json"]
    )


def _other(*matches: tuple[str, str]) -> OtherFixturesPayload:
    kickoff = dt.datetime(2026, 11, 4, 20, 0, tzinfo=dt.UTC)
    return OtherFixturesPayload.model_validate(
        {
            "competition": "Champions League",
            "matches": [{"home": home, "away": away, "kickoff_at": kickoff} for home, away in matches],
        }
    )


def test_a_payload_without_rows_keeps_its_bronze(tmp_path: Path) -> None:
    """A competition's page with no Serie A club gives no row: its bronze file is kept, nothing is added."""
    store, told = LakeStore(tmp_path), Told(OTHER_FIXTURES)
    nobody = store_one(store, _other(("Omega", "Sigma")), OCTOBER, domain=OTHER_FIXTURES)
    told.add(nobody.bronze_id, _other(("Omega", "Sigma")), OCTOBER)
    assert nobody.rows == 0
    assert table(store, OTHER_FIXTURES) == told.table()
    assert table(store, OTHER_FIXTURES)[0] == []
    ours = store_one(store, _other(("Alfa", "Omega")), EARLY_NOVEMBER, domain=OTHER_FIXTURES)
    told.add(ours.bronze_id, _other(("Alfa", "Omega")), EARLY_NOVEMBER)
    before = table(store, OTHER_FIXTURES)
    again = store_one(store, _other(("Sigma", "Omega")), LATE_NOVEMBER, domain=OTHER_FIXTURES)
    told.add(again.bronze_id, _other(("Sigma", "Omega")), LATE_NOVEMBER)
    assert again.rows == 0
    assert len(store.bronze_files(OTHER_FIXTURES.source)) == 3
    assert table(store, OTHER_FIXTURES) == before == told.table()  # the table didn't change
    assert not (tmp_path / "silver" / "other_fixtures" / STORING).exists()
    last = store_one(store, _other(("Omega", "Beta")), LATE_NOVEMBER, domain=OTHER_FIXTURES)
    told.add(last.bronze_id, _other(("Omega", "Beta")), LATE_NOVEMBER)
    assert table(store, OTHER_FIXTURES) == told.table()  # and it is still in step


def test_rows_of_two_months_go_to_two_files(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    store_one(store, fixtures(9), OCTOBER)
    store_one(store, fixtures(10), EARLY_NOVEMBER)
    written = store.description(FIXTURES.table)
    assert written is not None
    rows = [FIXTURES.row.model_validate(row) for row in store.read_rows(FIXTURES.table)]
    late = rows[0].model_copy(update={"round": 12})
    later = rows[2].model_copy(update={"round": 13})
    bronze_id = "20261201T090000000000Z-0123456789ab"
    added = store.append_rows(
        FIXTURES.table,
        [
            Incoming(bronze_id, "2026-10", late.model_dump_json()),
            Incoming(bronze_id, "2026-11", later.model_dump_json()),
        ],
        written,
    )
    assert added == 2
    assert [row["round"] for row in store.read_rows(FIXTURES.table)] == [9, 9, 12, 10, 10, 13]
    described = store.description(FIXTURES.table)
    assert described is not None
    assert described.model_copy(update={"files": written.files}) == written.model_copy(
        update={"last_bronze": bronze_id}
    )
    assert list(described.files) == ["2026-10", "2026-11"]
    assert set(described.files.values()).isdisjoint(written.files.values())  # both months in new files
