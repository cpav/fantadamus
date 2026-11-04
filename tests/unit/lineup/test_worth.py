"""Task 1.1: a choice's margin is what it's worth (design C1; R8.1, R8.2)."""

from __future__ import annotations

import pytest

from fantadamus.engine import rank
from fantadamus.engine.rank import Option

DOUBTFUL = Option(
    name="X", p_start=0.45, p_cameo=0.10, e_start=7.6, e_cameo=6.0
)  # key 7.309, 55% to get a rating
CERTAIN = Option(
    name="Y", p_start=0.95, p_cameo=0.02, e_start=6.6, e_cameo=6.0
)  # key 6.588, 97% to get a rating


def _in_order(first: Option, second: Option) -> float:
    """What a place is worth with `first` fielded and `second` first on the bench: the bench player comes in
    only when the starter gets no rating, worked out by hand from the ordering rule's own terms."""
    chance_first = first.p_start + first.p_cameo
    chance_second = second.p_start + second.p_cameo
    return chance_first * rank.key(**first.figures()) + (1 - chance_first) * chance_second * rank.key(
        **second.figures()
    )


def test_margin_is_what_the_choice_is_worth() -> None:
    verdict = rank.verdict(CERTAIN, DOUBTFUL)
    assert (verdict.first, verdict.second) == ("X", "Y")  # the order still follows the key
    assert verdict.key_margin == pytest.approx(7.309 - 6.588, abs=0.002)
    assert verdict.margin == pytest.approx(_in_order(DOUBTFUL, CERTAIN) - _in_order(CERTAIN, DOUBTFUL))
    assert verdict.margin == pytest.approx(0.385, abs=0.002)
    assert verdict.label == "lean"  # the difference in keys alone would say "clear"


def test_two_certain_starters_keep_the_whole_difference() -> None:
    a = Option(name="A", p_start=1.0, p_cameo=0.0, e_start=7.0, e_cameo=0.0)
    b = Option(name="B", p_start=1.0, p_cameo=0.0, e_start=6.0, e_cameo=0.0)
    verdict = rank.verdict(a, b)
    assert verdict.margin == pytest.approx(1.0)
    assert verdict.key_margin == pytest.approx(1.0)
    assert verdict.label == "clear"


def test_no_chance_of_a_rating() -> None:
    """R8.2: he won't play, so the advice stays, with the difference in keys as before."""
    out = Option(name="Fuori", p_start=0.0, p_cameo=0.0, e_start=7.0, e_cameo=5.5)
    verdict = rank.verdict(out, CERTAIN)
    assert (verdict.first, verdict.first_plays, verdict.second_plays) == ("Y", True, False)
    assert verdict.margin == pytest.approx(rank.key(**CERTAIN.figures()))
    assert verdict.key_margin == verdict.margin
    assert verdict.label == "clear"


def test_neither_can_get_a_rating() -> None:
    a = Option(name="A", p_start=0.0, p_cameo=0.0, e_start=7.0, e_cameo=5.5)
    b = Option(name="B", p_start=0.0, p_cameo=0.0, e_start=6.0, e_cameo=5.5)
    verdict = rank.verdict(a, b)
    assert (verdict.margin, verdict.key_margin, verdict.label) == (0.0, 0.0, "coin flip")
    assert not verdict.first_plays


def test_covered_keepers_have_no_margin_of_either_kind() -> None:
    a = Option(name="A", p_start=0.9, p_cameo=0.0, e_start=6.2, e_cameo=0.0)
    b = Option(name="B", p_start=0.1, p_cameo=0.0, e_start=6.0, e_cameo=0.0)
    verdict = rank.covering(a, b)
    assert (verdict.margin, verdict.key_margin, verdict.label) == (0.0, 0.0, "covered")
