"""P1 and P2: one request a second per host, and never a path robots.txt disallows (design C1; R2.1, R2.2)."""

from __future__ import annotations

import contextlib
import datetime as dt
import tempfile
from pathlib import Path
from urllib.robotparser import RobotFileParser

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.core.clock import fixed_clock
from fantadamus.web.fetch import Fetcher, FetchError, Response
from tests.collect_harness import FakeTime, FakeWeb

HOSTS = ["a.example", "b.example", "c.example"]
DAY = dt.datetime(2026, 10, 31, tzinfo=dt.UTC)
paths = st.lists(st.sampled_from(["x", "y", "private", "z"]), min_size=1, max_size=3).map(
    lambda parts: "/" + "/".join(parts)
)
requests = st.lists(st.tuples(st.sampled_from(HOSTS), paths), min_size=1, max_size=12)


def _run(web: FakeWeb, time: FakeTime, visits: list[tuple[str, str]]) -> None:
    with tempfile.TemporaryDirectory() as cache:
        fetcher = Fetcher(
            allowed_hosts=HOSTS,
            clock=fixed_clock(DAY),
            monotonic=time.monotonic,
            sleep=time.sleep,
            transport=web,
            robots_cache=Path(cache),
        )
        for host, path in visits:
            with contextlib.suppress(FetchError):
                fetcher.fetch(f"https://{host}{path}")


@given(requests)
def test_p1_one_request_per_second(visits: list[tuple[str, str]]) -> None:
    time = FakeTime()
    web = FakeWeb({}, time=time)
    _run(web, time, visits)
    last: dict[str, float] = {}
    for url, _, at in web.calls:
        host = url.split("/")[2]
        assert host not in last or at - last[host] >= 1.0 - 1e-9, (url, at, last[host])
        last[host] = at


@given(st.lists(paths, max_size=3), requests)
def test_p2_robots_never_broken(disallowed: list[str], visits: list[tuple[str, str]]) -> None:
    robots = "User-agent: *\n" + "".join(f"Disallow: {path}\n" for path in disallowed)
    time = FakeTime()
    web = FakeWeb(
        {f"https://{host}/robots.txt": Response(200, {}, robots.encode()) for host in HOSTS}, time=time
    )
    _run(web, time, visits)
    rules = RobotFileParser()
    rules.parse(robots.splitlines())
    for url, _, _ in web.calls:
        assert url.endswith("/robots.txt") or rules.can_fetch("Fantadamus", url), url
