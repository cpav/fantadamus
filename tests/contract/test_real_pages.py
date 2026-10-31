"""mvp-collect task 3.3: the round-page reader and page text on real pages saved under data/private/pages/
(design, testing strategy; R3.4). Real pages can't be committed to the public repository, so this runs only
where they've been saved, and there it shows a changed layout before a collection does."""

from __future__ import annotations

from pathlib import Path

import pytest

from fantadamus.web.html import parse
from fantadamus.web.readers.fco import read_round
from fantadamus.web.text import page_text, parts

PAGES = Path(__file__).resolve().parents[2] / "data" / "private" / "pages"
SAVED = sorted(PAGES.glob("*.html")) if PAGES.is_dir() else []


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
