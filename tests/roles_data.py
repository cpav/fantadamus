"""Shared by the `mvp-roles` tests: a statistics-page read for the test clubs, as rows the reader would give.

The clubs are `tests.xy_harness.CLUBS`; the players are invented, one of each role per club.
"""

from __future__ import annotations

from typing import Any

from fantadamus.core.clubs import Clubs
from tests.xy_harness import CLUBS

ROLES = (("P", "Por"), ("D", "Dc"), ("C", "C"), ("A", "Pc"))


def stats_row(club: str, role: str, mantra_role: str, player_id: int, **change: Any) -> dict[str, Any]:
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
