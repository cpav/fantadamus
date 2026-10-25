"""Silver for the skeleton: validate bronze rows, apply the quality rule, keep the latest row per player
(R16.4, R16.5).

The result depends only on the bronze contents, not on the order they arrived in: a player's row is the one
with the latest `captured_at`, ties broken by the row's canonical JSON.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import JsonValue, ValidationError

from fantadamus.contracts.skeleton.player import SkeletonPlayer
from fantadamus.contracts.skeleton.tables import SkeletonPlayerRecord
from fantadamus.core.hashing import canonical_json
from fantadamus.lake.duckdb_store import BronzeRecord, Table
from fantadamus.quality.rules import UNIQUE_PLAYER_PER_PAYLOAD, Violation

TABLE = Table(
    "skeleton_players",
    "CREATE TEMP TABLE skeleton_players (player_id BIGINT, name VARCHAR, club VARCHAR, role VARCHAR, "
    "source_url VARCHAR, captured_at TIMESTAMPTZ, bronze_sha256 VARCHAR)",
    "INSERT INTO skeleton_players VALUES (?, ?, ?, ?, ?, ?, ?)",
)


@dataclass(frozen=True)
class Rejection:
    """A payload row kept out of silver; `index` is None when the whole payload is unusable."""

    bronze_id: str
    index: int | None
    reason: str


@dataclass(frozen=True)
class SilverResult:
    rows: list[SkeletonPlayerRecord]
    rejections: list[Rejection]
    violations: list[Violation]


def validation_reason(error: ValidationError) -> str:
    """Field-level reasons, e.g. `player_id: Input should be greater than 0`."""
    return "; ".join(
        f"{'.'.join(map(str, detail['loc'])) or 'row'}: {detail['msg']}" for detail in error.errors()
    )


def validate_rows(
    payload: JsonValue,
) -> tuple[list[tuple[int, SkeletonPlayer]], list[tuple[int | None, str]]]:
    """Split a payload into valid players and (index, reason) rejections."""
    if not isinstance(payload, list):
        return [], [(None, "payload must be a list of rows")]
    valid: list[tuple[int, SkeletonPlayer]] = []
    invalid: list[tuple[int | None, str]] = []
    for index, row in enumerate(payload):
        try:
            valid.append((index, SkeletonPlayer.model_validate(row)))
        except ValidationError as error:
            invalid.append((index, validation_reason(error)))
    return valid, invalid


def _rank(record: SkeletonPlayerRecord) -> tuple[str, str]:
    return record.captured_at.isoformat(), canonical_json(record.model_dump(mode="json"))


def promote(records: Sequence[BronzeRecord]) -> SilverResult:
    """Build silver `skeleton_players` from every bronze record."""
    rejections: list[Rejection] = []
    candidates: list[tuple[BronzeRecord, int, SkeletonPlayer]] = []
    for record in records:
        valid, invalid = validate_rows(record.envelope.payload)
        rejections.extend(Rejection(record.bronze_id, index, reason) for index, reason in invalid)
        candidates.extend((record, index, player) for index, player in valid)
    violations = UNIQUE_PLAYER_PER_PAYLOAD.check(
        {"bronze_id": record.bronze_id, "player_id": player.player_id, "index": index}
        for record, index, player in candidates
    )
    excluded = {
        (violation.key["bronze_id"], index) for violation in violations for index in violation.indices
    }
    latest: dict[int, SkeletonPlayerRecord] = {}
    for record, index, player in candidates:
        if (record.bronze_id, index) in excluded:
            continue
        row = SkeletonPlayerRecord(
            **player.model_dump(),
            source_url=record.envelope.source_url,
            captured_at=record.envelope.captured_at,
            bronze_sha256=record.envelope.content_sha256,
        )
        current = latest.get(row.player_id)
        if current is None or _rank(row) > _rank(current):
            latest[row.player_id] = row
    return SilverResult(
        rows=[latest[player_id] for player_id in sorted(latest)],
        rejections=sorted(
            rejections, key=lambda item: (item.bronze_id, -1 if item.index is None else item.index)
        ),
        violations=violations,
    )


def table_rows(rows: Sequence[SkeletonPlayerRecord]) -> list[tuple[object, ...]]:
    """Rows in `TABLE`'s column order."""
    return [
        (row.player_id, row.name, row.club, row.role, row.source_url, row.captured_at, row.bronze_sha256)
        for row in rows
    ]
