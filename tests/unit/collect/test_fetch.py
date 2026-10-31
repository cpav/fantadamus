"""mvp-collect task 2.1: the fetcher keeps to the allowlist and robots.txt, and stops at a block (C1; R2)."""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Mapping
from pathlib import Path

import pytest

from fantadamus.core.clock import fixed_clock
from fantadamus.web.fetch import (
    DisallowedError,
    Fetcher,
    FetchFailedError,
    HostBlockedError,
    NotAllowedError,
    Response,
)
from tests.collect_harness import FakeTime, FakeWeb

DAY = dt.datetime(2026, 10, 31, 10, 0, tzinfo=dt.UTC)
HOSTS = ["site.example", "slow.example", "busy.example", "check.example"]
BODY = "<p>ciao è</p>".encode()
WEB: dict[str, Response | Exception] = {
    "https://site.example/robots.txt": Response(200, {}, b"User-agent: *\nDisallow: /secret\n"),
    "https://site.example/page": Response(200, {"Content-Type": "text/html; charset=utf-8"}, BODY),
    "https://site.example/moved": Response(301, {"Location": "/page"}, b""),
    "https://site.example/away": Response(302, {"Location": "https://evil.example/x"}, b""),
    "https://slow.example/page": TimeoutError("timed out"),
    "https://busy.example/a": Response(429, {}, b""),
    "https://check.example/a": Response(200, {}, b"<title>Just a moment...</title>"),
}


def _fetcher(web: FakeWeb, cache: Path, day: dt.datetime = DAY) -> Fetcher:
    time = web.time or FakeTime()
    return Fetcher(
        allowed_hosts=HOSTS,
        clock=fixed_clock(day),
        monotonic=time.monotonic,
        sleep=time.sleep,
        transport=web,
        robots_cache=cache,
    )


def test_allowlist_robots_and_blocks(tmp_path: Path) -> None:
    web = FakeWeb(WEB)
    fetcher = _fetcher(web, tmp_path)
    page = fetcher.fetch("https://site.example/page")
    assert (page.status, page.text, page.fetched_at) == (200, "<p>ciao è</p>", DAY)
    assert page.content_sha256 == hashlib.sha256(BODY).hexdigest()
    assert [url for url, _, _ in web.calls] == [
        "https://site.example/robots.txt",
        "https://site.example/page",
    ]
    assert web.calls[1][1]["User-Agent"].startswith("Fantadamus/")

    with pytest.raises(NotAllowedError, match=r"other\.example"):
        fetcher.fetch("https://other.example/x")
    with pytest.raises(DisallowedError, match=r"robots\.txt"):
        fetcher.fetch("https://site.example/secret/x")
    assert fetcher.fetch("https://site.example/moved").url == "https://site.example/page"
    with pytest.raises(NotAllowedError, match=r"evil\.example"):
        fetcher.fetch("https://site.example/away")
    with pytest.raises(FetchFailedError, match="404"):
        fetcher.fetch("https://site.example/missing")
    with pytest.raises(FetchFailedError, match="timed out"):
        fetcher.fetch("https://slow.example/page")
    with pytest.raises(HostBlockedError, match="429"):
        fetcher.fetch("https://busy.example/a")
    calls = len(web.calls)
    with pytest.raises(HostBlockedError):
        fetcher.fetch("https://busy.example/b")  # the host is stopped for the run: no request
    assert len(web.calls) == calls
    with pytest.raises(HostBlockedError, match="bot check"):
        fetcher.fetch("https://check.example/a")
    assert not any(
        "other.example" in url or "evil.example" in url or "/secret" in url for url, _, _ in web.calls
    )

    later = FakeWeb(WEB)
    _fetcher(later, tmp_path).fetch("https://site.example/page")
    assert [url for url, _, _ in later.calls] == [
        "https://site.example/page"
    ]  # robots.txt from today's cache
    tomorrow = FakeWeb(WEB)
    _fetcher(tomorrow, tmp_path, DAY + dt.timedelta(days=1)).fetch("https://site.example/page")
    assert tomorrow.calls[0][0] == "https://site.example/robots.txt"


def test_budget_bounds_a_run(tmp_path: Path) -> None:
    time = FakeTime()
    timeouts: list[float] = []

    def slow(url: str, headers: Mapping[str, str], timeout: float) -> Response:
        timeouts.append(timeout)
        time.now += 20  # every answer takes 20 seconds
        return Response(404 if url.endswith("/robots.txt") else 200, {}, b"<p>ok</p>")

    def fetcher(cache: Path, budget: float) -> Fetcher:
        return Fetcher(
            allowed_hosts=["example.org"],
            clock=fixed_clock(dt.datetime(2026, 10, 31, tzinfo=dt.UTC)),
            monotonic=time.monotonic,
            sleep=time.sleep,
            transport=slow,
            robots_cache=cache,
            budget=budget,
        )

    run = fetcher(tmp_path / "a", budget=30)
    run.fetch("https://example.org/one")
    assert timeouts == [15.0, 10.0]  # robots.txt at the usual 15 seconds, then the page with what's left
    with pytest.raises(FetchFailedError, match="out of time"):
        run.fetch("https://example.org/two")
    assert len(timeouts) == 2  # nothing asked once the budget was gone
    with pytest.raises(FetchFailedError, match="out of time"):
        fetcher(tmp_path / "b", budget=0).fetch("https://example.org/one")
    assert not (tmp_path / "b").exists()  # robots.txt out of time is not cached as "fetch nothing today"


def test_block_expires(tmp_path: Path) -> None:
    """The server's long-lived fetcher behind read_page leaves a blocking host alone for `block_for` seconds,
    not until Claude restarts it."""
    time = FakeTime()
    web = FakeWeb(
        {
            "https://example.org/robots.txt": Response(404, {}, b""),
            "https://example.org/busy": Response(429, {}, b""),
            "https://example.org/page": Response(200, {}, b"<p>ok</p>"),
        },
        time,
    )
    fetcher = Fetcher(
        allowed_hosts=["example.org"],
        clock=fixed_clock(dt.datetime(2026, 10, 31, tzinfo=dt.UTC)),
        monotonic=time.monotonic,
        sleep=time.sleep,
        transport=web,
        robots_cache=tmp_path,
        block_for=3600,
    )
    with pytest.raises(HostBlockedError):
        fetcher.fetch("https://example.org/busy")
    time.now += 3599
    with pytest.raises(HostBlockedError, match="stopped"):
        fetcher.fetch("https://example.org/page")
    time.now += 2
    assert fetcher.fetch("https://example.org/page").text == "<p>ok</p>"
