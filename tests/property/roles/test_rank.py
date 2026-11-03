"""mvp-roles P7: the verdict for two players of the same role doesn't depend on the order they're asked in
(design C8; R4.1)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.engine import keepers, outfield
from fantadamus.engine.constants import ROLE_PRIORS
from fantadamus.engine.keepers import KeeperInputs
from fantadamus.engine.outfield import OutfieldInputs
from fantadamus.engine.rank import Scoring, Verdict
from tests.roles_data import keeper
from tests.roles_data import outfield as player

CLASSIC = Scoring(goal=3, penalty_scored=3, assist=1, yellow=-0.5, clean_sheet=1, goal_conceded=-1)
chance = st.floats(min_value=0, max_value=0.95)
NAMES = ("First", "Second")
outfielders = st.builds(
    lambda mantra_role, goals, p_start, xg: player(
        "C",
        mantra_role,
        appearances=8,
        rated_appearances=8,
        average_rating=6.2,
        goals=goals,
        p_start=p_start,
        team_xg=xg,
    ),
    st.sampled_from(sorted(ROLE_PRIORS)),
    st.integers(0, 8),
    chance,
    st.floats(0.3, 3.0),
)
goalkeepers = st.builds(
    lambda club, rating, p_start, xg: keeper(
        club=club, average_rating=rating, p_start=p_start, opponent_xg=xg
    ),
    st.sampled_from(["alfa", "beta"]),
    st.floats(5.5, 7.5),
    chance,
    st.floats(0.3, 3.0),
)


def _same(one: Verdict, other: Verdict) -> None:
    assert (one.first, one.second, one.label) == (other.first, other.second, other.label)
    assert abs(one.margin - other.margin) < 1e-12


@given(outfield_pair=st.tuples(outfielders, outfielders), keeper_pair=st.tuples(goalkeepers, goalkeepers))
def test_p7_order_asked_doesnt_matter(
    outfield_pair: tuple[OutfieldInputs, OutfieldInputs], keeper_pair: tuple[KeeperInputs, KeeperInputs]
) -> None:
    a, b = (
        inputs.model_copy(update={"name": name}) for inputs, name in zip(outfield_pair, NAMES, strict=True)
    )
    _same(outfield.compare(a, b, CLASSIC).verdict, outfield.compare(b, a, CLASSIC).verdict)
    c, d = (inputs.model_copy(update={"name": name}) for inputs, name in zip(keeper_pair, NAMES, strict=True))
    _same(keepers.compare(c, d, CLASSIC).verdict, keepers.compare(d, c, CLASSIC).verdict)
