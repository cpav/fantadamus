"""Task 8.3: silver validation of a payload that isn't a list of rows (R16.5)."""

from __future__ import annotations

from fantadamus.domains.skeleton import silver


def test_non_list_payload_is_rejected_whole() -> None:
    assert silver.validate_rows({"player_id": 1}) == ([], [(None, "payload must be a list of rows")])
