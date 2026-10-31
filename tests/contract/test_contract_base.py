"""Task 8.2: the committed JSON schemas match the contracts, every contract has a semantic version, and the
bronze envelope accepts what it should."""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

import pytest
from pydantic import ValidationError
from scripts.checks.contracts import render

from fantadamus.contracts.base import SCHEMA_DIR, SEMVER_PATTERN, all_contracts
from fantadamus.contracts.envelope import BronzeEnvelope
from fantadamus.contracts.xy.fixtures import FixturesPayload
from fantadamus.core.hashing import content_sha256

PAYLOAD = {
    "round": 9,
    "matches": [{"home": "Alfa", "away": "Beta", "kickoff_at": "2026-10-31T15:00:00+01:00"}],
}
CEST = dt.timezone(dt.timedelta(hours=2))


def test_schema_matches_committed() -> None:
    contracts = all_contracts()
    assert {FixturesPayload, BronzeEnvelope} <= set(contracts)
    for contract in contracts:
        path = SCHEMA_DIR / f"{contract.contract_name()}.json"
        assert path.is_file(), f"{path.name} missing: run `uv run python -m scripts.checks.contracts --write`"
        assert path.read_text(encoding="utf-8") == render(contract.schema_document()), path.name


def test_every_contract_has_a_semantic_version() -> None:
    for contract in all_contracts():
        assert re.fullmatch(SEMVER_PATTERN, contract.__version__), contract.contract_name()
    assert FixturesPayload.contract_name() == "xy.fixtures.FixturesPayload"


def _envelope(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "source": "fixtures",
        "source_url": "https://example.org/calendar",
        "published_at": None,
        "captured_at": dt.datetime(2026, 10, 25, 12, 0, tzinfo=CEST),
        "received_at": dt.datetime(2026, 10, 25, 10, 5, tzinfo=dt.UTC),
        "content_sha256": content_sha256(PAYLOAD),
        "contract_version": "1.0.0",
        "submitted_by": "user-1",
        "payload": PAYLOAD,
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
        {"source_url": "https://user@example.org/calendar"},
        {"source_url": "ftp://example.org/calendar"},
        {"contract_version": "1.0"},
        {"submitted_by": "Mario Rossi"},
        {"source": "Fixtures Source"},
    ],
)
def test_envelope_rejects_invalid_fields(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        BronzeEnvelope.model_validate(_envelope(**overrides))
