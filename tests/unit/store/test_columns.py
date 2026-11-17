"""mvp-store task 1.3: a table says its columns once, in its `CREATE` statement, and a domain's table has its
row's fields in their order, so that rows loaded by name land where they belong (design C2)."""

from __future__ import annotations

import pytest

from fantadamus.contracts.xy.fixtures import FixturesPayload
from fantadamus.domains.facts import PROVENANCE_COLUMNS, Domain
from fantadamus.domains.fixtures.silver import FIXTURES, FixtureRow
from fantadamus.lake.duckdb_store import BRONZE, Table


def test_a_table_says_its_columns() -> None:
    assert FIXTURES.table.columns == {
        "source_url": "VARCHAR",
        "captured_at": "TIMESTAMPTZ",
        "content_sha256": "VARCHAR",
        "round": "BIGINT",
        "home": "VARCHAR",
        "away": "VARCHAR",
        "kickoff_at": "TIMESTAMPTZ",
    }
    assert list(BRONZE.columns)[:2] == ["source", "source_url"]
    assert len(BRONZE.columns) == 9


@pytest.mark.parametrize(
    "columns",
    [
        "round BIGINT, home VARCHAR, away VARCHAR",  # one missing
        "round BIGINT, away VARCHAR, home VARCHAR, kickoff_at TIMESTAMPTZ",  # another order
        "round BIGINT, home VARCHAR, away VARCHAR, kickoff_at TIMESTAMPTZ, note VARCHAR",  # one too many
    ],
)
def test_a_domains_table_has_its_rows_fields(columns: str) -> None:
    table = Table("fixtures", f"CREATE TEMP TABLE fixtures ({PROVENANCE_COLUMNS}, {columns})")
    with pytest.raises(ValueError, match=r"fixtures: columns .* differ from"):
        Domain("fixtures", FixturesPayload, FixtureRow, FIXTURES.to_rows, table)
