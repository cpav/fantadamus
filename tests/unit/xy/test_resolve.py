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


def test_an_initial_never_stands_for_a_whole_name() -> None:
    """mvp-roles task 2.2: with every listed player known, an outlet's "SKORUPSKI L" finds Skorupski, not also
    Libra, whose name its initial would pair with."""
    skorupski, libra, pessina, mbangula = (
        KnownPlayer(player_id=number, name=name, club="bologna")
        for number, name in enumerate(("Skorupski", "Libra", "Pessina Mas.", "Mbangula"), start=1)
    )
    squad = [skorupski, libra, pessina, mbangula]
    assert resolve("SKORUPSKI L", squad).player == skorupski
    assert resolve("PESSINA M", squad).player == pessina
    assert resolve("LIBRA ALVARADO M", squad).player == libra
    assert resolve("MBANGULA S", squad).player == mbangula


def test_the_two_sites_spellings_meet() -> None:
    """mvp-roles task 2.2: Fantacalcio-Online's names against the statistics page's, as on the real pages: a
    hyphenated surname written in part, and a surname written as two words. A first name that disagrees with
    an initial still rules a player out, so "ANGUISSA A" can't find "Zambo Anguissa": from the words alone,
    Zambo could be a first name."""
    keeper, defender, midfielder, other = (
        KnownPlayer(player_id=number, name=name, club="napoli")
        for number, name in enumerate(
            ("Milinkovic-Savic V.", "Delprato", "Zambo Anguissa", "Rossi L."), start=1
        )
    )
    squad = [keeper, defender, midfielder, other]
    assert resolve("MILINKOVIC V", squad).player == keeper
    assert resolve("DEL PRATO E", squad).player == defender
    assert resolve("Anguissa", squad).player == midfielder
    assert resolve("ANGUISSA A", squad).player is None
    assert resolve("ROSSI M", squad).player is None
