"""mvp-lineup task 12: a taker's share, a changed order, the list against the record (R10.1, R10.4, R10.5)."""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

import pytest

from fantadamus.domains.facts import Source
from fantadamus.domains.players.resolve import KnownPlayer
from fantadamus.domains.season.gold import PenaltyOrder, order_change, penalty_mismatch, penalty_share
from fantadamus.domains.season.silver import PenaltyTakerRow, PlayerSeasonRow

NOW = dt.datetime(2026, 11, 6, 12, tzinfo=dt.UTC)
DAY = dt.timedelta(days=1)
URL = "https://example.org/takers"
SOURCE = Source(source_url=URL, captured_at=NOW, content_sha256="a" * 64)
ROSSI, BIANCHI, VERDI, NERI = (
    KnownPlayer(player_id=number, name=name, club="alfa")
    for number, name in enumerate(("Rossi A.", "Bianchi B.", "Verdi C.", "Neri D."), start=1)
)
MATES = [ROSSI, BIANCHI, VERDI, NERI]
ORDER = PenaltyOrder(takers=["Rossi A.", "Bianchi B.", "Verdi C."], source=SOURCE)


def _share(player: KnownPlayer, order: PenaltyOrder = ORDER, **chance: float) -> float:
    return penalty_share(player, order, MATES, lambda mate: chance[mate.name.split()[0]])


def test_share_by_hand() -> None:
    """The first has all of them; each next one has what those ahead of him leave."""
    assert _share(ROSSI) == 1.0  # nobody ahead: nothing to ask about
    assert _share(BIANCHI, Rossi=0.6) == pytest.approx(0.4)
    assert _share(VERDI, Rossi=0.6, Bianchi=0.5) == pytest.approx(0.2)


def test_a_first_taker_who_is_out_hands_them_all_on() -> None:
    assert _share(BIANCHI, Rossi=0.0) == 1.0
    assert _share(VERDI, Rossi=0.0, Bianchi=1.0) == 0.0


def test_not_listed_gets_none() -> None:
    """And costs no lookup: most of a squad isn't on any list."""
    assert _share(NERI) == 0.0


def test_a_name_nobody_knows_counts_as_missing() -> None:
    """A name on the list that no club-mate answers to has no rated game: he isn't taking them."""
    order = PenaltyOrder(takers=["Sconosciuto Z.", "Bianchi B."], source=SOURCE)
    assert _share(BIANCHI, order) == 1.0


def _read(names: Sequence[str], at: dt.datetime, club: str = "alfa") -> list[PenaltyTakerRow]:
    digest = f"{hash((tuple(names), at)) & 0xFFFFFFFF:064x}"
    return [
        PenaltyTakerRow(
            source_url=URL, captured_at=at, content_sha256=digest, club=club, rank=rank, name=name
        )
        for rank, name in enumerate(names, start=1)
    ]


def test_a_change_is_shown_for_a_week() -> None:
    changed_at = NOW - 3 * DAY
    rows = _read(["Rossi A.", "Bianchi B."], NOW - 10 * DAY) + _read(["Bianchi B.", "Rossi A."], changed_at)
    change = order_change(rows, "alfa", NOW)
    assert change is not None
    assert (change.before, change.after, change.at) == (
        ["Rossi A.", "Bianchi B."],
        ["Bianchi B.", "Rossi A."],
        changed_at,
    )
    assert order_change(rows, "alfa", changed_at + 7 * DAY) is not None
    assert order_change(rows, "alfa", changed_at + 7 * DAY + dt.timedelta(seconds=1)) is None
    assert order_change(rows, "alfa", changed_at - dt.timedelta(seconds=1)) is None


def test_a_repeated_order_is_no_change() -> None:
    """The window runs out and the same list is stored again: nothing has moved."""
    rows = _read(["Rossi A."], NOW - 15 * DAY) + _read(["Rossi A."], NOW - DAY)
    assert order_change(rows, "alfa", NOW) is None


def test_a_first_read_is_no_change() -> None:
    assert order_change(_read(["Rossi A."], NOW - DAY), "alfa", NOW) is None
    assert order_change([], "alfa", NOW) is None


def test_another_clubs_change_is_not_this_ones() -> None:
    rows = (
        _read(["Rossi A."], NOW - 5 * DAY)
        + _read(["Nove B."], NOW - 5 * DAY, club="beta")
        + _read(["Dieci B."], NOW - DAY, club="beta")
    )
    assert order_change(rows, "alfa", NOW) is None
    assert order_change(rows, "beta", NOW) is not None


def _season(player: KnownPlayer, taken: int, scored: int = 0) -> PlayerSeasonRow:
    return PlayerSeasonRow(
        source_url=URL,
        captured_at=NOW,
        content_sha256="b" * 64,
        player_id=player.player_id,
        name=player.name,
        club=player.club,
        role="A",
        mantra_role="Pc",
        appearances=8,
        rated_appearances=8,
        average_rating=6.2,
        goals=2,
        assists=0,
        yellow_cards=0,
        penalties_scored=scored,
        penalties_taken=taken,
    )


def _seasons(*rows: PlayerSeasonRow) -> dict[int, PlayerSeasonRow]:
    return {row.player_id: row for row in rows}


def test_the_list_against_the_record() -> None:
    """Either of the two hears it: the one listed first, and the one who has really been taking them."""
    seasons = _seasons(_season(ROSSI, 1), _season(BIANCHI, 2, 2), _season(VERDI, 0))
    for asked in (ROSSI, BIANCHI):
        mismatch = penalty_mismatch(asked, ORDER, MATES, seasons)
        assert mismatch is not None
        assert (mismatch.first.name, mismatch.other.name) == ("Rossi A.", "Bianchi B.")
    assert penalty_mismatch(VERDI, ORDER, MATES, seasons) is None


def test_the_first_hears_about_whoever_has_taken_the_most() -> None:
    seasons = _seasons(_season(ROSSI, 0), _season(BIANCHI, 1, 1), _season(VERDI, 2, 1))
    first = penalty_mismatch(ROSSI, ORDER, MATES, seasons)
    second = penalty_mismatch(BIANCHI, ORDER, MATES, seasons)
    assert first is not None
    assert first.other.name == "Verdi C."
    assert second is not None
    assert second.other.name == "Bianchi B."


def test_level_figures_say_nothing() -> None:
    seasons = _seasons(_season(ROSSI, 1, 1), _season(BIANCHI, 1, 1))
    assert penalty_mismatch(ROSSI, ORDER, MATES, seasons) is None
    assert penalty_mismatch(BIANCHI, ORDER, MATES, seasons) is None


def test_a_first_taker_nobody_knows_says_nothing() -> None:
    """There's nobody to compare him with: R10.1 has already handed his share on."""
    order = PenaltyOrder(takers=["Sconosciuto Z.", "Bianchi B."], source=SOURCE)
    assert penalty_mismatch(BIANCHI, order, MATES, _seasons(_season(BIANCHI, 3, 3))) is None
