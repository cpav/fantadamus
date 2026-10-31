"""mvp-collect task 4.1: many payloads from one page, one bronze record each and one silver rebuild per
domain; a payload that fails is reported and the others still go in (design C8; R1.1, R1.4)."""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from fantadamus.contracts.xy.lineups import OutletLineupPayload
from fantadamus.core.clock import fixed_clock
from fantadamus.domains import facts
from fantadamus.domains.availability.silver import OUTLET_VIEWS
from fantadamus.lake.duckdb_store import LakeStore, Layer, Row, Table
from tests.xy_harness import CLUBS, NOW, URL, outlet_lineup

READ = dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.UTC)


def _view(outlet: str, home: str = "Alfa") -> OutletLineupPayload:
    return OutletLineupPayload.model_validate_json(json.dumps(outlet_lineup(outlet, home=home)))


def _submit_many(store: LakeStore, items: list[facts.Submission[Any]], url: str = URL) -> facts.Stored:
    return facts.submit_many(
        store,
        OUTLET_VIEWS,
        items,
        source_url=url,
        captured_at=READ,
        allowed_hosts=["example.org"],
        clock=fixed_clock(NOW),
        submitted_by="collector",
        clubs=CLUBS,
    )


def test_one_rebuild_per_domain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = LakeStore(tmp_path)
    rebuilt: list[str] = []
    write_table = store.write_table

    def counting(layer: Layer, table: Table, rows: Sequence[Row]) -> Path:
        rebuilt.append(table.name)
        return write_table(layer, table, rows)

    monkeypatch.setattr(store, "write_table", counting)
    published = dt.datetime(2026, 10, 26, 8, 0, tzinfo=dt.UTC)
    stored = _submit_many(
        store,
        [
            facts.Submission(_view("Uno"), published_at=published),
            facts.Submission(_view("Due")),
            facts.Submission(_view("Tre", home="Omega")),
        ],
    )
    assert len(stored.receipts) == 2
    assert [(rejection.index, rejection.reason) for rejection in stored.rejections] == [
        (2, "unknown club 'Omega'; known clubs: Alfa, Beta, Delta, Gamma")
    ]
    assert rebuilt == ["outlet_views"]  # once for the whole page
    records = store.read_bronze(OUTLET_VIEWS.source)
    assert {(record.envelope.submitted_by, record.envelope.published_at) for record in records} == {
        ("collector", published),
        ("collector", None),
    }
    assert {row.outlet for row in facts.read_silver(store, OUTLET_VIEWS)} == {"Uno", "Due"}
    assert facts.last_read(store, OUTLET_VIEWS, URL) == {record.envelope.content_sha256 for record in records}
    with pytest.raises(facts.RefusedError, match=r"elsewhere\.example is not on the allowlist"):
        _submit_many(store, [facts.Submission(_view("Uno"))], url="https://elsewhere.example/x")
    assert len(store.bronze_files(OUTLET_VIEWS.source)) == 2
