"""mvp-lineup task 4.1: arranging a lineup, with hand-worked cases (design C6; R3.2, R3.3, R3.5)."""

from __future__ import annotations

from collections.abc import Collection

import pytest

from fantadamus.engine.lineup import Arrangement, Candidate, CannotFieldError, arrange
from tests.lineup_data import candidate, full_squad, lineup_rules

RULES = lineup_rules()
SQUAD = full_squad()


def _ids(players: tuple[Candidate, ...], role: str) -> list[int]:
    return [player.player_id for player in players if player.role == role]


def _arranged(
    squad: list[Candidate], *, start: Collection[int] = (), leave_out: Collection[int] = ()
) -> Arrangement:
    return arrange(squad, "3-4-3", RULES, start, leave_out)


def test_the_top_of_each_role_starts_and_the_rest_wait_in_order() -> None:
    arranged = _arranged(SQUAD)
    defenders = _ids((*arranged.starters, *arranged.bench), "D")
    assert defenders == sorted(defenders)  # in this squad, a lower ID has a higher key
    assert len(_ids(arranged.starters, "D")) == 3
    assert arranged.formation == "3-4-3"
    assert arranged.left_off == ()
    assert [player.role for player in arranged.starters] == [
        "P",
        "D",
        "D",
        "D",
        "C",
        "C",
        "C",
        "C",
        "A",
        "A",
        "A",
    ]


def test_no_chance_of_a_rating_sorts_last_whatever_his_value() -> None:
    """Fielding him would waste a place only the bench could fill."""
    out = candidate(99, "A", key=15.0, p_start=0.0, p_cameo=0.0)
    arranged = arrange([*SQUAD, out], "3-4-3", lineup_rules(bench_size=20))
    assert 99 not in _ids(arranged.starters, "A")
    assert _ids(arranged.bench, "A")[-1] == 99
    full_bench = arrange([*SQUAD, out], "3-4-3", RULES)
    assert [player.player_id for player in full_bench.left_off] == [99]  # the first to go from a full bench


def test_a_cameo_counts_as_a_chance_of_a_rating() -> None:
    late = candidate(99, "A", key=15.0, p_start=0.0, p_cameo=0.5)
    assert 99 in _ids(_arranged([*SQUAD, late]).starters, "A")


def _keepers(*players: Candidate) -> list[Candidate]:
    return [*players, *(player for player in SQUAD if player.role != "P")]


def test_the_likelier_starter_of_a_club_is_fielded_even_with_the_lower_key() -> None:
    """An unrated backup can out-rank his club's starter on the key, from the average prior (design C6)."""
    starter = candidate(1, "P", club="torino", p_start=0.9, key=5.5)
    backup = candidate(2, "P", club="torino", p_start=0.1, key=5.6)
    arranged = _arranged(_keepers(backup, starter))
    assert _ids(arranged.starters, "P") == [1]
    assert _ids(arranged.bench, "P") == [2]


def test_clubs_compete_by_their_likelier_starter_and_the_mate_covers_first() -> None:
    starter = candidate(1, "P", club="torino", p_start=0.9, key=5.5)
    backup = candidate(2, "P", club="torino", p_start=0.1, key=9.0)  # his key doesn't lift his club
    other = candidate(3, "P", club="frosinone", p_start=0.9, key=6.0)
    arranged = _arranged(_keepers(starter, backup, other))
    assert _ids(arranged.starters, "P") == [3]
    assert _ids(arranged.bench, "P") == [1, 2]
    stronger = starter.model_copy(update={"key": 6.5})
    arranged = _arranged(_keepers(stronger, backup, other))
    assert _ids(arranged.starters, "P") == [1]
    assert _ids(arranged.bench, "P") == [2, 3]  # the club-mate first, whatever his chance


def test_a_keeper_with_no_chance_comes_last_with_his_club() -> None:
    gone = candidate(1, "P", club="torino", p_start=0.0, p_cameo=0.0, key=0.0)
    other = candidate(3, "P", club="frosinone", p_start=0.5, key=5.0)
    assert _ids(_arranged(_keepers(gone, other)).starters, "P") == [3]


