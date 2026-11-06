"""Shared by the `mvp-roles` tests: a statistics-page read for the test clubs, as rows the reader would give,
and the engine's inputs for a player of each role.

The clubs are `tests.xy_harness.CLUBS`; the players are invented, one of each role per club.
"""

from __future__ import annotations

from typing import Any

from fantadamus.contracts.types import Role
from fantadamus.core.clubs import Clubs
from fantadamus.engine.keepers import KeeperInputs
from fantadamus.engine.outfield import OutfieldInputs
from tests.xy_harness import CLUBS

ROLES = (("P", "Por"), ("D", "Dc"), ("C", "C"), ("A", "Pc"))


def stats_row(club: str, role: str, mantra_role: str | None, player_id: int, **change: Any) -> dict[str, Any]:
    """One player's row: eight rated games, a keeper's with nine goals conceded."""
    keeper = role == "P"
    return {
        "player_id": player_id,
        "name": f"{club} {mantra_role}",
        "club": club,
        "role": role,
        "mantra_role": mantra_role,
        "appearances": 8,
        "rated_appearances": 8,
        "average_rating": 6.2 if keeper else 6.3,
        "goals": 0 if keeper else 2,
        "goals_conceded": 9 if keeper else 0,
        "assists": 0 if keeper else 1,
        "yellow_cards": 1,
        "penalties_scored": 0,
        "penalties_taken": 0,
    } | change


def stats_read(*, without: tuple[str | tuple[str, str], ...] = (), clubs: Clubs = CLUBS) -> dict[str, Any]:
    """A full read: every club (the test clubs by default) with a player of each role, leaving out the clubs
    and the (club, role) pairs named. Clubs go by name; the page's links write that in lower case, its key."""
    players = [
        stats_row(clubs.names[club], role, mantra, 7000 + 10 * index + number)
        for index, club in enumerate(sorted(clubs.names))
        for number, (role, mantra) in enumerate(ROLES)
        if (clubs.names[club], role) not in without and clubs.names[club] not in without
    ]
    return {"players": players}


def outfield(role: Role, mantra_role: str | None, **changes: Any) -> OutfieldInputs:
    """An outfield player of `role` without goals, assists or games, unless `changes` give them: what's left
    is his role's priors."""
    base = OutfieldInputs(
        name=f"{role} {mantra_role}",
        role=role,
        mantra_role=mantra_role,
        appearances=0,
        rated_appearances=0,
        average_rating=None,
        goals=0,
        assists=0,
        yellow_cards=0,
        club_goals_per_match=1.5,
        penalty_share=0.0,
        team_xg=1.4,
        p_win=0.45,
        p_loss=0.30,
        p_start=0.9,
        p_cameo=0.05,
    )
    return base.model_copy(update=changes)


def keeper(**changes: Any) -> KeeperInputs:
    """A keeper with eight rated games, nine goals conceded, facing an opponent expected to score 1.1."""
    base = KeeperInputs(
        name="Keeper",
        club="alfa",
        rated_appearances=8,
        average_rating=6.2,
        goals_conceded=9,
        league_goals_per_match=1.3,
        opponent_xg=1.1,
        p_start=0.95,
    )
    return base.model_copy(update=changes)


def season(name: str, role: Role, mantra_role: str | None, player_id: int, **changes: Any) -> dict[str, Any]:
    """A player's season, as Claude submits it from a profile; his club is the first word of his name. The
    synthetic lineups list `<Club> Uno` to `<Club> Undici` as starters, `Dodici` and `Tredici` on the bench
    and `Quattordici` unavailable."""
    return stats_row(name.split()[0], role, mantra_role, player_id, name=name) | changes


ROLE_PLAYERS = (
    season("Alfa Uno", "P", "Por", 9101, average_rating=6.6),
    season("Gamma Uno", "P", "Por", 9103, goals_conceded=14),
    season(
        "Alfa Dodici",
        "P",
        "Por",
        9111,
        rated_appearances=1,
        appearances=1,
        average_rating=6.0,
        goals_conceded=1,
    ),
    season("Alfa Due", "D", "Dc", 9201),
    season("Gamma Due", "D", "Dd", 9203),
    season("Alfa Quattordici", "D", "Dc", 9214),
    season("Alfa Sei", "C", "C", 9301),
    season("Gamma Sei", "C", "T", 9303),
)


def squad_stats(clubs: Clubs = CLUBS) -> list[dict[str, Any]]:
    """The statistics page's rows for every club, under the names the synthetic lineups use: its keeper, a
    defender, a midfielder and its forward."""
    rows = []
    for index, club in enumerate(sorted(clubs.names)):
        name = clubs.names[club]
        rows += [
            season(f"{name} Uno", "P", "Por", 8000 + 10 * index),
            season(f"{name} Due", "D", "Dc", 8001 + 10 * index),
            season(f"{name} Sei", "C", "C", 8002 + 10 * index),
            season(f"{name} Nove", "A", "Pc", 8003 + 10 * index),
        ]
    return rows
