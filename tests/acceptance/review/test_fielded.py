"""AT-1 of mvp-review: what the user fielded, by name or "as advised"; a lineup the league couldn't field
refused; saving again replacing; a league-mate's team kept apart; all of it in private storage (design C4;
R1.1 to R1.4, R5.4)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.domains.review import Advice
from fantadamus.league.fielded import Choose, FieldedLineup, FieldedStore, Refused, as_advised, fielded_lineup
from fantadamus.league.squads import SquadPlayer, StoredSquad
from tests.lineup_data import full_squad, lineup_rules

AT = dt.datetime(2026, 11, 23, 9, 0, tzinfo=dt.UTC)
SQUAD = StoredSquad(
    team="mine",
    saved_at=AT,
    players=[
        SquadPlayer(player_id=player.player_id, name=player.name, club=player.club, role=player.role)
        for player in full_squad()
    ],
)  # names like "P1", "D4": keepers 1 to 3, defenders 4 to 11, midfielders 12 to 19, forwards 20 to 25
RULES = lineup_rules()
ELEVEN = ["P1", "D4", "D5", "D6", "C12", "C13", "C14", "C15", "A20", "A21", "A22"]


def _field(starters: list[str] = ELEVEN, bench: list[str] | None = None, **choices: str) -> object:
    return fielded_lineup(
        SQUAD,
        RULES,
        round=12,
        starters=starters,
        bench=["P2", "D7", "C16", "A23"] if bench is None else bench,
        captain=choices.get("captain"),
        vice=choices.get("vice"),
        at=AT,
    )


def test_at1_by_name() -> None:
    fielded = _field(captain="A20", vice="C12")
    assert fielded == FieldedLineup(
        round=12,
        team="mine",
        formation="3-4-3",
        starters=[1, 4, 5, 6, 12, 13, 14, 15, 20, 21, 22],
        bench=[2, 7, 16, 23],
        captain=20,
        vice=12,
        saved_at=AT,
    )


def test_at1_as_advised() -> None:
    advice = Advice("4-4-2", [1, 4, 5, 6, 7, 12, 13, 14, 15, 20, 21], [2, 8], 20, 4, AT)
    fielded = as_advised(advice, round=12, team="mine", at=AT)
    assert fielded == FieldedLineup(
        round=12,
        team="mine",
        formation="4-4-2",
        starters=advice.starters,
        bench=advice.bench,
        captain=20,
        vice=4,
        as_advised=True,
        saved_at=AT,
    )


@pytest.mark.parametrize(
    ("starters", "bench", "choices", "says"),
    [
        (ELEVEN[:10], None, {}, "an eleven needs 11 players: got 10"),
        (["P2", *ELEVEN], [], {}, "an eleven needs 11 players: got 12"),
        (["P1", "P2", *ELEVEN[1:9], "A22"], [], {}, "an eleven needs one keeper: got 2"),
        (["D7", *ELEVEN[1:]], [], {}, "an eleven needs one keeper: got 0"),
        (
            ["P1", "D4", "D5", "C12", "C13", "C14", "C15", "C16", "A20", "A21", "A22"],
            [],
            {},
            "2-5-3 isn't a formation",
        ),
        (ELEVEN, ["P2", "D4"], {}, "D4 is listed twice"),
        (ELEVEN, None, {"captain": "A23"}, "the captain must start"),
        (ELEVEN, None, {"captain": "A20", "vice": "D7"}, "the vice must start"),
        (ELEVEN, None, {"captain": "A20", "vice": "A20"}, "the vice can't be the captain"),
        (["Nessuno Mai", *ELEVEN[1:]], None, {}, "Nessuno Mai isn't in this squad"),
    ],
)
def test_at1_refused(
    starters: list[str], bench: list[str] | None, choices: dict[str, str], says: str
) -> None:
    found = _field(starters, bench, **choices)
    assert isinstance(found, Refused)
    assert says in found.reason


def test_at1_a_bench_longer_than_the_leagues() -> None:
    bench = ["P2", "D7", "D8", "C16", "C17", "A23", "A24", "A25"]
    found = fielded_lineup(
        SQUAD,
        lineup_rules(bench_size=7),
        round=12,
        starters=ELEVEN,
        bench=bench,
        captain=None,
        vice=None,
        at=AT,
    )
    assert found == Refused(reason="a bench of 8 places, and this league's has 7")


def test_at1_a_name_that_could_be_two_players() -> None:
    namesakes = [
        *SQUAD.players[:-2],
        SQUAD.players[-2].model_copy(update={"name": "Marco Rossi"}),
        SQUAD.players[-1].model_copy(update={"name": "Luca Rossi"}),
    ]
    squad = SQUAD.model_copy(update={"players": namesakes})
    found = fielded_lineup(
        squad, RULES, round=12, starters=[*ELEVEN[:10], "Rossi"], bench=[], captain=None, vice=None, at=AT
    )
    assert isinstance(found, Choose)
    assert sorted(player.player_id for player in found.unresolved["Rossi"]) == [24, 25]


def test_at1_saved_again(tmp_path: Path) -> None:
    store = FieldedStore(tmp_path)
    first = _field(captain="A20", vice="C12")
    assert isinstance(first, FieldedLineup)
    store.set("user-1", first)
    second = first.model_copy(update={"captain": 21, "vice": 20})
    store.set("user-1", second)
    assert store.get("user-1", "mine", 12) == second
    earlier = first.model_copy(update={"round": 11})
    rival = first.model_copy(update={"team": "Rivals"})
    store.set("user-1", earlier)
    store.set("user-1", rival)
    assert store.get("user-1", "Mine", 12) == second
    assert store.get("user-1", "mine", 11) == earlier
    assert store.get("user-1", "rivals", 12) == rival
    assert store.get("user-2", "mine", 12) is None
    assert [path.name for path in tmp_path.iterdir()] == ["user-1-fielded.json"]
