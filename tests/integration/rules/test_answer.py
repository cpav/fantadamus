"""mvp-rules task 3.2: a close call a formula rule could tip says so, rather than search every
combination (R3.5)."""

from __future__ import annotations

from fantadamus.contracts.xy.league import Band, FormulaRule, Unit
from fantadamus.engine.lineup import Arrangement, arrange
from fantadamus.engine.rank import Option
from fantadamus.mcp.tools.lineup import place_calls
from tests.lineup_data import candidate, lineup_rules

DEFENCE = FormulaRule(
    name="defence modifier",
    who=[Unit(role="P"), Unit(role="D", best=3)],
    combine="average",
    bands=[Band(from_value=6.0, points=1.0)],
)
ATTACK = FormulaRule(name="attack modifier", who=[Unit(role="A")], combine="each", bands=DEFENCE.bands)


def _options(arranged: Arrangement) -> dict[int, Option]:
    return {
        player.player_id: Option(
            name=player.name, p_start=player.p_start, p_cameo=player.p_cameo, e_start=player.key, e_cameo=0.0
        )
        for player in (*arranged.starters, *arranged.bench)
    }


def test_a_close_call_says_a_rule_could_tip_it() -> None:
    """Only a coin flip, and only in a role the rule counts: here a defender's, not the keeper's lean."""
    squad = [
        candidate(1, "P", key=6.0, p_start=0.9, p_cameo=0.0, club="a"),
        candidate(2, "P", key=5.7, p_start=0.9, p_cameo=0.0, club="b"),
        *(candidate(10 + n, "D", key=7.0 - n / 10, p_start=0.9, p_cameo=0.0) for n in range(5)),
        *(candidate(20 + n, "C", key=7.0 - n, p_start=0.9, p_cameo=0.0) for n in range(5)),
        *(candidate(30 + n, "A", key=8.0 - n, p_start=0.9, p_cameo=0.0) for n in range(4)),
    ]
    arranged = arrange(squad, "4-3-3", lineup_rules())
    options = _options(arranged)
    defender, keeper = place_calls(arranged, options, [DEFENCE])
    assert (defender.label, keeper.label) == ("coin flip", "lean")
    assert defender.text.endswith("The defence modifier could tip this.")
    assert "could tip" not in keeper.text
    for others in ([], [ATTACK]):
        assert all("could tip" not in call.text for call in place_calls(arranged, options, others))
