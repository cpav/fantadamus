"""mvp-sources: the new facts' contracts, as a submit tool will receive them (design C2)."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import pytest
from pydantic import ValidationError

from fantadamus.contracts.xy.fixtures import OtherFixturesPayload

MATCH = {"home": "Alfa", "away": "Ostrava Rovers", "kickoff_at": "2026-09-08T21:00:00+02:00"}


def _parse(payload: dict[str, Any]) -> OtherFixturesPayload:
    return OtherFixturesPayload.model_validate_json(json.dumps(payload))


def test_other_fixtures_payload() -> None:
    """Task 2.1 (R2.1): a competition's matches, each with its kickoff stored in UTC and two different clubs;
    a league phase's 144 matches fit."""
    payload = _parse({"competition": "Champions League", "matches": [MATCH]})
    assert payload.matches[0].kickoff_at == dt.datetime(2026, 9, 8, 19, 0, tzinfo=dt.UTC)
    assert OtherFixturesPayload.__version__ == "1.0.0"
    assert len(_parse({"competition": "Coppa Italia", "matches": [MATCH] * 144}).matches) == 144
    wrong: list[tuple[dict[str, Any], str]] = [
        ({"competition": "Serie B", "matches": [MATCH]}, "competition"),
        ({"competition": "Europa League", "matches": []}, "at least 1"),
        ({"competition": "Europa League", "matches": [MATCH] * 201}, "at most 200"),
        ({"competition": "Europa League", "matches": [MATCH | {"away": "ALFA"}]}, "plays itself"),
        (
            {"competition": "Europa League", "matches": [MATCH | {"kickoff_at": "2026-09-08T21:00:00"}]},
            "timezone",
        ),
        ({"competition": "Europa League", "matches": [MATCH], "score": "2-1"}, "Extra inputs"),
    ]
    for payload_json, reason in wrong:
        with pytest.raises(ValidationError, match=reason):
            _parse(payload_json)
