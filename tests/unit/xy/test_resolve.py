"""Task 2.3: name resolution (design C4; R1.2, R1.3)."""

from __future__ import annotations

import pytest

from fantadamus.domains.players.resolve import KnownPlayer, resolve

MARCO = KnownPlayer(player_id=1, name="Marco Rossi", club="alfa")
LUCA = KnownPlayer(player_id=2, name="Rossi L.", club="beta")
DARIO = KnownPlayer(player_id=3, name="Dario Verdì", club="alfa")
GIORGIO = KnownPlayer(player_id=4, name="Bianchi", club="gamma")
PLAYERS = [MARCO, LUCA, DARIO, GIORGIO]


@pytest.mark.parametrize(
    ("name", "player"),
    [
        ("marco ROSSI", MARCO),
        ("  dario   verdi ", DARIO),
        ("DarioVerdì", DARIO),
        ("Verdi", DARIO),
        ("Giorgio Bianchi", GIORGIO),  # the profile has the surname only
    ],
)
def test_full_name_and_unique_surname(name: str, player: KnownPlayer) -> None:
    assert resolve(name, PLAYERS).player == player


@pytest.mark.parametrize(
    ("name", "player"),
    [("Rossi M.", MARCO), ("Marco R", MARCO), ("Luca Rossi", LUCA), ("Rossi L", LUCA)],
)
def test_surname_and_initial(name: str, player: KnownPlayer) -> None:
    resolution = resolve(name, PLAYERS)
    assert resolution.player == player
    assert resolution.candidates == []


def test_ambiguous_or_unknown_returns_candidates() -> None:
    ambiguous = resolve("Rossi", PLAYERS)
    assert ambiguous.player is None
    assert ambiguous.candidates == [MARCO, LUCA]
    for unknown in ("Neri", "Paolo Rossi", "", "  .  "):
        resolution = resolve(unknown, PLAYERS)
        assert (resolution.player, resolution.candidates) == (None, [])
