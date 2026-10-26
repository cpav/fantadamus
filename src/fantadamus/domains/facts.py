"""How a submitted fact reaches bronze and silver, shared by the slice's domains (design C3; R7.1, R7.2).

A submit tool's payload has already passed its contract. `submit` checks the page's host against the
allowlist and maps the clubs through `config/clubs.toml`; only then does it append the payload to bronze and
rebuild the domain's silver table from all of its bronze records. Silver keeps every submission's rows with
their provenance, so nothing is overwritten and a read at an earlier as-of time sees what was known then.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from fantadamus.contracts.base import Contract
from fantadamus.contracts.envelope import BronzeEnvelope
from fantadamus.core.clock import Clock
from fantadamus.core.clubs import Clubs
from fantadamus.core.hashing import canonical_json, content_sha256
from fantadamus.core.urls import host_allowed, url_host
from fantadamus.lake.duckdb_store import LakeStore, Table

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

    def __post_init__(self) -> None:
        columns = re.findall(r"[(,] *(\w+) ", self.table.create_sql)
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
    """Check the page and the clubs, append the payload to bronze and rebuild the domain's silver table."""
    if not host_allowed(source_url, allowed_hosts):
        host = url_host(source_url)
        raise RefusedError(
            f"source_url host {host} is not on the allowlist" if host else "source_url is not a web page"
        )
    data = payload.model_dump(mode="json")
    received_at = clock()
    envelope = BronzeEnvelope(
        source=domain.source,
        source_url=source_url,
        published_at=published_at,
        captured_at=min(captured_at, received_at),  # a page can't be read after it arrives; clocks drift
        received_at=received_at,
        content_sha256=content_sha256(data),
        contract_version=payload.__version__,
        submitted_by=submitted_by,
        payload=data,
    )
    rows = domain.to_rows(payload, clubs, _provenance(envelope))
    bronze_id = store.append_bronze(envelope)
    rebuild(store, domain, clubs)
    return Receipt(bronze_id=bronze_id, rows=len(rows))


def rebuild(store: LakeStore, domain: Domain[Any, Any], clubs: Clubs) -> None:
    """Replace the domain's silver table with the rows of every bronze record."""
    rows: list[SilverRow] = []
    for record in store.read_bronze(domain.source):
        payload = domain.contract.model_validate_json(canonical_json(record.envelope.payload))
        rows.extend(domain.to_rows(payload, clubs, _provenance(record.envelope)))
    store.write_table("silver", domain.table, [tuple(row.model_dump().values()) for row in rows])


def read_silver[R: SilverRow](store: LakeStore, domain: Domain[Any, R]) -> list[R]:
    return [domain.row.model_validate(row) for row in store.read_table("silver", domain.table.name)]


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
