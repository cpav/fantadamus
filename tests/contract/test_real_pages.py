"""mvp-collect task 3.3 and mvp-roles task 2.2: the readers and page text on real pages saved under
data/private/pages/ (mvp-collect R3.4; mvp-roles R1.2, R1.6). Real pages can't be committed to the public
repository, so this runs only where they've been saved, and there it shows a changed layout, or a name the two
sites spell differently, before a collection or an answer does."""

from __future__ import annotations

from pathlib import Path

import pytest

from fantadamus.core.clubs import Clubs
from fantadamus.domains.players.resolve import KnownPlayer, resolve
from fantadamus.web.html import parse
from fantadamus.web.readers.fcit_stats import read_stats
from fantadamus.web.readers.fco import read_round
from fantadamus.web.text import page_text, parts

ROOT = Path(__file__).resolve().parents[2]
PAGES = ROOT / "data" / "private" / "pages"
SAVED = sorted(PAGES.glob("*.html")) if PAGES.is_dir() else []
STATS = PAGES / "fcit-statistiche.html"
ROUNDS = [path for path in SAVED if path.name.startswith("fco-round")]
CLUBS = Clubs.from_toml((ROOT / "config" / "clubs.toml").read_text(encoding="utf-8"))
RESOLVED = 0.95
"""The share of a round page's distinct names that must find a player: 96.6% did on the pages of 31 October
and 3 November, and the rest were players outside the official list, which the statistics page doesn't show.
Before an initial was kept from pairing with a whole name, 45% did."""


@pytest.mark.skipif(
    not SAVED, reason="no real pages saved under data/private/pages/, which is never committed"
)
def test_reading_saved_pages() -> None:
    for path in SAVED:
        html = path.read_text(encoding="utf-8")
        text = page_text(parse(html), "https://example.org/", lambda _: False)
        assert text.strip(), path.name
        assert "\n".join(parts(text)) == text, path.name
        if path.name.startswith("fco-round"):
            facts = read_round(html)  # the round from the page's title
            assert facts.fixtures.matches, path.name
            assert {(view.home, view.away) for view in facts.outlets} == _published(html), path.name


def _published(html: str) -> set[tuple[str, str]]:
    """The matches whose lineup tables the page shows, from the HTML itself: early in the week, none."""
    published = set()
    for pane in parse(html).find_all("div", "tab-pane"):
        header = pane.find("header", "prb-incontro")
        if header is not None and pane.find("table", "prb-tabella") is not None:
            home, away = (name.text() for name in header.find_all(class_="prb-incontro__nome"))
            published.add((home, away))
    return published


@pytest.mark.skipif(
    not STATS.is_file(), reason="no statistics page saved under data/private/pages/, which is never committed"
)
def test_saved_statistics_page() -> None:
    facts = read_stats(STATS.read_text(encoding="utf-8"))
    assert facts.problems == []
    players = facts.payload.players
    assert {CLUBS.key(player.club) for player in players} == set(CLUBS.names)
    keepers = {CLUBS.key(player.club) for player in players if player.role == "P"}
    assert keepers == set(CLUBS.names)


@pytest.mark.skipif(
    not (STATS.is_file() and ROUNDS),
    reason="no statistics or round page saved under data/private/pages/, which is never committed",
)
def test_round_page_names_resolve() -> None:
    """Every outlet's name on a saved round page finds at most one player of its club on the statistics page,
    and almost every one finds one."""
    players = read_stats(STATS.read_text(encoding="utf-8")).payload.players
    known = [KnownPlayer(player_id=p.player_id, name=p.name, club=CLUBS.key(p.club)) for p in players]
    for path in ROUNDS:
        names = {
            (CLUBS.key(club), name)
            for view in read_round(path.read_text(encoding="utf-8")).outlets
            for club, team in ((view.home, view.home_team), (view.away, view.away_team))
            for name in [*(player.name for player in team.players), *team.unavailable]
        }
        found = [resolve(name, [mate for mate in known if mate.club == club]) for club, name in names]
        assert not [resolution.candidates for resolution in found if resolution.candidates], path.name
        assert sum(resolution.player is not None for resolution in found) >= RESOLVED * len(found), path.name
