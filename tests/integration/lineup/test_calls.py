"""mvp-lineup tasks 6.1 and 6.3: the calls that matter, and a two-role question pointing to the lineup (design
C8; R3.4, R5.2, R6.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fantadamus.engine.lineup import Arrangement, Candidate, arrange
from fantadamus.engine.rank import Option, label, verdict
from fantadamus.engine.simulate import Simulated
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.mcp.tools.lineup import formation_call, place_calls
from tests.lineup_data import candidate, lineup_rules
from tests.lineup_harness import READ, a_round
from tests.xy_harness import ask, collect, set_classic, tools

pytestmark = pytest.mark.anyio


def _simulated(formation: str, mean: float, high: float) -> Simulated:
    return Simulated(
        formation=formation, mean=mean, low=mean - 8, high=high, fantasy_goals=1.0, thresholds=[]
    )


def _squad() -> list[Candidate]:
    return [
        candidate(1, "P", key=6.0),
        *(candidate(10 + n, "D", key=7.0 - n / 2) for n in range(5)),
        *(candidate(20 + n, "C", key=7.0 - n / 2) for n in range(6)),
        *(candidate(30 + n, "A", key=8.0 - n / 2) for n in range(4)),
    ]


def _arranged(*formations: str) -> dict[str, Arrangement]:
    return {formation: arrange(_squad(), formation, lineup_rules()) for formation in formations}


def test_a_formation_call_names_who_it_comes_down_to() -> None:
    """From 3-4-3 to 4-4-2: the 3rd forward (key 7.0) against the 4th defender (key 5.5)."""
    call = formation_call(
        [_simulated("3-4-3", 72.0, 80.0), _simulated("4-4-2", 71.0, 79.0)], _arranged("3-4-3", "4-4-2")
    )
    assert call is not None
    assert (call.kind, call.first, call.second) == ("formation", "3-4-3", "4-4-2")
    assert call.worth == pytest.approx(1.0)
    assert call.label == "clear"
    assert call.ceiling is None
    assert "A32 7.0" in call.text
    assert "D13 5.5" in call.text
    assert "A30" not in call.text  # both formations field him, so it doesn't come down to him
    assert "D10" not in call.text


@pytest.mark.parametrize(
    ("second_mean", "second_high", "expected_label", "ceiling"),
    [
        (71.9, 79.0, "coin flip", "3-4-3"),  # the recommended one also has the higher ceiling
        (71.9, 83.0, "coin flip", "4-4-2"),  # the other one does
        (71.5, 83.0, "lean", None),  # far enough apart, so the ceiling isn't the question
    ],
)
def test_coin_flip_names_the_ceiling(
    second_mean: float, second_high: float, expected_label: str, ceiling: str | None
) -> None:
    """R3.4: within about 0.15 points, and variance helps an underdog."""
    call = formation_call(
        [_simulated("3-4-3", 72.0, 80.0), _simulated("4-4-2", second_mean, second_high)],
        _arranged("3-4-3", "4-4-2"),
    )
    assert call is not None
    assert call.label == expected_label
    assert call.ceiling == ceiling
    if ceiling:
        assert f"{ceiling} has the higher ceiling" in call.text


def test_the_gap_counts_whichever_way_round_they_are() -> None:
    """Head to head, the formation with more fantasy goals can have the lower mean."""
    call = formation_call(
        [_simulated("3-4-3", 71.0, 80.0), _simulated("4-4-2", 72.0, 79.0)], _arranged("3-4-3", "4-4-2")
    )
    assert call is not None
    assert call.worth == pytest.approx(1.0)


def test_one_formation_has_no_formation_call() -> None:
    assert formation_call([_simulated("3-4-3", 72.0, 80.0)], _arranged("3-4-3")) is None


def _option(player: Candidate, *, p_start: float | None = None) -> Option:
    chance = player.p_start if p_start is None else p_start
    return Option(name=player.name, p_start=chance, p_cameo=0.0, e_start=player.key, e_cameo=0.0)


def _options(arranged: Arrangement) -> dict[int, Option]:
    return {player.player_id: _option(player) for player in (*arranged.starters, *arranged.bench)}


def test_place_calls_are_the_closest_choices_with_what_each_is_worth() -> None:
    """A role's last starter against the player behind him, closest first, and at most two."""
    squad = [
        candidate(1, "P", key=6.0, p_start=0.9, p_cameo=0.0, club="a"),
        candidate(2, "P", key=5.0, p_start=0.9, p_cameo=0.0, club="b"),
        *(candidate(10 + n, "D", key=7.0 - n, p_start=0.9, p_cameo=0.0) for n in range(4)),
        *(candidate(20 + n, "C", key=7.0 - n / 10, p_start=0.9, p_cameo=0.0) for n in range(5)),
        *(candidate(30 + n, "A", key=8.0 - n / 2, p_start=0.9, p_cameo=0.0) for n in range(4)),
    ]
    arranged = arrange(squad, "3-4-3", lineup_rules())
    calls = place_calls(arranged, _options(arranged))
    assert [(call.first, call.second) for call in calls] == [("C23", "C24"), ("A32", "A33")]
    closest = calls[0]
    assert closest.kind == "place"
    # By hand: 0.9 x 0.9 x (6.7 - 6.6).
    assert closest.worth == pytest.approx(0.081)
    assert closest.label == label(closest.worth) == "coin flip"
    assert "4th midfielder" in closest.text
    assert "C23 6.7" in closest.text
    assert closest.worth == pytest.approx(verdict(_option(squad[9]), _option(squad[10])).margin)


