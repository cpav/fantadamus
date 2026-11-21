"""P2 (mvp-fixes design; R1.2, R1.3): over runs in which a host's robots.txt can't be read, the fetcher asks
for it once per run and requests none of the host's pages; an answer never tries a page sooner than
`RETRY_AFTER` after a failed try."""

from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fantadamus.core.clock import fixed_clock
from fantadamus.web.cadence import RETRY_AFTER, may_read_after
from fantadamus.web.collector import PageKind
from fantadamus.web.fetch import Fetcher, Response, RobotsUnreadableError
from tests.collect_harness import FakeTime, FakeWeb

DAY = dt.datetime(2026, 11, 21, 7, 2, tzinfo=dt.UTC)
ROBOTS = "https://site.example/robots.txt"
PATHS = ("/a", "/b", "/c", "/d")
FAILURES: tuple[Response | Exception, ...] = (
    TimeoutError("timed out"),
    ConnectionRefusedError("refused"),
    Response(500, {}, b""),
    Response(502, {}, b""),
    Response(504, {}, b""),
)


@given(
    st.lists(st.sampled_from(PATHS), min_size=1, max_size=8),
    st.sampled_from(FAILURES),
    st.integers(min_value=1, max_value=4),
)
def test_p2_one_robots_try_a_run_and_no_page_requested(
    paths: list[str], failure: Response | Exception, runs: int
) -> None:
    web = FakeWeb(
        {ROBOTS: failure, **{f"https://site.example{path}": Response(200, {}, b"ok") for path in PATHS}}
    )
    with tempfile.TemporaryDirectory() as cache:
        for _ in range(runs):
            time = FakeTime()
            fetcher = Fetcher(
                allowed_hosts=["site.example"],
                clock=fixed_clock(DAY),
                monotonic=time.monotonic,
                sleep=time.sleep,
                transport=web,
                robots_cache=Path(cache),
            )
            for path in paths:
                with pytest.raises(RobotsUnreadableError):
                    fetcher.fetch(f"https://site.example{path}")
    assert [url for url, _, _ in web.calls] == [ROBOTS] * runs


PAGES: tuple[PageKind, ...] = ("round", "statistics", "takers", "injuries")


@given(
    st.integers(min_value=0, max_value=3 * 24 * 60),
    st.integers(min_value=0, max_value=60),
    st.sampled_from(PAGES),
)
def test_p2_an_answer_never_retries_sooner(answered_ago: int, failed_ago: int, page: PageKind) -> None:
    now = DAY
    last_failed = now - dt.timedelta(minutes=failed_ago)
    last_answered = now - dt.timedelta(minutes=answered_ago + failed_ago)
    if now - last_failed < RETRY_AFTER:
        assert not may_read_after(page, last_answered, last_failed, now)
