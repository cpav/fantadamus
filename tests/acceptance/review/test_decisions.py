"""AT-4 and AT-5 of mvp-review: each decision against the advice, with its expected cost at the lock and its
real result, by hand on stand-ins; judged by the cost; following the advice; a replayed advice (design C6;
R3.1 to R3.5)."""

from __future__ import annotations

import dataclasses

from fantadamus.domains.review import Choice, Picked, applied, review_choices
from tests.review_choices import ADVICE, ARRANGED, RULES, SQUAD, Stand

# The user started D7 for D6, played 4-4-2 with D8 for A22, put C17 first on the bench, and made 21 captain
# with 20 as his vice.
FIELDED = Picked(
    formation="4-4-2",
    starters=(1, 4, 5, 7, 8, 12, 13, 14, 15, 20, 21),
    bench=(2, 3, 6, 9, 10, 11, 17, 16, 18, 19, 22, 23, 24, 25),
    captain=21,
    vice=20,
)


def _stand(
    *,
    expected: dict[int, float] | None = None,
    real: dict[int, float] | None = None,
    unknown: tuple[int, ...] = (),
    moves: tuple[tuple[int, int], ...] = ((13, 17),),  # a midfielder came on: the bench order mattered
    bench_expected: dict[int, float] | None = None,
) -> Stand:
    return Stand(
        {6: 6.5, 7: 6.2, 8: 6.1, 22: 7.0} if expected is None else expected,
        {6: 5.0, 7: 7.0, 8: 6.0, 22: 9.0} if real is None else real,
        captain_expected={20: 2.0, 21: 1.0},
        captain_real={20: 0.5, 21: 2.5},
        bench_expected={16: 0.1} if bench_expected is None else bench_expected,
        bench_real={17: 1.0},
        unknown=unknown,
        moves=moves,
    )


def test_at4_each_decision_by_hand() -> None:
    stand = _stand()
    reviewed = review_choices(ADVICE, FIELDED, SQUAD, RULES, price=stand.price, score=stand.score)
    found = [(choice.kind, choice.fielded, choice.advised) for choice in reviewed.choices]
    assert found == [
        ("player", (7,), (6,)),
        ("formation", (8,), (22,)),
        ("bench", (17,), (16,)),
        ("bench", (22,), (23,)),  # on the advice's bench, with his swaps made, 23 would have come first
        ("captain", (21, 20), (20, 21)),  # against the best pair for the eleven he fielded
    ]
    costs = [round(choice.expected_cost, 6) for choice in reviewed.choices]
    assert costs == [0.3, 0.9, 0.1, 0.0, 1.0]  # 6.5 - 6.2, 7 - 6.1, the first midfielder off the bench, 2 - 1
    assert round(reviewed.total_cost, 6) == 2.3
    assert len(stand.priced) == 1  # one simulation for all of it
    gains = [choice.real_gain for choice in reviewed.choices]
    assert gains == [2.0, -3.0, 1.0, 0.0, 2.0]  # 7 - 5, 6 - 9, the first midfielder off the bench, 2.5 - 0.5
    assert reviewed.total_gain == 2.0
    assert [choice.mattered for choice in reviewed.choices] == [None, None, True, False, None]
    assert (reviewed.advice_real.total, reviewed.fielded_real.total) == (68.5, 70.5)
    assert not reviewed.replayed
    # The advice goes to the engine as the engine arranged it, with the pair it named.
    assert stand.priced[0][0] == ARRANGED.model_copy(update={"captain": 20, "vice": 12})


def test_at4_the_choices_made_on_the_advice_give_the_eleven_fielded() -> None:
    """The swaps, then the bench, then the captain, as listed: the eleven, its formation, its pair, and each
    role's first substitute are the ones fielded."""
    reviewed = review_choices(ADVICE, FIELDED, SQUAD, RULES, price=_stand().price, score=_stand().score)
    roles = {player.player_id: player.role for player in SQUAD}
    built = ADVICE
    for choice in reviewed.choices:
        built = applied(built, choice, roles)
    assert (set(built.starters), built.formation) == (set(FIELDED.starters), FIELDED.formation)
    assert (built.captain, built.vice) == (FIELDED.captain, FIELDED.vice)
    firsts = [
        next(p for p in lineup.bench if roles[p] == role) for lineup in (built, FIELDED) for role in "PDCA"
    ]
    assert firsts[:4] == firsts[4:]


def test_at4_a_bench_order_that_never_came_into_play() -> None:
    reviewed = review_choices(
        ADVICE, FIELDED, SQUAD, RULES, price=_stand(moves=()).price, score=_stand(moves=()).score
    )
    bench = next(choice for choice in reviewed.choices if choice.kind == "bench")
    assert bench.mattered is False


def test_at4_a_player_whose_round_isnt_known() -> None:
    stand = _stand(unknown=(7,))
    reviewed = review_choices(ADVICE, FIELDED, SQUAD, RULES, price=stand.price, score=stand.score)
    player = reviewed.choices[0]
    assert (player.real_gain, player.unknown) == (None, (7,))
    assert reviewed.total_gain is None
    assert reviewed.choices[1].real_gain == -3.0  # the formation's result doesn't need him


