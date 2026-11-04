"""P1 and P2: arranging a lineup (design C6; R3.2, R3.3)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.contracts.types import Role
from fantadamus.contracts.xy.league import formation_lines
from fantadamus.engine.lineup import Candidate, arrange
from tests.lineup_data import FORMATIONS, candidate, lineup_rules

_SHAPE: tuple[tuple[Role, int], ...] = (("P", 3), ("D", 6), ("C", 6), ("A", 4))
"""Enough for every formation, with at least one of each role left for the bench."""
_PLAYER = st.tuples(st.integers(30, 150), st.sampled_from((0.0, 0.1, 0.5, 0.9, 1.0)), st.integers(0, 2))


def _squad(raw: list[tuple[int, float, int]]) -> list[Candidate]:
    """As the ordering rule sees them: a player with no chance of a rating has a key of 0 (method §A3)."""
    roles = [role for role, count in _SHAPE for _ in range(count)]
    return [
        candidate(
            number + 1,
            role,
            key=tenths / 10 if p_start else 0.0,
            p_start=p_start,
            p_cameo=0.0,
            club=f"club{club}",
        )
        for number, (role, (tenths, p_start, club)) in enumerate(zip(roles, raw, strict=True))
    ]


_COUNT = sum(count for _, count in _SHAPE)
_SQUADS = st.lists(_PLAYER, min_size=_COUNT, max_size=_COUNT).map(_squad)


@given(squad=_SQUADS, formation=st.sampled_from(FORMATIONS), bench=st.integers(4, 14))
def test_p1_fills_the_formation(squad: list[Candidate], formation: str, bench: int) -> None:
    arranged = arrange(squad, formation, lineup_rules(bench_size=bench))
    defenders, midfielders, forwards = formation_lines(formation)
    fielded = [player.role for player in arranged.starters]
    assert (fielded.count("P"), fielded.count("D"), fielded.count("C"), fielded.count("A")) == (
        1,
        defenders,
        midfielders,
        forwards,
    )
    everyone = [*arranged.starters, *arranged.bench, *arranged.left_off]
    assert sorted(player.player_id for player in everyone) == sorted(player.player_id for player in squad)
    assert len(arranged.bench) <= bench
    for role in ("D", "C", "A"):
        starters = [player.key for player in arranged.starters if player.role == role]
        bench_keys = [player.key for player in arranged.bench if player.role == role]
        assert not bench_keys or min(starters) >= max(bench_keys)
        assert bench_keys == sorted(bench_keys, reverse=True)
        assert [player.role for player in arranged.bench].count(role) >= 1  # first in his role is kept


@given(squad=_SQUADS, formation=st.sampled_from(FORMATIONS))
def test_p2_one_keeper_of_a_club(squad: list[Candidate], formation: str) -> None:
    arranged = arrange(squad, formation, lineup_rules())
    [fielded] = [player for player in arranged.starters if player.role == "P"]
    keepers = [player for player in squad if player.role == "P"]
    mates = [player for player in keepers if player.club == fielded.club and player != fielded]
    assert all(fielded.p_start >= mate.p_start for mate in mates)  # the likelier starter of his club
    bench_keepers = [player for player in arranged.bench if player.role == "P"]
    if mates:
        assert bench_keepers[0].club == fielded.club  # the slot is covered first
