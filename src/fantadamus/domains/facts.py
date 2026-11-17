"""How a submitted fact reaches bronze and silver, shared by the slice's domains (design C3; R7.1, R7.2).

A submit tool's payload has already passed its contract. `submit` checks the page's host against the
allowlist and maps the clubs through `config/clubs.toml`; only then does it add the payload to bronze and its
rows to the domain's silver table. Silver keeps every submission's rows with their provenance, so nothing is
overwritten and a read at an earlier as-of time sees what was known then.

A store holds the lake's lock and adds its rows to the end of their month's file (mvp-store C3). The table
is always what a rebuild from bronze gives: when a store finds it isn't, because an earlier store stopped
part-way, the domain's rows changed, or the new bronze files don't sort last, it rebuilds the table instead.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from fantadamus.contracts.base import Contract
from fantadamus.contracts.envelope import BronzeEnvelope
from fantadamus.core.clock import Clock
from fantadamus.core.clubs import Clubs
from fantadamus.core.hashing import canonical_json, content_sha256
from fantadamus.core.urls import host_allowed, url_host
from fantadamus.lake.duckdb_store import Incoming, LakeStore, Table
from fantadamus.lake.months import bronze_order, follows, month_of

PROVENANCE_COLUMNS = "source_url VARCHAR, captured_at TIMESTAMPTZ, content_sha256 VARCHAR"
"""The first columns of every silver table, matching `SilverRow`."""


class RefusedError(ValueError):
    """A submission rejected before anything was written; the message says why."""


class Source(BaseModel):
    """Where a fact came from: the page, when it was read, and the content hash of its bronze record."""

    model_config = ConfigDict(frozen=True)

    source_url: str
    captured_at: dt.datetime
    content_sha256: str


class SilverRow(Source):
    """A silver row: its provenance, then the domain's columns."""

    @property
    def source(self) -> Source:
        return Source(
            source_url=self.source_url, captured_at=self.captured_at, content_sha256=self.content_sha256
        )


class Receipt(BaseModel):
    """A stored submission: its bronze record and how many silver rows it gave."""

    bronze_id: str
    rows: int


@dataclass(frozen=True)
class Domain[P: Contract, R: SilverRow]:
    """One kind of fact: its bronze folder, contract, silver table and how a payload becomes silver rows."""

    source: str
    contract: type[P]
    row: type[R]
    to_rows: Callable[[P, Clubs, Source], list[R]]
    """Silver rows for one payload; raises `UnknownClubError` or `RefusedError` if it can't be stored."""
    table: Table
    """The silver table, its columns in the row model's field order."""
    rows_version: int = 1
    """Raised when `to_rows` gives other rows for the same payload, so that the table is written again from
    bronze (mvp-store C3)."""

    def __post_init__(self) -> None:
        columns = list(self.table.columns)
        if columns != list(self.row.model_fields):
            raise ValueError(
                f"{self.table.name}: columns {columns} differ from {list(self.row.model_fields)}"
            )


def _provenance(envelope: BronzeEnvelope) -> Source:
    return Source(
        source_url=envelope.source_url,
        captured_at=envelope.captured_at,
        content_sha256=envelope.content_sha256,
    )


def payload_hash(payload: Contract) -> str:
    """The content hash a payload's bronze record carries."""
    return content_sha256(payload.model_dump(mode="json"))


def _check_host(source_url: str, allowed_hosts: Iterable[str]) -> None:
    if not host_allowed(source_url, allowed_hosts):
        host = url_host(source_url)
        raise RefusedError(
            f"source_url host {host} is not on the allowlist" if host else "source_url is not a web page"
        )


def _envelope(
    domain: Domain[Any, Any],
    payload: Contract,
    *,
    source_url: str,
    captured_at: dt.datetime,
    published_at: dt.datetime | None,
    received_at: dt.datetime,
    submitted_by: str,
) -> BronzeEnvelope:
    return BronzeEnvelope(
        source=domain.source,
        source_url=source_url,
        published_at=published_at,
        captured_at=min(captured_at, received_at),  # a page can't be read after it arrives; clocks drift
        received_at=received_at,
        content_sha256=payload_hash(payload),
        contract_version=payload.__version__,
        submitted_by=submitted_by,
        payload=payload.model_dump(mode="json"),
    )


def _incoming(bronze_id: str, rows: Iterable[SilverRow]) -> Iterator[Incoming]:
    for row in rows:
        yield Incoming(bronze_id, month_of(row.captured_at), row.model_dump_json())


def _rebuild(store: LakeStore, domain: Domain[Any, Any], clubs: Clubs) -> int:
    """Write the domain's silver table again from every bronze record. Bronze is read a batch of files at a
    time and each row goes straight to its month, so a rebuild's memory doesn't grow with the season."""

    def rows() -> Iterator[Incoming]:
        for record in store.iter_bronze(domain.source):
            payload = domain.contract.model_validate_json(canonical_json(record.envelope.payload))
            yield from _incoming(
                record.bronze_id, domain.to_rows(payload, clubs, _provenance(record.envelope))
            )

    return store.replace_rows(domain.table, rows(), domain.rows_version)


