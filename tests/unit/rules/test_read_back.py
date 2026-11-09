"""mvp-rules task 5.1: the read-back says every part of a rule in plain words (R4.2)."""

from __future__ import annotations

from fantadamus.contracts.xy.league import Band, FormulaRule, LeagueRules, LineupRules, Unit
from fantadamus.league.rules import CLASSIC, READY_MADE, left_out, priced

BANDS = [Band(from_value=6.0, points=1.0), Band(from_value=6.5, points=-0.5)]


def _line(rule: FormulaRule) -> str:
    rules = CLASSIC.model_copy(update={"formula_rules": [rule]})
    return priced(rules)[-1]


def test_each_part_is_said() -> None:
    attack = _line(next(entry.rule for entry in READY_MADE if entry.rule.name == "attack modifier"))
    assert attack == (
        "attack modifier: pure votes of A, each on his own, leaving out a player who scored, conceded or "
        "saved a penalty; from 6.5 +0.5, from 7 +1, from 7.5 +1.5, from 8 +2"
    )
    counted = FormulaRule(
        name="back four",
        who=[Unit(role="D", at_most=4)],
        combine="sum",
        base=4,
        stand_in=[5.0, 4.5],
        bands=BANDS,
    )
    assert _line(counted) == (
        "back four: pure votes of D (at most 4 D fielded), summed, counting 4 with stand-in votes 5, 4.5; "
        "from 6 +1, from 6.5 -0.5"
    )
    plain = counted.model_copy(update={"stand_in": [], "who": [Unit(role="C", at_least=3, at_most=5)]})
    assert _line(plain) == (
        "back four: pure votes of C (at least 3 and at most 5 C fielded), summed, counting 4; "
        "from 6 +1, from 6.5 -0.5"
    )


def test_the_events_come_first_and_left_out_is_by_name() -> None:
    lines = priced(CLASSIC)
    assert lines[0] == "A goal scored: +3 (P, D, C, A)"
    assert len(lines) == len(CLASSIC.events)
    assert left_out(CLASSIC) == []
    named = LeagueRules(
        events=CLASSIC.events, lineup=LineupRules(other_rules=["home factor: needs the opponent's team"])
    )
    assert left_out(named) == ["home factor: needs the opponent's team"]
