"""Helpers for mvp-store's tests: fixtures stored in a lake, the table a rebuild must give, worked out here
from what was stored, and a table put back in the layout it had before the slice."""

from __future__ import annotations

import datetime as dt
import shutil
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fantadamus.contracts.xy.fixtures import FixturesPayload
from fantadamus.core.clock import fixed_clock
from fantadamus.core.files import temporary_beside
from fantadamus.domains import facts
from fantadamus.domains.facts import Domain, Receipt, Source, Stored, Submission
from fantadamus.domains.fixtures.silver import FIXTURES
from fantadamus.lake import duckdb_store
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.lake.months import Description, month_of
from tests.xy_harness import CLUBS

URL = "https://example.org/calendar"
HOSTS = ["example.org"]
FOUR = ("Alfa", "Beta", "Gamma", "Delta")


def fixtures(round: int, clubs: Sequence[str] = FOUR, hours: int = 24) -> FixturesPayload:
    """A round of two matches between the four clubs, in the order given."""
    kickoff = dt.datetime(2026, 12, 1, 15, 0, tzinfo=dt.UTC) + dt.timedelta(days=7 * round, hours=hours)
    return FixturesPayload.model_validate(
        {
            "round": round,
            "matches": [
                {"home": clubs[0], "away": clubs[1], "kickoff_at": kickoff},
                {"home": clubs[2], "away": clubs[3], "kickoff_at": kickoff + dt.timedelta(hours=3)},
            ],
        }
    )


def store_one(
    store: LakeStore,
    payload: Any,
    captured_at: dt.datetime,
    received_at: dt.datetime | None = None,
    *,
    domain: Domain[Any, Any] = FIXTURES,
    url: str = URL,
) -> Receipt:
    return facts.submit(
        store,
        domain,
        payload,
        source_url=url,
        captured_at=captured_at,
        published_at=None,
        allowed_hosts=HOSTS,
        clock=fixed_clock(received_at or captured_at),
        submitted_by="user-1",
        clubs=CLUBS,
    )


def store_page(
    store: LakeStore,
    payloads: Iterable[Any],
    captured_at: dt.datetime,
    received_at: dt.datetime | None = None,
    *,
    domain: Domain[Any, Any] = FIXTURES,
    url: str = URL,
) -> Stored:
    return facts.submit_many(
        store,
        domain,
        [Submission(payload) for payload in payloads],
        source_url=url,
        captured_at=captured_at,
        allowed_hosts=HOSTS,
        clock=fixed_clock(received_at or captured_at),
        submitted_by="user-1",
        clubs=CLUBS,
    )


def bronze_bytes(store: LakeStore) -> dict[str, bytes]:
    """Every bronze file's bytes, by its place in the lake."""
    files = sorted((store.root / "bronze").rglob("*.parquet"))
    return {str(path.relative_to(store.root)): path.read_bytes() for path in files}


Table = tuple[list[dict[str, object]], dict[str, object] | None]


def said(written: Description | None) -> dict[str, object] | None:
    """What `_table.json` says, with the months it has files for in place of their names: they're new each
    time a month is written."""
    if written is None:
        return None
    return {**written.model_dump(exclude={"files"}), "months": sorted(written.files)}


def table(store: LakeStore, domain: Domain[Any, Any] = FIXTURES) -> Table:
    """A silver table as it stands: its rows in stored order, and what `_table.json` says."""
    return store.read_rows(domain.table), said(store.description(domain.table))


@dataclass
class Told:
    """What a test stored, by bronze record: enough to say which table a rebuild must give, without reading
    the lake."""

    domain: Domain[Any, Any] = FIXTURES
    records: dict[str, tuple[Any, Source]] | None = None

    def add(self, bronze_id: str, payload: Any, captured_at: dt.datetime, url: str = URL) -> None:
        source = Source(source_url=url, captured_at=captured_at, content_sha256=facts.payload_hash(payload))
        self.records = {**(self.records or {}), bronze_id: (payload, source)}

    def table(self) -> Table:
        """The months oldest first, and in each the rows of the bronze records as their files sort."""
        by_month: dict[str, list[dict[str, object]]] = {}
        last = None
        for bronze_id in sorted(self.records or {}, key=lambda found: f"{found}.parquet"):
            payload, source = (self.records or {})[bronze_id]
            for row in self.domain.to_rows(payload, CLUBS, source):
                by_month.setdefault(month_of(row.captured_at), []).append(row.model_dump())
                last = bronze_id
        rows = [row for month in sorted(by_month) for row in by_month[month]]
        columns = list(self.domain.table.columns.items())
        written = Description(
            columns=columns,
            rows_version=self.domain.rows_version,
            last_bronze=last,
            files=dict.fromkeys(by_month, ""),
        )
        return rows, said(written)


def _value(row: Any, name: str) -> Any:
    return row[name] if isinstance(row, dict) else getattr(row, name)


def newest_submissions[R](
    rows: Sequence[R], keys: Sequence[str], since: dt.datetime | None = None, until: dt.datetime | None = None
) -> list[R]:
    """What a reduced read keeps, worked out here: within the window, each page's newest submission for each
    value of `keys`, by its time and then its content hash, as `latest_by` orders them; in the order given."""

    def group(row: R) -> tuple[Any, ...]:
        return (_value(row, "source_url"), *(_value(row, key) for key in keys))

    def mark(row: R) -> tuple[dt.datetime, str]:
        return _value(row, "captured_at"), _value(row, "content_sha256")

    window = [
        row
        for row in rows
        if (since is None or _value(row, "captured_at") >= since)
        and (until is None or _value(row, "captured_at") <= until)
    ]
    newest: dict[tuple[Any, ...], tuple[dt.datetime, str]] = {}
    for row in window:
        newest[group(row)] = max(newest.get(group(row), mark(row)), mark(row))
    return [row for row in window if mark(row) == newest[group(row)]]


def told_by_bronze(store: LakeStore, domain: Domain[Any, Any] = FIXTURES) -> Told:
    """What the lake's bronze records say was stored, whoever stored them and however far they got."""
    told = Told(domain)
    for record in store.read_bronze(domain.source):
        envelope = record.envelope
        payload = domain.contract.model_validate(envelope.payload)
        told.add(record.bronze_id, payload, envelope.captured_at, envelope.source_url)
    return told


def rebuilt_elsewhere(store: LakeStore, domain: Domain[Any, Any] = FIXTURES) -> Table:
    """The table a rebuild gives, in another lake that holds a copy of this one's bronze."""
    with tempfile.TemporaryDirectory() as folder:
        other = LakeStore(Path(folder))
        if (store.root / "bronze").is_dir():
            shutil.copytree(store.root / "bronze", other.root / "bronze")
        facts.rebuild(other, domain, CLUBS)
        return table(other, domain)


def to_earlier_layout(store: LakeStore, domain: Domain[Any, Any]) -> None:
    """Put a silver table back as it was stored before mvp-store: one Parquet file, and no folder."""
    rows = [domain.row.model_validate(row) for row in store.read_rows(domain.table)]
    folder = store.root / "silver" / domain.table.name
    target = store.root / "silver" / f"{domain.table.name}.parquet"
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = temporary_beside(target)
    lines.write_text("".join(row.model_dump_json() + "\n" for row in rows), encoding="utf-8")
    try:
        duckdb_store._load(domain.table, lines, target)
    finally:
        lines.unlink()
    shutil.rmtree(folder, ignore_errors=True)
