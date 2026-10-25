"""The skeleton's flow: allowlist, bronze, silver, gold, and the summary the read tool returns (C10, S3)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable

from pydantic import BaseModel, JsonValue, ValidationError

from fantadamus.contracts.skeleton.tables import SkeletonRoleCount
from fantadamus.core.clock import Clock
from fantadamus.core.urls import host_allowed, url_host
from fantadamus.domains.skeleton import bronze, gold, silver
from fantadamus.lake.duckdb_store import LakeStore


class Submission(BaseModel):
    """What a client submits: the rows, where they were read and when."""

    rows: list[JsonValue]
    source_url: str
    captured_at: dt.datetime
    published_at: dt.datetime | None = None


class RowRejection(BaseModel):
    """A rejected row (`index`), or the whole submission (`index` is None), with the reason."""

    index: int | None
    reason: str


class SubmitResult(BaseModel):
    """How many rows reached silver, which were rejected and why, and the bronze record written (if any)."""

    accepted: int
    rejected: list[RowRejection]
    bronze_id: str | None


def _refused(reason: str) -> SubmitResult:
    return SubmitResult(accepted=0, rejected=[RowRejection(index=None, reason=reason)], bronze_id=None)


def refresh(store: LakeStore) -> silver.SilverResult:
    """Rebuild silver and gold from every bronze record."""
    promoted = silver.promote(store.read_bronze(bronze.SOURCE))
    store.write_table("silver", silver.TABLE, silver.table_rows(promoted.rows))
    store.write_table("gold", gold.TABLE, gold.table_rows(gold.role_counts(promoted.rows)))
    return promoted


def submit(
    store: LakeStore, submission: Submission, *, allowed_hosts: Iterable[str], clock: Clock, submitted_by: str
) -> SubmitResult:
    """Check the source, write bronze, refresh silver and gold, and report this submission's rows."""
    if not host_allowed(submission.source_url, allowed_hosts):
        host = url_host(submission.source_url)
        if host is None:
            return _refused("source_url is not an http(s) URL with a valid host and no user-info")
        return _refused(f"source_url host {host} is not on the allowlist")
    if not submission.rows:
        return _refused("no rows submitted")
    try:
        envelope = bronze.build_envelope(
            submission.rows,
            source_url=submission.source_url,
            captured_at=submission.captured_at,
            published_at=submission.published_at,
            received_at=clock(),
            submitted_by=submitted_by,
        )
    except ValidationError as error:
        return _refused(silver.validation_reason(error))
    bronze_id = store.append_bronze(envelope)
    promoted = refresh(store)
    rejected = [
        RowRejection(index=rejection.index, reason=rejection.reason)
        for rejection in promoted.rejections
        if rejection.bronze_id == bronze_id
    ]
    rejected += [
        RowRejection(index=index, reason=violation.message)
        for violation in promoted.violations
        if violation.key["bronze_id"] == bronze_id
        for index in violation.indices
    ]
    rejected.sort(key=lambda item: -1 if item.index is None else item.index)
    return SubmitResult(accepted=len(submission.rows) - len(rejected), rejected=rejected, bronze_id=bronze_id)


def summary(store: LakeStore) -> list[SkeletonRoleCount]:
    """The gold product as stored, for the read tool."""
    return [SkeletonRoleCount.model_validate(row) for row in store.read_table("gold", gold.TABLE.name)]