def test_a_small_bench_drops_the_lowest_keys_and_keeps_the_first_of_each_role() -> None:
    """Ten forwards' worth of depth, and a bench of 4: the first of each role stays, whatever his key."""
    weak_first = [
        candidate(1, "P", club="a", key=1.0),
        candidate(2, "P", club="b", key=2.0),
        *(candidate(10 + n, "D", key=9.0 - n / 10) for n in range(4)),
        *(candidate(20 + n, "C", key=9.0 - n / 10) for n in range(5)),
        *(candidate(30 + n, "A", key=9.0 - n / 10) for n in range(4)),
    ]
    arranged = arrange(weak_first, "3-4-3", lineup_rules(bench_size=4))
    assert sorted(player.player_id for player in arranged.bench) == [1, 13, 24, 33]
    assert len(arranged.left_off) == 0
    arranged = arrange([*weak_first, candidate(25, "C", key=5.0)], "3-4-3", lineup_rules(bench_size=4))
    assert [player.player_id for player in arranged.left_off] == [25]


def test_the_bench_runs_by_key_across_roles_and_keeps_each_roles_order() -> None:
    squad = [
        candidate(1, "P", key=9.5),
        candidate(2, "P", key=4.0, club="b"),
        *(candidate(10 + n, "D", key=8.0 - n) for n in range(5)),
        *(candidate(20 + n, "C", key=8.5 - n) for n in range(6)),
        *(candidate(30 + n, "A", key=9.0 - n) for n in range(5)),
    ]
    arranged = arrange(squad, "3-4-3", RULES)
    assert [player.player_id for player in arranged.bench] == [33, 13, 34, 24, 2, 14, 25]
    keys = [player.key for player in arranged.bench]
    assert keys == sorted(keys, reverse=True)


def test_start_goes_in_whatever_his_key() -> None:
    weakest_defender = _ids(_arranged(SQUAD).bench, "D")[-1]
    arranged = _arranged(SQUAD, start={weakest_defender})
    defenders = _ids(arranged.starters, "D")
    assert weakest_defender in defenders
    assert len(defenders) == 3
    assert _ids(arranged.bench, "D") == sorted(_ids(arranged.bench, "D"))


def test_leave_out_stays_available_for_the_bench() -> None:
    best = _ids(_arranged(SQUAD).starters, "A")[0]
    arranged = _arranged(SQUAD, leave_out={best})
    assert best not in _ids(arranged.starters, "A")
    assert len(_ids(arranged.starters, "A")) == 3
    assert best in _ids(arranged.bench, "A")


def test_starting_the_backup_keeper_puts_his_mate_on_the_bench_first() -> None:
    backup = _ids(_arranged(SQUAD).bench, "P")[0]
    arranged = _arranged(SQUAD, start={backup})
    assert _ids(arranged.starters, "P") == [backup]
    assert _ids(arranged.bench, "P")[0] != backup


@pytest.mark.parametrize(
    ("start", "leave_out", "reason"),
    [
        ({999}, set(), "isn't in the squad"),
        (set(), {999}, "isn't in the squad"),
        ({4}, {4}, "both start and be left out"),
        ({4, 5, 6, 7}, set(), "3-4-3 has 3 defender places, and 4 are told to start"),
        ({1, 2}, set(), "3-4-3 has 1 keeper places, and 2 are told to start"),
    ],
)
def test_what_cant_be_fielded_is_refused_with_the_reason(
    start: set[int], leave_out: set[int], reason: str
) -> None:
    with pytest.raises(CannotFieldError, match=reason):
        _arranged(SQUAD, start=start, leave_out=leave_out)


def test_a_role_too_short_for_the_formation_is_refused() -> None:
    without = [player for player in SQUAD if player.role != "A"][:-1]
    with pytest.raises(CannotFieldError, match="3-4-3 needs 3 forwards, and 0 can play"):
        _arranged(without)
    everyone_left_out = {player.player_id for player in SQUAD if player.role == "P"}
    with pytest.raises(CannotFieldError, match="1 keepers, and 0 can play"):
        _arranged(SQUAD, leave_out=everyone_left_out)
