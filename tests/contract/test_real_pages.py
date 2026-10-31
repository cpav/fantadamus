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
            facts = read_round(html, round=1)
            matches = {(match.home, match.away) for match in facts.fixtures.matches}
            assert {(view.home, view.away) for view in facts.outlets} == matches, path.name
