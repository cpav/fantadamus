"""mvp-alerts task 1.2: what changed between two calls, and what doesn't count (design C1; R2.1, R2.3)."""

from __future__ import annotations

from fantadamus.domains.alerts import Change, changes
from tests.alerts_data import LATER, ROLES, a_call, moved


def test_each_kind_of_change() -> None:
    before = a_call()
    after = a_call(
        starters=[1, 11, 3, 4, 5, 6, 7, 13, 8, 9, 14],  # 11 for 2, both defenders
        bench=[10, 12, 2],
        captain=9,
        vice=8,
    )
    assert changes(before, after, ROLES) == [
        Change("swap", now=11, before=2, role="D"),
        Change("captain", now=9, before=8),
        Change("vice", now=8, before=9),
        Change("bench", now=12, before=11, role="D"),
    ]


def test_a_new_formation_leaves_lone_changes() -> None:
    before = a_call()
    after = a_call(formation="4-3-3", starters=[1, 2, 3, 4, 11, 5, 6, 7, 8, 9, 14], bench=[10, 13, 12])
    assert changes(before, after, ROLES) == [
        Change("in", now=11, role="D"),
        Change("out", before=13, role="C"),
        Change("formation", formations=("3-4-3", "4-3-3")),
        Change("bench", now=12, before=11, role="D"),
    ]


def test_a_player_without_a_role_is_a_lone_change() -> None:
    before = a_call()
    after = a_call(starters=[1, 2, 3, 4, 5, 6, 7, 13, 8, 9, 99])
    assert changes(before, after, ROLES) == [Change("out", before=14, role="A"), Change("in", now=99)]


def test_chances_alone_change_nothing() -> None:
    before = a_call()
    after = moved(before, chances=dict.fromkeys(ROLES, 0.1), at=LATER)
    assert changes(before, after, ROLES) == []


def test_lower_on_the_bench_changes_nothing() -> None:
    assert changes(a_call(bench=[10, 11, 12, 14]), a_call(bench=[14, 10, 11, 12]), ROLES) == []
    assert changes(a_call(bench=[11, 10, 12]), a_call(bench=[11, 12, 10]), ROLES) == []


def test_a_captain_the_league_doesnt_have_isnt_compared() -> None:
    assert changes(a_call(captain=None, vice=None), a_call(), ROLES) == []


def test_a_role_with_no_one_on_the_bench_isnt_compared() -> None:
    assert changes(a_call(bench=[10]), a_call(bench=[10, 11]), ROLES) == []
