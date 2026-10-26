"""Task 1.1: the Serie A clubs and the spellings outlets use (design C1; R2.1, R6.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fantadamus.core.clubs import Clubs, UnknownClubError

ROOT = Path(__file__).resolve().parents[3]


def _repo_clubs() -> Clubs:
    return Clubs.from_toml((ROOT / "config" / "clubs.toml").read_text(encoding="utf-8"))


def test_twenty_clubs_unique_aliases() -> None:
    clubs = _repo_clubs()
    assert len(clubs.names) == 20
    assert (
        clubs.key("Inter")
        == clubs.key("internazionale")
        == clubs.key("F.C. Internazionale Milano")
        == "inter"
    )
    assert clubs.key("  AC   MILAN ") == "milan"
    assert clubs.key("Udinésé") == "udinese"
    with pytest.raises(ValueError, match="'milan' is a spelling of both milan and inter"):
        Clubs.from_toml(
            '[clubs.milan]\nname = "Milan"\n\n[clubs.inter]\nname = "Inter"\naliases = ["Milan"]\n'
        )


def test_unknown_club_lists_known_ones() -> None:
    clubs = Clubs.from_toml(
        '[clubs.alfa]\nname = "Alfa"\n\n[clubs.beta]\nname = "Beta"\naliases = ["Beta FC"]\n'
    )
    with pytest.raises(UnknownClubError, match=r"unknown club 'Gamma'; known clubs: Alfa, Beta"):
        clubs.key("Gamma")
    for bad in ('[clubs.Alfa]\nname = "Alfa"\n', '[clubs.alfa]\nname = ""\n', "x = 1\n"):
        with pytest.raises(ValueError, match="clubs"):
            Clubs.from_toml(bad)
