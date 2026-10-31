"""P8: `read_page` requests an address only if the reading list names it or one of its patterns matches it
(design C3.2; R3.3)."""

from __future__ import annotations

import datetime as dt
import tempfile
from collections.abc import Mapping
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.core.clock import fixed_clock
from fantadamus.mcp.tools.compare import ReadingItem
from fantadamus.mcp.tools.pages import NotOnReadingListError, PageReader
from fantadamus.web.fetch import Fetcher, Response
from tests.collect_harness import FakeTime

READING = {
    "team_season": ReadingItem(
        need="N5", submit_tool="submit_team_season", pages=["https://example.org/table"]
    ),
    "player_season": ReadingItem(
        need="N5",
        submit_tool="submit_player_season",
        pages=["https://example.org/squads/{club}"],
        patterns=["https://example.org/squads/{club}/{player}/{id}"],
    ),
}
segment = st.text(alphabet="abc9-", min_size=1, max_size=6)  # never spells "table"
listed = st.one_of(
    st.just("https://example.org/table"),
    segment.map(lambda club: f"https://example.org/squads/{club}"),
    st.tuples(segment, segment, segment).map(
        lambda parts: "https://example.org/squads/{}/{}/{}".format(*parts)
    ),
)
unlisted = st.one_of(
    st.just("https://example.org/table/more"),
    st.just("https://example.org/squads/"),  # an empty segment
    st.tuples(segment, segment).map(lambda parts: "https://example.org/squads/{}/{}".format(*parts)),
    segment.map(lambda path: f"https://example.org/{path}"),
    segment.map(lambda club: f"https://example.org/squads/{club}?page=2"),
    segment.map(lambda club: f"https://other.example/squads/{club}"),
    segment.map(lambda club: f"http://example.org/squads/{club}"),
)


class AnyPage:
    """Every address answers with a page; robots.txt is missing, so everything is allowed."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def __call__(self, url: str, headers: Mapping[str, str], timeout: float) -> Response:
        self.urls.append(url)
        if url.endswith("/robots.txt"):
            return Response(404, {}, b"")
        return Response(200, {"Content-Type": "text/html; charset=utf-8"}, b"<p>ok</p>")


@given(case=st.one_of(listed.map(lambda url: (True, url)), unlisted.map(lambda url: (False, url))))
def test_p8_only_listed_addresses(case: tuple[bool, str]) -> None:
    listed_by_construction, url = case
    web, time = AnyPage(), FakeTime()
    with tempfile.TemporaryDirectory() as cache:
        fetcher = Fetcher(
            allowed_hosts=["example.org", "other.example"],  # the reading list refuses, not the allowlist
            clock=fixed_clock(dt.datetime(2026, 10, 31, tzinfo=dt.UTC)),
            monotonic=time.monotonic,
            sleep=time.sleep,
            transport=web,
            robots_cache=Path(cache),
        )
        try:
            PageReader(READING, fetcher).read(url)
            read = True
        except NotOnReadingListError:
            read = False
    assert read == listed_by_construction
    assert [seen for seen in web.urls if not seen.endswith("/robots.txt")] == ([url] if read else [])
