"""mvp-lineup task 3.3: what a squad can't field, and how a squad is stored (design C3; R1.1, R1.3, R1.5)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from fantadamus.contracts.types import Role
from fantadamus.league.squads import MINE, SquadPlayer, SquadStore, cannot_field

AT = dt.datetime(2026, 11, 4, 9, 0, tzinfo=dt.UTC)
ONE = SquadPlayer(player_id=1, name="Uno", club="Alfa", role="P")


def test_a_formation_short_in_one_line_cannot_be_fielded() -> None:
    roles: dict[Role, int] = {"P": 3, "D": 4, "C": 8, "A": 6}
    assert cannot_field(["4-3-3"], roles) == []
    assert cannot_field(["5-3-2", "4-3-3"], roles) == [
        "Can't field 5-3-2: it needs 5 defenders, 3 midfielders and 2 forwards, and the squad has 4, 8 and 6."
    ]


def test_exactly_enough_can_be_fielded() -> None:
    assert cannot_field(["3-4-3"], {"P": 1, "D": 3, "C": 4, "A": 3}) == []


def test_a_squad_is_private_to_its_user_and_team(tmp_path: Path) -> None:
    store = SquadStore(tmp_path)
    store.set("user-1", MINE, [ONE], at=AT)
    assert store.get("user-2") is None
    assert store.get("user-1", "Rivali") is None
    assert (tmp_path / "user-1-squads.json").is_file()
    assert (
        json.loads((tmp_path / "user-1-squads.json").read_text(encoding="utf-8"))["teams"]["mine"]["team"]
        == "mine"
    )
    assert not list(tmp_path.glob(".*.tmp"))


@pytest.mark.parametrize("user", ["../user-1", "User One", ""])
def test_a_user_id_cannot_reach_outside_the_folder(tmp_path: Path, user: str) -> None:
    store = SquadStore(tmp_path)
    with pytest.raises(ValueError, match="user ID"):
        store.get(user)
    with pytest.raises(ValueError, match="user ID"):
        store.set(user, MINE, [ONE], at=AT)


@pytest.mark.parametrize("team", ["", "  ", "---"])
def test_a_team_needs_a_name(tmp_path: Path, team: str) -> None:
    with pytest.raises(ValueError, match="a team needs a name"):
        SquadStore(tmp_path).set("user-1", team, [ONE], at=AT)
