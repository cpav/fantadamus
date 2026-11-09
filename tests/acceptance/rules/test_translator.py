"""AT-10 and AT-13 of mvp-rules: Claude as the translator. Saved rules are read back as what's priced and
what's left out; left-out rules are named in every answer; one setup step offers the ready-made entries; the
blank profile and the guide name the new settings (R2.3, R2.5, R4.1 to R4.5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fantadamus.contracts.xy.league import FormulaRule, LeagueRules
from fantadamus.league.rules import CLASSIC, READY_MADE, setup_step
from tests.lineup_harness import LEAGUE, a_round
from tests.xy_harness import classic_with

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[3]
LEFT_OUT = ["home factor: needs the opponent's team", "fair play: not priced yet"]


def _ready(name: str) -> FormulaRule:
    return next(entry.rule for entry in READY_MADE if entry.rule.name == name)


async def _save(here: Any, **changes: Any) -> dict[str, Any]:
    result = await here.client.call_tool("set_league_rules", {"rules": classic_with(**changes)})
    assert not result.is_error, result
    saved: dict[str, Any] | None = result.structured_content
    assert saved is not None
    return saved


async def test_at10_the_read_back(tmp_path: Path) -> None:
    """Every event and formula rule that counts, in plain words, and what's left out with what it needs."""
    async with a_round(tmp_path) as here:
        saved = await _save(
            here,
            goal={"defender": 4.5, "forward": 3.0},
            formula_rules=[_ready("defence modifier").model_dump(), _ready("captain").model_dump()],
            lineup=LEAGUE | {"other_rules": LEFT_OUT},
        )
    priced = saved["priced"]
    assert "A goal scored: +4.5 (D)" in priced
    assert "A goal scored: +3 (A)" in priced
    assert "A yellow card: -0.5 (P, D, C, A)" in priced
    defence = next(line for line in priced if line.startswith("defence modifier: "))
    for part in ("the best 3 D", "at least 4 D fielded", "from 7 +6"):
        assert part in defence, part
    assert any(line.startswith("captain: the captain's pure vote") for line in priced)
    assert saved["left_out"] == LEFT_OUT
    assert saved["rules"]["formula_rules"][0]["name"] == "defence modifier"


async def test_at10_left_out_rules_are_named(tmp_path: Path) -> None:
    """A rule that needs the opponent, and one with no estimate: named in the lineup, "X or Y?" and an
    outlook, and kept by name only."""
    async with a_round(tmp_path) as here:
        await _save(
            here, lineup=LEAGUE | {"other_rules": LEFT_OUT}, formula_rules=[_ready("captain").model_dump()]
        )
        lineup = (await here.ask())["lineup"]
        compared = await here.client.call_tool(
            "compare_players", {"first": "Alfa Nove", "second": "Gamma Nove"}
        )
        outlook = await here.client.call_tool("player_outlook", {"player": "Alfa Nove"})
    warning = next(line for line in lineup["warnings"] if "doesn't include" in line)
    assert all(rule in warning for rule in LEFT_OUT)
    for result in (compared, outlook):
        content = result.structured_content
        assert content is not None
        left_out = content["answer"]["left_out"]
        assert left_out[: len(LEFT_OUT)] == LEFT_OUT
        assert "captain: counted in the full lineup, not in this answer" in left_out


def test_at13_the_ready_made_entries_are_valid() -> None:
    """At the researched values, each valid on its own and together with Classic's table."""
    defence, attack, captain = (_ready(name) for name in ("defence modifier", "attack modifier", "captain"))
    assert [(band.from_value, band.points) for band in defence.bands] == [(6.0, 1.0), (6.5, 3.0), (7.0, 6.0)]
    assert defence.who != "captain"
    assert [(unit.role, unit.best, unit.at_least) for unit in defence.who] == [("P", None, None), ("D", 3, 4)]
    assert (attack.combine, attack.leave_out) == ("each", "bonus_or_goal")
    assert [(band.from_value, band.points) for band in attack.bands] == [
        (6.5, 0.5),
        (7.0, 1.0),
        (7.5, 1.5),
        (8.0, 2.0),
    ]
    assert captain.who == "captain"
    assert [band.points for band in captain.bands] == [-2.5 + step / 2 for step in range(11)]
    assert [band.from_value for band in captain.bands][1:] == [4.0 + step / 2 for step in range(10)]
    everything = CLASSIC.model_dump() | {"formula_rules": [entry.rule.model_dump() for entry in READY_MADE]}
    assert len(LeagueRules.model_validate(everything).formula_rules) == 3
    assert all(entry.meaning for entry in READY_MADE)


def test_at13_one_setup_step() -> None:
    """Whatever the question still needs, in one step, with the ready-made entries until a league has some."""
    first = setup_step(None, lineup=False)
    assert first is not None
    assert {field.field for field in first.events} == {row.event for row in CLASSIC.events}
    assert (first.lineup, first.also) == ([], [])
    assert [entry.rule.name for entry in first.ready_made] == [
        "defence modifier",
        "attack modifier",
        "captain",
    ]
    for_a_lineup = setup_step(None, lineup=True)
    assert for_a_lineup is not None
    assert for_a_lineup.events
    assert for_a_lineup.lineup
    assert for_a_lineup.also
    assert setup_step(CLASSIC, lineup=False) is None
    with_rules = CLASSIC.model_copy(update={"formula_rules": [_ready("captain")]})
    lineup_only = setup_step(with_rules, lineup=True)
    assert lineup_only is not None
    assert (lineup_only.events, lineup_only.ready_made) == ([], [])
    assert lineup_only.lineup


def test_at13_the_profile_names_the_new_settings() -> None:
    profile = " ".join((ROOT / "docs" / "league-profile-template.md").read_text(encoding="utf-8").split())
    for part in (
        "## Modifiers and the captain",
        "- Defence modifier: (the keeper and the three best defenders",
        "- Attack modifier: (each forward who didn't score",
        "- Captain: (the captain's pure vote",
        "- Another modifier:",
        "what it needs",
        "docs/league-rules.md",
    ):
        assert part in profile, part
    assert "Fantadamus doesn't include these in its score yet" not in profile
    guide = " ".join((ROOT / "docs" / "player-setup.md").read_text(encoding="utf-8").split())
    for part in ("paste your league's rulebook", "what's priced and what's left out", "docs/league-rules.md"):
        assert part in guide, part
