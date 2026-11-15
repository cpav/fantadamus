"""mvp-alerts task 1.1: the call an alert compares, from a lineup's parts and from a logged answer (design C1;
R2.1)."""

from __future__ import annotations

from fantadamus.domains.alerts import call_of_advice
from fantadamus.domains.review import Advice
from tests.alerts_data import AT, ROLES, a_call


def test_a_call_from_a_lineup() -> None:
    call = a_call()
    assert call.round == 12
    assert call.formation == "3-4-3"
    assert call.starters == frozenset({1, 2, 3, 4, 5, 6, 7, 13, 8, 9, 14})
    assert (call.captain, call.vice) == (8, 9)
    assert call.chances[11] == 0.8
    assert call.at == AT


def test_the_first_on_the_bench_in_each_role() -> None:
    call = a_call(bench=[12, 11, 10])
    assert dict(call.first_on_bench) == {"D": 12, "P": 10}
    assert dict(a_call(bench=[]).first_on_bench) == {}


def test_a_player_whose_role_isnt_known_has_no_bench_place() -> None:
    assert dict(a_call(bench=[99, 11]).first_on_bench) == {"D": 11}


def test_a_call_from_a_logged_answer() -> None:
    advice = Advice("4-4-2", [1, 2, 3, 4, 11, 5, 6, 7, 13, 8, 9], [10, 12, 14], 9, 8, AT, chances={8: 0.9})
    call = call_of_advice(advice, round=12, roles=ROLES)
    assert call.formation == "4-4-2"
    assert 11 in call.starters
    assert dict(call.first_on_bench) == {"P": 10, "D": 12, "A": 14}
    assert (call.captain, call.vice) == (9, 8)
    assert call.chances == {8: 0.9}
    assert call.at == AT


def test_an_override_is_compared_by_its_advice() -> None:
    """`last_advice` already gives the advice behind an override; the call is that advice."""
    advice = Advice("3-4-3", [1, 2, 3, 4, 5, 6, 7, 13, 8, 9, 14], [10, 11, 12], None, None, AT)
    call = call_of_advice(advice, round=12, roles=ROLES)
    assert call.starters == a_call().starters
    assert call.captain is None
