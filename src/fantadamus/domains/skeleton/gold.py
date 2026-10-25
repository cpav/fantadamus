"""Gold for the skeleton: `skeleton_role_counts`, computed in DuckDB from silver (R16.6, R16.12)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from fantadamus.contracts.skeleton.tables import SkeletonPlayerRecord, SkeletonRoleCount
from fantadamus.domains.skeleton import silver
from fantadamus.lake.duckdb_store import Table, connect, fill

QUERY = (Path(__file__).parent / "gold.sql").read_text(encoding="utf-8")
TABLE = Table(
    "skeleton_role_counts",
    "CREATE TEMP TABLE skeleton_role_counts "
    "(club VARCHAR, role VARCHAR, n_players BIGINT, source_urls VARCHAR[])",
    "INSERT INTO skeleton_role_counts VALUES (?, ?, ?, ?)",
)


def role_counts(rows: Sequence[SkeletonPlayerRecord]) -> list[SkeletonRoleCount]:
    """Players per club and role, sorted by club then role."""
    with connect() as connection:
        fill(connection, silver.TABLE, silver.table_rows(rows))
        result = connection.execute(QUERY).fetchall()
    return [
        SkeletonRoleCount(club=club, role=role, n_players=n_players, source_urls=list(source_urls))
        for club, role, n_players, source_urls in result
    ]


def table_rows(rows: Sequence[SkeletonRoleCount]) -> list[tuple[object, ...]]:
    """Rows in `TABLE`'s column order."""
    return [(row.club, row.role, row.n_players, row.source_urls) for row in rows]
