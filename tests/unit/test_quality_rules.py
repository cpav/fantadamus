"""Task 8.3: the skeleton's data-quality rule (C10): `player_id` is unique within one payload."""

from __future__ import annotations

from fantadamus.quality.rules import UNIQUE_PLAYER_PER_PAYLOAD, Violation


def test_duplicate_player_id_reported() -> None:
    rows = [
        {"bronze_id": "b1", "player_id": 7, "index": 0},
        {"bronze_id": "b1", "player_id": 7, "index": 2},
        {"bronze_id": "b1", "player_id": 8, "index": 1},
        {"bronze_id": "b2", "player_id": 7, "index": 0},  # another payload: not a violation
    ]
    assert UNIQUE_PLAYER_PER_PAYLOAD.check(rows) == [
        Violation(
            rule="unique_player_id",
            key={"bronze_id": "b1", "player_id": 7},
            indices=(0, 2),
            message="player_id 7 appears 2 times in one payload",
        )
    ]


def test_unique_rows_pass() -> None:
    rows = [{"bronze_id": "b1", "player_id": n, "index": n} for n in range(3)]
    assert UNIQUE_PLAYER_PER_PAYLOAD.check(rows) == []