def test_a_keepers_call_skips_his_club_mate() -> None:
    """His club-mate covers him rather than competes: the choice is against another club's keeper."""
    squad = [
        candidate(1, "P", key=6.0, p_start=0.9, p_cameo=0.0, club="a"),
        candidate(2, "P", key=5.9, p_start=0.1, p_cameo=0.0, club="a"),
        candidate(3, "P", key=5.9, p_start=0.9, p_cameo=0.0, club="b"),
        *(candidate(10 + n, "D", key=7.0 - n) for n in range(4)),
        *(candidate(20 + n, "C", key=7.0 - n) for n in range(5)),
        *(candidate(30 + n, "A", key=8.0 - n) for n in range(4)),
    ]
    arranged = arrange(squad, "3-4-3", lineup_rules())
    keeper = next(call for call in place_calls(arranged, _options(arranged)) if call.first == "P1")
    assert keeper.second == "P3"


def test_no_call_against_someone_who_wont_play() -> None:
    squad = [
        candidate(1, "P", key=6.0, p_start=0.9, p_cameo=0.0),
        *(candidate(10 + n, "D", key=7.0, p_start=0.9, p_cameo=0.0) for n in range(3)),
        candidate(13, "D", key=0.0, p_start=0.0, p_cameo=0.0),
        *(candidate(20 + n, "C", key=7.0, p_start=0.9, p_cameo=0.0) for n in range(4)),
        *(candidate(30 + n, "A", key=8.0, p_start=0.9, p_cameo=0.0) for n in range(3)),
    ]
    arranged = arrange(squad, "3-4-3", lineup_rules())
    assert place_calls(arranged, _options(arranged)) == []


async def test_calls_that_matter(tmp_path: Path) -> None:
    """R5.2: from one call, the formation first and then the closest choices: two or three in all."""
    async with a_round(tmp_path) as here:
        lineup = (await here.ask())["lineup"]
    calls = lineup["calls"]
    assert 2 <= len(calls) <= 3
    assert calls[0]["kind"] == "formation"
    assert calls[0]["first"] == lineup["formation"]
    assert calls[0]["second"] == lineup["formations"][1]["formation"]
    places = calls[1:]
    assert all(call["kind"] == "place" for call in places)
    worths = [call["worth"] for call in places]
    assert worths == sorted(worths)
    starters = {part["name"]: part["role"] for part in lineup["starters"]}
    bench = {part["name"]: part["role"] for part in lineup["bench"]}
    for call in places:
        assert starters[call["first"]] == bench[call["second"]]


async def test_two_roles_with_a_squad(tmp_path: Path) -> None:
    """R6.2: `best_lineup` answers it, as the formation call; `compare_players` itself stays as it is."""
    async with a_round(tmp_path) as here:
        result = await ask(here.client, "Alfa Uno", "Beta Nove")
    assert result["status"] == "outlooks", result
    assert result["answer"]["verdict"] is None
    assert "best_lineup" in result["message"]
    assert "formation call" in result["message"]
    assert "set_squad" not in result["message"]  # the squad is already there


async def test_two_roles_without_a_squad_says_how_to_get_there(tmp_path: Path) -> None:
    async with a_round(tmp_path, squad=False) as here:
        result = await ask(here.client, "Alfa Uno", "Beta Nove")
    assert result["status"] == "outlooks", result
    assert "set_squad" in result["message"]


async def test_two_of_one_role_are_unchanged(tmp_path: Path) -> None:
    async with tools(LakeStore(tmp_path)) as client:
        await set_classic(client)
        await collect(client, READ)
        result = await ask(client)
    assert result["status"] == "answer"
    assert "best_lineup" not in result["message"]
