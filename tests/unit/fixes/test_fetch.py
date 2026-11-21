"""mvp-fixes tasks 1.1 and 1.2: a robots.txt that got no answer fails its host's pages instead of disallowing
them, and is asked once a run; a page the site says is gone is missing (design C1; R1.1, R1.3, R1.4)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.core.clock import fixed_clock
from fantadamus.web.fetch import (
    DisallowedError,
    Fetcher,
    FetchFailedError,
    PageMissingError,
    Response,
    RobotsUnreadableError,
)
from tests.collect_harness import FakeTime, FakeWeb

DAY = dt.datetime(2026, 11, 21, 7, 2, tzinfo=dt.UTC)
ROBOTS = "https://site.example/robots.txt"
PAGE = "https://site.example/page"
OTHER = "https://site.example/other"
OK = Response(200, {"Content-Type": "text/html; charset=utf-8"}, b"<p>ok</p>")
NOT_FOUND = Response(404, {}, b"")


def _fetcher(web: FakeWeb, cache: Path) -> Fetcher:
    time = FakeTime()
    return Fetcher(
        allowed_hosts=["site.example"],
        clock=fixed_clock(DAY),
        monotonic=time.monotonic,
        sleep=time.sleep,
        transport=web,
        robots_cache=cache,
    )


def test_robots_without_an_answer_fails_the_hosts_pages(tmp_path: Path) -> None:
    """A robots.txt that times out isn't the site's answer: the page fails, saying why, instead of being
    reported as disallowed, and nothing is kept for the day."""
    web = FakeWeb({ROBOTS: TimeoutError("timed out"), PAGE: OK})
    with pytest.raises(RobotsUnreadableError, match=r"robots\.txt couldn't be read \(timed out\)") as raised:
        _fetcher(web, tmp_path).fetch(PAGE)
    assert isinstance(raised.value, FetchFailedError)
    assert not isinstance(raised.value, DisallowedError)
    assert [url for url, _, _ in web.calls] == [ROBOTS]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("status", [500, 502, 504])
def test_robots_server_error_fails_the_hosts_pages(tmp_path: Path, status: int) -> None:
    web = FakeWeb({ROBOTS: Response(status, {}, b""), PAGE: OK})
    with pytest.raises(
        RobotsUnreadableError, match=rf"robots\.txt couldn't be read \(it answered {status}\)"
    ):
        _fetcher(web, tmp_path).fetch(PAGE)
    assert [url for url, _, _ in web.calls] == [ROBOTS]
    assert list(tmp_path.iterdir()) == []


def test_robots_is_asked_once_a_run(tmp_path: Path) -> None:
    """One run asks for robots.txt once per host and requests none of the host's pages while it can't be read;
    the next run asks again."""
    web = FakeWeb({ROBOTS: TimeoutError("timed out"), PAGE: OK, OTHER: OK})
    fetcher = _fetcher(web, tmp_path)
    for url in (PAGE, OTHER, PAGE):
        with pytest.raises(RobotsUnreadableError):
            fetcher.fetch(url)
    assert [url for url, _, _ in web.calls] == [ROBOTS]
    with pytest.raises(RobotsUnreadableError):
        _fetcher(web, tmp_path).fetch(PAGE)
    assert [url for url, _, _ in web.calls] == [ROBOTS, ROBOTS]


@pytest.mark.parametrize("status", [429, 503])
def test_robots_block_status_still_disallows(tmp_path: Path, status: int) -> None:
    """A block status for robots.txt is the site's answer: nothing is fetched this run, as before."""
    web = FakeWeb({ROBOTS: Response(status, {}, b""), PAGE: OK})
    with pytest.raises(DisallowedError):
        _fetcher(web, tmp_path).fetch(PAGE)
    assert [url for url, _, _ in web.calls] == [ROBOTS]


def test_robots_not_found_still_allows_everything(tmp_path: Path) -> None:
    web = FakeWeb({ROBOTS: NOT_FOUND, PAGE: OK})
    assert _fetcher(web, tmp_path).fetch(PAGE).status == 200


@pytest.mark.parametrize("status", [400, 404, 410])
def test_a_page_the_site_says_is_gone_is_missing(tmp_path: Path, status: int) -> None:
    """The site's own answer that the page isn't there: still a failed fetch for callers that catch one, and
    told apart, so that a page that's gone isn't asked for at every run."""
    web = FakeWeb({ROBOTS: NOT_FOUND, PAGE: Response(status, {}, b"")})
    with pytest.raises(PageMissingError, match=str(status)) as raised:
        _fetcher(web, tmp_path).fetch(PAGE)
    assert isinstance(raised.value, FetchFailedError)


@pytest.mark.parametrize("status", [408, 500, 502, 504])
def test_a_page_server_error_fails(tmp_path: Path, status: int) -> None:
    """A server error, or a 408 (the server gave up waiting), isn't an answer about the page: a failed try."""
    web = FakeWeb({ROBOTS: NOT_FOUND, PAGE: Response(status, {}, b"")})
    with pytest.raises(FetchFailedError, match=str(status)) as raised:
        _fetcher(web, tmp_path).fetch(PAGE)
    assert not isinstance(raised.value, PageMissingError)
