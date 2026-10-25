"""Task 8.2: the committed JSON schemas match the contracts, and the contracts accept what they should."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from pydantic import ValidationError
from scripts.checks.contracts import render

from fantadamus.contracts.base import SCHEMA_DIR, all_contracts
from fantadamus.contracts.envelope import BronzeEnvelope
from fantadamus.contracts.skeleton.player import SkeletonPlayer
from fantadamus.core.hashing import content_sha256

ROW = {"player_id": 1, "name": "Giocatore Uno", "club": "Squadra Alfa", "role": "A"}
CEST = dt.timezone(dt.timedelta(hours=2))


def test_schema_matches_committed() -> None:
    contracts = all_contracts()
    assert {SkeletonPlayer, BronzeEnvelope} <= set(contracts)
    for contract in contracts:
        path = SCHEMA_DIR / f"{contract.contract_name()}.json"
        assert path.is_file(), f"{path.name} missing: run `uv run python -m scripts.checks.contracts --write`"
        assert path.read_text(encoding="utf-8") == render(contract.schema_document()), path.name


def test_every_contract_has_a_semantic_version() -> None:
    assert SkeletonPlayer.__version__ == "1.0.0"
    assert BronzeEnvelope.__version__ == "1.0.0"
    assert SkeletonPlayer.contract_name() == "skeleton.player.SkeletonPlayer"


def test_skeleton_player_accepts_a_valid_row() -> None:
    assert SkeletonPlayer.model_validate(ROW).model_dump() == ROW


@pytest.mark.parametrize(
    "change",
    [
        {"player_id": 0},
        {"player_id": "1"},
        {"player_id": True},
        {"name": ""},
        {"name": "x" * 61},
        {"club": ""},
        {"role": "X"},
        {"shirt": 9},
    ],
)
def test_skeleton_player_rejects_invalid_rows(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SkeletonPlayer.model_validate(ROW | change)


def _envelope(**overrides: Any) -> dict[str, Any]:
    payload = [ROW]
    fields: dict[str, Any] = {
        "source": "skeleton",
        "source_url": "https://example.org/skeleton",
        "published_at": None,
        "captured_at": dt.datetime(2026, 10, 25, 12, 0, tzinfo=CEST),
        "received_at": dt.datetime(2026, 10, 25, 10, 5, tzinfo=dt.UTC),
        "content_sha256": content_sha256(payload),
        "contract_version": "1.0.0",
        "submitted_by": "user-1",
        "payload": payload,
    }
    return fields | overrides


def test_envelope_stores_times_in_utc() -> None:
    envelope = BronzeEnvelope.model_validate(_envelope())
    assert envelope.captured_at == dt.datetime(2026, 10, 25, 10, 0, tzinfo=dt.UTC)
    assert envelope.captured_at.utcoffset() == dt.timedelta(0)


@pytest.mark.parametrize(
    "overrides",
    [
        {"captured_at": dt.datetime(2026, 10, 25, 12, 0)},  # naive
        {"content_sha256": "0" * 64},  # not the payload's hash
        {"source_url": "https://user@example.org/skeleton"},
        {"source_url": "ftp://example.org/skeleton"},
        {"contract_version": "1.0"},
        {"submitted_by": "Mario Rossi"},
        {"source": "Skeleton Source"},
    ],
)
def test_envelope_rejects_invalid_fields(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        BronzeEnvelope.model_validate(_envelope(**overrides))
