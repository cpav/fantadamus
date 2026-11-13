"""P2 of mvp-sources: a `Football box` template's match, written by a generator in either of the pages'
layouts, is read back the same (design, correctness properties; R2.1)."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.core.names import name_key
from fantadamus.web.readers.wiki_fixtures import read_other_fixtures
from tests.sources_pages import Box, cup_box, link, plain_date, start_date, uefa_box, wiki_page

ROME = ZoneInfo("Europe/Rome")
_WORD = st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=2, max_size=9).map(str.title)
_NAME = st.lists(_WORD, min_size=1, max_size=3).map(" ".join)


@st.composite
def _side(draw: st.DrawFn, name: str) -> str:
    """A club as either page writes it: a link with or without its article's title, maybe its tier, maybe in
    bold as the winner."""
    target = draw(st.one_of(st.none(), _NAME.map(lambda title: f"{title} FC")))
    side = link(name, target if target and name_key(target) != name_key(name) else None)
    if draw(st.booleans()):
        side += f" ({draw(st.integers(1, 4))})"
    return f"'''{side}'''" if draw(st.booleans()) else side


@st.composite
def _match(draw: st.DrawFn) -> tuple[str, str, dt.datetime, str]:
    home = draw(_NAME)
    away = draw(_NAME.filter(lambda name: name_key(name) != name_key(home)))
    day = draw(st.dates(dt.date(2026, 7, 1), dt.date(2027, 6, 30)))
    hour, minute = draw(st.integers(12, 22)), draw(st.sampled_from([0, 15, 30, 45]))
    time = f"{hour:02d}:{minute:02d}"
    cup = draw(st.booleans())
    box = Box(
        draw(_side(home)),
        draw(_side(away)),
        plain_date(day) if cup else start_date(day),
        time + draw(st.sampled_from(["", " [[Central European Time|CET]]", "&nbsp;{{small|(19:45 UTC+3)}}"])),
        draw(st.sampled_from(["", "1\u20130", "{{score link|A v B|2\u20132}}"])),
    )
    kickoff = dt.datetime.combine(day, dt.time(hour, minute), ROME).astimezone(dt.UTC)
    return home, away, kickoff, cup_box(box, collapsible=draw(st.booleans())) if cup else uefa_box(box)


@given(st.lists(_match(), min_size=1, max_size=6))
def test_p2_a_match_read_back(matches: list[tuple[str, str, dt.datetime, str]]) -> None:
    facts = read_other_fixtures(wiki_page([box for *_, box in matches]), "Conference League")
    assert [(m.home, m.away, m.kickoff_at) for m in facts.payload.matches] == [
        (home, away, kickoff) for home, away, kickoff, _ in matches
    ]
    assert facts.problems == []
