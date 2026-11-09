"""AT-15: the blank league profile names every setting `set_league_rules` takes, so the two can't drift
apart, and holds no user's details; the agent prompt tells Claude to use it (R9.3, R9.4)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import pytest

from fantadamus.contracts.xy.league import EventName, LeagueRules, LineupRules
from fantadamus.league.rules import CLASSIC, COMMON_LINEUP

ROOT = Path(__file__).resolve().parents[3]
PROFILE = (ROOT / "docs" / "league-profile-template.md").read_text(encoding="utf-8")
MINUS = "\u2212"  # how the profile writes a malus

_CLASSIC: dict[str, float] = {row.event: row.points for row in CLASSIC.events}
_EVENTS = {
    "goal": "Goal",
    "decisive_goal": "Decisive goal, on top of the goal",
    "set_piece_assist": "Set-piece assist, in place of the assist",
    "assist": "Assist",
    "penalty_scored": "Penalty scored",
    "penalty_missed": "Penalty missed",
    "penalty_saved": "Penalty saved",
    "own_goal": "Own goal",
    "yellow_card": "Yellow card",
    "red_card": "Red card",
    "goal_conceded": "Goal conceded, for a keeper",
    "clean_sheet": "Clean sheet, for a keeper",
}
_LINEUP = {
    "format": "- Format:",
    "thresholds": "## Goal thresholds",
    "bench_size": "- Bench places:",
    "substitutions": "- Substitutions per round:",
    "substitution_mode": "- How a player without a rating is replaced:",
    "formations": "- Allowed formations:",
    "no_rating_vote": "keeps this vote:",
    "other_rules": "## Other rules my league uses",
}


def test_at15_the_profile_names_every_setting() -> None:
    """A new setting fails here until the profile has it: it isn't in these tables."""
    assert set(LeagueRules.model_fields) == {"events", "formula_rules", "lineup"}
    assert "- Another modifier:" in PROFILE  # where formula rules go (mvp-rules R4.5)
    assert set(get_args(EventName)) == set(_EVENTS)
    assert set(LineupRules.model_fields) == set(_LINEUP)
    assert "## Lineup rules" in PROFILE
    for label in _LINEUP.values():
        assert label in PROFILE, label
    for label in _EVENTS.values():
        assert f"- {label}:" in PROFILE, label


@pytest.mark.parametrize("field", [field for field in _CLASSIC if field != "goal"])
def test_at15_the_values_it_offers_are_classics(field: str) -> None:
    line = next(line for line in PROFILE.splitlines() if line.startswith(f"- {_EVENTS[field]}:"))
    offered = re.search(rf"\(([+{MINUS}][\d.]+)\)", line)
    assert offered is not None, line
    assert float(offered.group(1).replace(MINUS, "-")) == _CLASSIC[field]


def test_at15_the_goal_and_the_common_values() -> None:
    assert f"- Goal: (+{_CLASSIC['goal']:g})" in PROFILE
    lines = " ".join(PROFILE.split())
    for formation in COMMON_LINEUP["formations"][0]:
        assert formation in lines.split("- Allowed formations:", 1)[1].split("- A player")[0], formation
    assert f"first fantasy goal: ({COMMON_LINEUP['thresholds'][0][0]:g})" in lines
    for mode in ("same role only", "role first, then bench order", "bench order first"):
        assert mode in lines, mode


def test_at15_it_holds_no_users_details() -> None:
    """Nothing is filled in: every field of a person's league and team ends at its colon."""
    for section in ("## My league", "## My team", "## Other teams I ask about"):
        block = PROFILE.split(section, 1)[1].split("\n## ", 1)[0]
        fields = [line for line in block.splitlines() if line.startswith("- ")]
        assert fields, section
        for line in fields:
            label, _, value = line.partition(":")
            if label in ("- Format", "- Ratings used"):  # the choices it offers
                continue
            assert value.strip() == "", line


def test_at15_the_prompt_and_the_guide_use_it() -> None:
    prompt = " ".join((ROOT / "docs" / "agent-prompt.md").read_text(encoding="utf-8").split())
    assert "league profile" in prompt
    assert "ask only for what it leaves out" in prompt
    guide = " ".join((ROOT / "docs" / "player-setup.md").read_text(encoding="utf-8").split())
    assert "docs/league-profile-template.md" in guide
    assert "Keep your filled-in copy to yourself" in PROFILE
