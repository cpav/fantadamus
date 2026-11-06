"""What the formation call says, on real results (mvp-lineup task 9.1; design C8; R5.2, R6.1)."""

from __future__ import annotations

from fantadamus.engine.lineup import Arrangement, Candidate
from fantadamus.engine.simulate import Simulated
from fantadamus.mcp.tools.lineup import formation_call
from tests.lineup_data import candidate


def _simulated(formation: str, mean: float) -> Simulated:
    return Simulated(formation=formation, mean=mean, low=0.0, high=0.0, fantasy_goals=1.0, thresholds=[])


def _call(gained: list[Candidate], lost: list[Candidate]) -> str:
    arrangements = {
        "4-3-3": Arrangement(formation="4-3-3", starters=tuple(gained), bench=(), left_off=()),
        "3-4-3": Arrangement(formation="3-4-3", starters=tuple(lost), bench=(), left_off=()),
    }
    call = formation_call([_simulated("4-3-3", 72.0), _simulated("3-4-3", 71.3)], arrangements)
    assert call is not None
    return call.text


def test_the_better_player_starts() -> None:
    gained = [candidate(1, "A", name="Alfa", key=6.8)]
    lost = [candidate(2, "D", name="Beta", key=6.0)]
    assert _call(gained, lost) == "4-3-3 over 3-4-3: clear, 0.70 points. Alfa 6.8 over Beta 6.0."


def test_a_lower_value_is_never_said_to_be_over_a_higher_one() -> None:
    """A real round: the 4th midfielder was worth more, but starting the 4th defender scored more, because
    the midfielder covered two doubtful starters from the bench."""
    gained = [candidate(1, "D", name="Alfa", key=6.0)]
    lost = [candidate(2, "C", name="Beta", key=6.5)]
    assert _call(gained, lost) == (
        "4-3-3 over 3-4-3: clear, 0.70 points. On paper Beta 6.5 is worth more than Alfa 6.0, but the "
        "simulated rounds favour this lineup: from the bench he covers a starter who misses out."
    )


def test_several_players_are_compared_together() -> None:
    gained = [candidate(1, "D", name="Alfa", key=6.0), candidate(2, "D", name="Beta", key=6.0)]
    lost = [candidate(3, "C", name="Gamma", key=6.5), candidate(4, "A", name="Delta", key=6.5)]
    assert _call(gained, lost) == (
        "4-3-3 over 3-4-3: clear, 0.70 points. On paper Gamma 6.5 and Delta 6.5 are worth more than "
        "Alfa 6.0 and Beta 6.0, but the simulated rounds favour this lineup: from the bench they cover a "
        "starter who misses out."
    )
