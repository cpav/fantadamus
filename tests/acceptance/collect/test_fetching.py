"""AT-2 and AT-3: polite fetching against a real local server (R2.1 to R2.3)."""

from __future__ import annotations

import itertools
import time
from collections.abc import Mapping
from pathlib import Path

import pytest

from fantadamus.core.clock import utc_now
from fantadamus.web.fetch import DisallowedError, Fetcher, HostBlockedError, Response, http_transport
from tests.collect_harness import local_site

PAGE = (200, {"Content-Type": "text/html; charset=utf-8"}, b"<p>ok</p>")


def test_at2_disallowed_never_requested(tmp_path: Path) -> None:
    routes = {
        "/robots.txt": (200, {}, b"User-agent: *\nDisallow: /private\n"),
        "/private/page": PAGE,
        "/open": PAGE,
    }
    with local_site(routes) as site:
        fetcher = Fetcher(allowed_hosts=["127.0.0.1"], clock=utc_now, robots_cache=tmp_path)
        with pytest.raises(DisallowedError):
            fetcher.fetch(f"{site.base_url}/private/page")
        assert fetcher.fetch(f"{site.base_url}/open").text == "<p>ok</p>"
    assert [path for path, _ in site.requests] == ["/robots.txt", "/open"]


def test_at3_rate_and_too_many_requests(tmp_path: Path) -> None:
    """A second between requests to a host, timed as the fetcher sends them: the server's thread can be slow
    to pick a request up when the machine is busy, which used to make this test fail on a gap the fetcher had
    kept. A host that answers 429 is left alone for the rest of the run."""
    routes = {"/robots.txt": (404, {}, b""), "/a": PAGE, "/b": PAGE, "/busy": (429, {}, b"")}
    sent: list[float] = []

    def timed(url: str, headers: Mapping[str, str], timeout: float) -> Response:
        sent.append(time.monotonic())
        return http_transport(url, headers, timeout)

    with local_site(routes) as site:
        fetcher = Fetcher(allowed_hosts=["127.0.0.1"], clock=utc_now, robots_cache=tmp_path, transport=timed)
        fetcher.fetch(f"{site.base_url}/a")
        fetcher.fetch(f"{site.base_url}/b")
        with pytest.raises(HostBlockedError):
            fetcher.fetch(f"{site.base_url}/busy")
        with pytest.raises(HostBlockedError):
            fetcher.fetch(f"{site.base_url}/a")
    assert [path for path, _ in site.requests] == ["/robots.txt", "/a", "/b", "/busy"]
    assert len(sent) == 4
    assert all(later - earlier >= 0.99 for earlier, later in itertools.pairwise(sent))
