"""An invented review for the decision tests: a squad, the advice, and stand-ins for the simulation and the
real score, so every expected cost and real result can be worked out by hand."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from fantadamus.domains.review import Picked, RealScore
from fantadamus.engine.lineup import Arrangement, arrange
from fantadamus.engine.simulate import Simulated
from tests.lineup_data import full_squad, lineup_rules

SQUAD = full_squad()  # keepers 1 to 3, defenders 4 to 11, midfielders 12 to 19, forwards 20 to 25
RULES = lineup_rules()  # role for role, five substitutions, a bench of 14
ARRANGED = arrange(SQUAD, "3-4-3", RULES)
ADVICE = Picked(
    formation="3-4-3",
    starters=tuple(player.player_id for player in ARRANGED.starters),
    bench=tuple(player.player_id for player in ARRANGED.bench),
    captain=20,
    vice=12,
)
BEST_PAIR = (20, 21)
"""Who the stand-in simulation picks when no captain is named."""


def first_of(bench: Sequence[int], role_ids: range) -> int | None:
    return next((player for player in bench if player in role_ids), None)


class Stand:
    """A stand-in simulation and real score: each starter's value adds up; a captain adds his bonus; the first
    midfielder on the bench adds a little."""

    def __init__(
        self,
        expected: Mapping[int, float],
        real: Mapping[int, float],
        *,
        captain_expected: Mapping[int, float],
        captain_real: Mapping[int, float],
        bench_expected: Mapping[int, float],
        bench_real: Mapping[int, float],
        unknown: Sequence[int] = (),
        moves: Sequence[tuple[int, int]] = (),
    ) -> None:
        self.expected, self.real = expected, real
        self.captain_expected, self.captain_real = captain_expected, captain_real
        self.bench_expected, self.bench_real = bench_expected, bench_real
        self.unknown, self.moves = list(unknown), list(moves)
        self.priced: list[list[Arrangement]] = []

    def price(self, arrangements: Sequence[Arrangement]) -> list[Simulated]:
        self.priced.append(list(arrangements))
        found = []
        for arranged in arrangements:
            captain = arranged.captain if arranged.captain is not None else BEST_PAIR[0]
            vice = (
                arranged.vice if arranged.captain is not None and arranged.vice is not None else BEST_PAIR[1]
            )
            starters = [player.player_id for player in arranged.starters]
            bench = [player.player_id for player in arranged.bench]
            mean = (
                sum(self.expected.get(player, 6.0) for player in starters)
                + self.captain_expected.get(captain, 0.0)
                + self.bench_expected.get(first_of(bench, range(12, 20)) or 0, 0.0)
            )
            found.append(
                Simulated(
                    formation=arranged.formation,
                    mean=mean,
                    low=mean - 6.0,
                    high=mean + 6.0,
                    fantasy_goals=0.0,
                    thresholds=[],
                    captain=captain,
                    vice=vice,
                )
            )
        return found

    def score(self, arranged: Arrangement, captain: int | None, vice: int | None) -> RealScore:
        starters = [player.player_id for player in arranged.starters]
        bench = [player.player_id for player in arranged.bench]
        blocked = [player for player in self.unknown if player in starters]
        if blocked:
            return RealScore(None, None, {}, [], {}, blocked, [])
        total = (
            sum(self.real.get(player, 6.0) for player in starters)
            + self.captain_real.get(captain or 0, 0.0)
            + self.bench_real.get(first_of(bench, range(12, 20)) or 0, 0.0)
        )
        return RealScore(total, 1, {}, list(self.moves), {}, [], [])
