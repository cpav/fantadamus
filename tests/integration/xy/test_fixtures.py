"""Task 2.1: `submit_fixtures`, silver `fixtures` and the round's deadline (R2.1, R2.2, R7.1, R7.2)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.domains.facts import read_silver
from fantadamus.domains.fixtures import gold
from fantadamus.domains.fixtures.silver import FIXTURES
from fantadamus.lake.duckdb_store import LakeStore
from tests.xy_harness import URL, error_text, page, send, tools

pytestmark = pytest.mark.anyio

READ = dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.UTC)
LATER = dt.datetime(2026, 10, 28, 9, 0, tzinfo=dt.UTC)


def _kickoff(day: int, hour: int) -> dt.datetime:
    return dt.datetime(2026, 10, day, hour, 0, tzinfo=dt.UTC)


async def test_submit_fixtures_bronze_to_silver(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    async with tools(store) as client:
        result = await send(client, "submit_fixtures", page("fixtures"), READ)
        assert not result.is_error, result
        assert result.structured_content is not None
        assert result.structured_content["rows"] == 2

        off_list = await send(
            client, "submit_fixtures", page("fixtures"), READ, url="https://elsewhere.example/x"
        )
        assert "elsewhere.example is not on the allowlist" in error_text(off_list)
        not_a_page = await send(client, "submit_fixtures", page("fixtures"), READ, url="ftp://example.org/x")
        assert "not a web page" in error_text(not_a_page)
        unknown = page("fixtures")
        unknown["matches"][0]["home"] = "Omega"
        refused = await send(client, "submit_fixtures", unknown, READ)
        assert "unknown club 'Omega'; known clubs: Alfa, Beta, Delta, Gamma" in error_text(refused)
        bad_round = page("fixtures") | {"round": 39}
        assert "less than or equal to 38" in error_text(
            await send(client, "submit_fixtures", bad_round, READ)
        )

    assert len(store.bronze_files("fixtures")) == 1  # refusals write nothing
    [record] = store.read_bronze("fixtures")
    assert record.envelope.submitted_by == "user-1"
    assert record.envelope.captured_at == READ
    rows = read_silver(store, FIXTURES)
    assert [(row.round, row.home, row.away, row.kickoff_at) for row in rows] == [
        (9, "alfa", "beta", _kickoff(31, 14)),
        (9, "gamma", "delta", _kickoff(31, 17)),
    ]
    assert {(row.source_url, row.captured_at, row.content_sha256) for row in rows} == {
        (URL, READ, record.envelope.content_sha256)
    }


async def test_deadline_is_first_kickoff(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    moved = page("fixtures")
    moved["matches"][0]["kickoff_at"] = "2026-10-31T21:00:00+01:00"  # Alfa-Beta moved after Gamma-Delta
    async with tools(store) as client:
        await send(client, "submit_fixtures", page("fixtures"), READ)
        await send(client, "submit_fixtures", moved, LATER)
    rows = read_silver(store, FIXTURES)
    assert gold.deadline(rows, 9, as_of=READ) == _kickoff(31, 14)
    assert gold.deadline(rows, 9, as_of=LATER) == _kickoff(31, 17)
    assert gold.deadline(rows, 10, as_of=LATER) is None


async def test_as_of_ignores_later_fixtures(tmp_path: Path) -> None:
    store = LakeStore(tmp_path)
    moved = page("fixtures")
    moved["round"] = 12
    async with tools(store) as client:
        await send(client, "submit_fixtures", page("fixtures"), READ)
        await send(client, "submit_fixtures", moved, LATER)
    rows = read_silver(store, FIXTURES)
    assert gold.fixture(rows, "beta", 9, as_of=READ - dt.timedelta(seconds=1)) is None
    match = gold.fixture(rows, "beta", 9, as_of=READ)
    assert match is not None
    assert (match.home, match.away, match.source.captured_at) == ("alfa", "beta", READ)
    assert gold.fixture(rows, "beta", 9, as_of=LATER) is None  # postponed to round 12
    later = gold.fixture(rows, "beta", 12, as_of=LATER)
    assert later is not None
    assert later.source.source_url == URL