def _store(
    store: LakeStore,
    domain: Domain[Any, Any],
    clubs: Clubs,
    accepted: Sequence[tuple[BronzeEnvelope, Sequence[SilverRow]]],
) -> list[str]:
    """Store payloads already checked and turned into rows, holding the lake's lock (mvp-store C3): the
    store is marked as under way, the bronze files are added, and their rows go to the end of the silver
    table, or the table is rebuilt if it was out of step or the new files don't sort last. Returns the
    bronze IDs, in the order given."""
    with store.storing(domain.table, domain.rows_version) as written:
        bronze_ids = [store.append_bronze(envelope) for envelope, _ in accepted]
        if written is not None and follows(written.last_bronze, bronze_ids):
            stored = zip(bronze_ids, (rows for _, rows in accepted), strict=True)
            ordered = sorted(stored, key=lambda pair: bronze_order(pair[0]))
            lines = (line for bronze_id, rows in ordered for line in _incoming(bronze_id, rows))
            store.append_rows(domain.table, lines, written)
        else:
            _rebuild(store, domain, clubs)
    return bronze_ids


def submit[P: Contract](
    store: LakeStore,
    domain: Domain[P, Any],
    payload: P,
    *,
    source_url: str,
    captured_at: dt.datetime,
    published_at: dt.datetime | None,
    allowed_hosts: Iterable[str],
    clock: Clock,
    submitted_by: str,
    clubs: Clubs,
) -> Receipt:
    """Check the page and the clubs, then add the payload to bronze and its rows to the domain's silver
    table."""
    _check_host(source_url, allowed_hosts)
    with store.lock():
        envelope = _envelope(
            domain,
            payload,
            source_url=source_url,
            captured_at=captured_at,
            published_at=published_at,
            received_at=clock(),
            submitted_by=submitted_by,
        )
        rows = domain.to_rows(payload, clubs, _provenance(envelope))
        (bronze_id,) = _store(store, domain, clubs, [(envelope, rows)])
    return Receipt(bronze_id=bronze_id, rows=len(rows))


@dataclass(frozen=True)
class Submission[P: Contract]:
    """One payload read from a page, with the page's own time for it when it shows one."""

    payload: P
    published_at: dt.datetime | None = None


class Rejection(BaseModel):
    """A payload that couldn't be stored: its place in the submission and why."""

    index: int
    reason: str


class Stored(BaseModel):
    receipts: list[Receipt]
    rejections: list[Rejection]


def submit_many[P: Contract](
    store: LakeStore,
    domain: Domain[P, Any],
    submissions: Sequence[Submission[P]],
    *,
    source_url: str,
    captured_at: dt.datetime,
    allowed_hosts: Iterable[str],
    clock: Clock,
    submitted_by: str,
    clubs: Clubs,
) -> Stored:
    """The payloads one page gave for a domain: each checked first, one bronze record each and one store for
    all (design C8). A payload that fails is reported and the others still go in; a page off the allowlist
    refuses them all."""
    _check_host(source_url, allowed_hosts)
    accepted: list[tuple[BronzeEnvelope, list[SilverRow]]] = []
    rejections: list[Rejection] = []
    with store.lock():
        received_at = clock()
        for index, submission in enumerate(submissions):
            envelope = _envelope(
                domain,
                submission.payload,
                source_url=source_url,
                captured_at=captured_at,
                published_at=submission.published_at,
                received_at=received_at,
                submitted_by=submitted_by,
            )
            try:
                rows = domain.to_rows(submission.payload, clubs, _provenance(envelope))
            except ValueError as rejection:
                rejections.append(Rejection(index=index, reason=str(rejection)))
            else:
                accepted.append((envelope, rows))
        bronze_ids = _store(store, domain, clubs, accepted) if accepted else []
    receipts = [
        Receipt(bronze_id=bronze_id, rows=len(rows))
        for bronze_id, (_, rows) in zip(bronze_ids, accepted, strict=True)
    ]
    return Stored(receipts=receipts, rejections=rejections)


def rebuild(store: LakeStore, domain: Domain[Any, Any], clubs: Clubs) -> int:
    """Write the domain's silver table again from every bronze record, holding the lake's lock, a month's
    file for each month a row was captured in, and return how many rows it holds (mvp-store C4)."""
    with store.lock(), store.storing(domain.table, domain.rows_version):
        return _rebuild(store, domain, clubs)


def read_silver[R: SilverRow](
    store: LakeStore,
    domain: Domain[Any, R],
    since: dt.datetime | None = None,
    until: dt.datetime | None = None,
) -> list[R]:
    """The domain's rows, or only those captured from `since` to `until`, both included."""
    rows = store.read_rows(domain.table, since, until)
    return [domain.row.model_validate(row) for row in rows]


def last_read(
    store: LakeStore, domain: Domain[Any, Any], source_url: str, since: dt.datetime | None = None
) -> set[str]:
    """The content hashes of the newest stored read of `source_url` in the domain, from `since` on: what the
    page said last."""
    rows = [row for row in read_silver(store, domain, since) if row.source_url == source_url]
    newest = max((row.captured_at for row in rows), default=None)
    return {row.content_sha256 for row in rows if row.captured_at == newest}


def latest_by[R: SilverRow, K](rows: Iterable[R], as_of: dt.datetime, key: Callable[[R], K]) -> dict[K, R]:
    """For each key, the row captured last at or before `as_of`; ties go to the higher content hash."""
    best: dict[K, R] = {}
    for row in rows:
        if row.captured_at > as_of:
            continue
        current = best.get(key(row))
        if current is None or (row.captured_at, row.content_sha256) > (
            current.captured_at,
            current.content_sha256,
        ):
            best[key(row)] = row
    return best


def latest_submissions[R: SilverRow, K](
    rows: Iterable[R], as_of: dt.datetime, key: Callable[[R], K]
) -> dict[K, list[R]]:
    """For each key, all the rows of the submission captured last at or before `as_of`."""
    rows = list(rows)
    winners = latest_by(rows, as_of, key)
    return {
        group: [row for row in rows if key(row) == group and row.source == winner.source]
        for group, winner in winners.items()
    }
