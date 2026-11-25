"""AT-7: an approved share is in the constants and in the calibration log, and what it moves on a round's
lineup and cards: the flat cameos' chances, never a chance of starting or a priced cameo's, with the shape of
every answer the same (mvp-cameos R3.2, R3.3)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from fantadamus.engine import constants
from fantadamus.engine.outfield import priors
from fantadamus.lake.decision_log import LoggedPlayer
from tests.lineup_harness import CLUBS, LINES, a_round, player_id

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[3]
PRICED = {
    player_id(club, word): role != "P" and priors(role, mantra).priced_cameo
    for club in CLUBS
    for word, (role, mantra) in LINES.items()
}
"""Every player of the invented round, and whether his cameo is priced."""
KEEPERS = {player_id(club, word) for club in CLUBS for word, (role, _) in LINES.items() if role == "P"}


def _entries() -> list[str]:
    """The calibration log's entries, newest first, each from its heading's date."""
    log = (ROOT / "docs" / "calibration-log.md").read_text(encoding="utf-8")
    return log.split("\n## ")[1:]


def _values(entry: str) -> dict[str, tuple[str, str]]:
    """Each value an entry changed, from what and to what."""
    return {
        name: (old.strip(), new.strip())
        for name, old, new in re.findall(r"^\| `([A-Z_]+)` \| ([^|]+) \| ([^|]+) \|", entry, re.MULTILINE)
    }


def test_at7_the_log_has_the_value() -> None:
    """The newest entry that names the share has the value in `engine/constants.py`, on what evidence, what it
    moves and what it leaves alone, as aggregates."""
    entry = next(entry for entry in _entries() if "CAMEO_SHARE" in _values(entry))
    assert entry.startswith("2026-11-24: rounds 10 to 12")
    assert _values(entry) == {"CAMEO_SHARE": ("0.500", f"{constants.CAMEO_SHARE:.3f}")}
    assert "255 players with a flat cameo" in entry
    for heading in ("### What it moves", "### Not changed"):
        assert heading in entry
    assert "`CAMEO_SHARE_PRICED`" in entry.split("### Not changed")[1]
    assert constants.CAMEO_SHARE_PRICED == 0.5  # it waits for its 200 players


def _shape(answer: Any) -> Any:
    """Every key an answer has, at every depth, without its values."""
    if isinstance(answer, dict):
        return {key: _shape(value) for key, value in answer.items()}
    if isinstance(answer, list):
        return [_shape(item) for item in answer[:1]]
    return type(answer).__name__


async def _answers(
    tmp_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[int, LoggedPlayer]]:
    """The lineup, a card, and what the lineup logged for each player of the squad."""
    async with a_round(tmp_path) as here:
        lineup = await here.ask()
        card = await here.client.call_tool("match_card", {"club": "Alfa"})
        decision = next(found for found in here.log.read() if found.kind == "lineup")
    assert card.structured_content is not None
    return lineup, card.structured_content, {player.player_id: player for player in decision.players}


async def test_at7_what_it_moves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calibrated, calibrated_card, now = await _answers(tmp_path / "calibrated")
    share = constants.CAMEO_SHARE
    monkeypatch.setattr(constants, "CAMEO_SHARE", 0.5)
    started, started_card, was = await _answers(tmp_path / "started")

    assert _shape(calibrated) == _shape(started)
    assert _shape(calibrated_card) == _shape(started_card)
    assert calibrated["lineup"]["formation"] == started["lineup"]["formation"]
    card_now = {player["player_id"]: player["p_start"] for player in calibrated_card["card"]["players"]}
    card_was = {player["player_id"]: player["p_start"] for player in started_card["card"]["players"]}
    assert card_now == card_was

    flat = [id for id in now if id not in KEEPERS and not PRICED[id] and was[id].p_cameo > 0]
    priced = [id for id in now if PRICED[id] and was[id].p_cameo > 0]
    assert flat
    assert priced
    for id in now:
        assert now[id].p_start == was[id].p_start
    for id in flat:
        assert now[id].p_cameo == pytest.approx(was[id].p_cameo * share / 0.5)
        after, before = now[id].p_rating, was[id].p_rating
        assert after is not None
        assert before is not None
        assert after < before
    for id in [*priced, *(id for id in now if id in KEEPERS)]:
        assert (now[id].p_cameo, now[id].p_rating) == (was[id].p_cameo, was[id].p_rating)