def test_at4_judged_by_the_cost() -> None:
    """The cost decides the judgement, whatever the round did: the swap cost 0.3 and gained 2 this round."""
    reviewed = review_choices(ADVICE, FIELDED, SQUAD, RULES, price=_stand().price, score=_stand().score)
    assert [choice.judged for choice in reviewed.choices] == ["cost", "cost", "even", "even", "cost"]
    better = _stand(expected={6: 6.0, 7: 6.5, 8: 6.1, 22: 7.0})
    gained = review_choices(ADVICE, FIELDED, SQUAD, RULES, price=better.price, score=better.score)
    assert gained.choices[0].judged == "gain"


def test_at5_following_the_advice() -> None:
    """No decisions; the real score against the expected one and its range."""
    stand = _stand(real={})
    reviewed = review_choices(ADVICE, ADVICE, SQUAD, RULES, price=stand.price, score=stand.score)
    assert reviewed.choices == []
    assert (reviewed.total_cost, reviewed.total_gain) == (0.0, 0.0)
    assert reviewed.advice_real.total == 66.5  # eleven 6s and the captain's 0.5
    assert reviewed.position == "inside"  # 66.5 against 69.6 expected, 63.6 to 75.6
    high = _stand(real={22: 20.0})
    assert (
        review_choices(ADVICE, ADVICE, SQUAD, RULES, price=high.price, score=high.score).position == "above"
    )
    low = _stand(real={1: 0.0, 4: 0.0})
    assert review_choices(ADVICE, ADVICE, SQUAD, RULES, price=low.price, score=low.score).position == "below"
    for real in ({1: 3.0}, {22: 15.0}):  # exactly on the range's ends, 63.5 and 75.5: still inside
        edge = _stand(real=real, bench_expected={})
        assert (
            review_choices(ADVICE, ADVICE, SQUAD, RULES, price=edge.price, score=edge.score).position
            == "inside"
        )


def test_at5_replayed_when_none_was_asked() -> None:
    stand = _stand()
    reviewed = review_choices(
        dataclasses.replace(ADVICE),
        FIELDED,
        SQUAD,
        RULES,
        price=stand.price,
        score=stand.score,
        replayed=True,
    )
    assert reviewed.replayed
    assert isinstance(reviewed.choices[0], Choice)


def _swapped(*swaps: tuple[int, int], bench: tuple[int, ...] | None = None) -> Picked:
    """The advice with each (advised, fielded) starter swapped, the fielded one's bench place going to the
    other."""
    into = dict(swaps)
    back = {new: old for old, new in swaps}
    return dataclasses.replace(
        ADVICE,
        starters=tuple(into.get(player, player) for player in ADVICE.starters),
        bench=bench if bench is not None else tuple(back.get(player, player) for player in ADVICE.bench),
    )


def test_at4_pairs_go_best_first() -> None:
    """Two defenders swapped: the best dropped is shown against the best brought in."""
    fielded = _swapped((5, 9), (6, 10))
    reviewed = review_choices(ADVICE, fielded, SQUAD, RULES, price=_stand().price, score=_stand().score)
    found = [(choice.kind, choice.fielded, choice.advised) for choice in reviewed.choices]
    assert found == [("player", (9,), (5,)), ("player", (10,), (6,))]
    keys = {6: 9.95, 10: 9.9}  # now the 6 dropped and the 10 brought in are the best of each
    squad = [player.model_copy(update={"key": keys.get(player.player_id, player.key)}) for player in SQUAD]
    keyed = review_choices(ADVICE, fielded, squad, RULES, price=_stand().price, score=_stand().score)
    paired = [(choice.fielded, choice.advised) for choice in keyed.choices]
    assert paired == [((10,), (6,)), ((9,), (5,))]  # by key, not by number


def test_at4_a_bench_without_a_role() -> None:
    """A bench with no keeper has no first keeper to compare."""
    fielded = dataclasses.replace(
        ADVICE, bench=tuple(player for player in ADVICE.bench if player not in (2, 3))
    )
    reviewed = review_choices(ADVICE, fielded, SQUAD, RULES, price=_stand().price, score=_stand().score)
    assert reviewed.choices == []


def test_at4_a_bench_choice_on_the_eleven_fielded() -> None:
    """He started 8 for 6 and put 6 first among the defenders on the bench, where the advice's order, with
    his swap made, puts 7: after the swap, the bench choice gives his bench."""
    bench = (2, 3, 6, 23, 7, 16, 24, 9, 17, 25, 10, 18, 11, 19)
    fielded = _swapped((6, 8), bench=bench)
    reviewed = review_choices(ADVICE, fielded, SQUAD, RULES, price=_stand().price, score=_stand().score)
    found = [(choice.kind, choice.fielded, choice.advised) for choice in reviewed.choices]
    assert found == [("player", (8,), (6,)), ("bench", (6,), (7,))]
    roles = {player.player_id: player.role for player in SQUAD}
    built = ADVICE
    for choice in reviewed.choices:
        built = applied(built, choice, roles)
    assert (built.starters, built.bench) == (fielded.starters, fielded.bench)


def test_at4_a_swap_that_takes_off_the_captain() -> None:
    """Applied on its own, a swap of the advice's captain leaves the captain and vice to the simulation; a
    swap of the vice keeps the captain."""
    roles = {player.player_id: player.role for player in SQUAD}
    without_captain = applied(ADVICE, Choice("player", (23,), (20,)), roles)
    assert (without_captain.captain, without_captain.vice) == (None, None)
    without_vice = applied(ADVICE, Choice("player", (16,), (12,)), roles)
    assert (without_vice.captain, without_vice.vice) == (20, None)
    elsewhere = applied(ADVICE, Choice("player", (7,), (6,)), roles)
    assert (elsewhere.captain, elsewhere.vice) == (20, 12)
