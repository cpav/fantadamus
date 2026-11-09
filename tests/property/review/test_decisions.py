"""P3 and P4 of mvp-review: following the advice gives no decision and no gain; each decision is priced on
its own, whatever order the lineup comes in, and applying them all gives the eleven fielded (design C6; R3.1,
R3.2, R3.4)."""

from __future__ import annotations

import dataclasses
import random

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.domains.review import Picked, applied, review_choices
from fantadamus.engine.lineup import arrange
from tests.lineup_data import FORMATIONS
from tests.review_choices import ADVICE, RULES, SQUAD, Stand

_VALUES = st.dictionaries(st.integers(1, 25), st.floats(4.0, 9.0), max_size=10)


def _stand(expected: dict[int, float], real: dict[int, float]) -> Stand:
    return Stand(
        expected,
        real,
        captain_expected={20: 1.0},
        captain_real={20: 2.0},
        bench_expected={},
        bench_real={},
    )


@given(formation=st.sampled_from(FORMATIONS), expected=_VALUES, real=_VALUES)
def test_p3_the_advice_followed(formation: str, expected: dict[int, float], real: dict[int, float]) -> None:
    arranged = arrange(SQUAD, formation, RULES)
    advice = Picked(
        formation,
        tuple(player.player_id for player in arranged.starters),
        tuple(player.player_id for player in arranged.bench),
        20 if any(player.player_id == 20 for player in arranged.starters) else None,
        None,
    )
    stand = _stand(expected, real)
    reviewed = review_choices(advice, advice, SQUAD, RULES, price=stand.price, score=stand.score)
    assert reviewed.choices == []
    assert (reviewed.total_cost, reviewed.total_gain) == (0.0, 0.0)


@given(
    formation=st.sampled_from(FORMATIONS),
    order=st.randoms(use_true_random=False),
    expected=_VALUES,
    real=_VALUES,
)
def test_p4_the_order_doesnt_matter(
    formation: str, order: random.Random, expected: dict[int, float], real: dict[int, float]
) -> None:
    arranged = arrange(SQUAD, formation, RULES, start={8, 17})  # a different eleven from the advice's
    fielded = Picked(
        formation,
        tuple(player.player_id for player in arranged.starters),
        tuple(player.player_id for player in arranged.bench),
        None,
        None,
    )
    shuffled = list(fielded.starters)
    order.shuffle(shuffled)
    stand = _stand(expected, real)
    first = review_choices(ADVICE, fielded, SQUAD, RULES, price=stand.price, score=stand.score)
    again = review_choices(
        ADVICE,
        dataclasses.replace(fielded, starters=tuple(shuffled)),
        SQUAD,
        RULES,
        price=stand.price,
        score=stand.score,
    )
    assert first.choices == again.choices
    assert first.total_cost == again.total_cost
    roles = {player.player_id: player.role for player in SQUAD}
    built = ADVICE
    for choice in first.choices:
        if choice.kind in ("player", "formation"):
            built = applied(built, choice, roles)
    assert set(built.starters) == set(fielded.starters)
    assert built.formation == fielded.formation
