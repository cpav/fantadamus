"""The polite fetcher (mvp-collect design C1; R2; ADR-0004's rules, ADR-0006).

Before any request: the host must be on the allowlist and the path allowed by the host's robots.txt, which
is read at most once a day per host. Requests to one host are at least a second apart, carry a user agent
naming Fantadamus, and get one attempt. A block, a bot check or "too many requests" stops the host for the
rest of the run: nothing tries to get around it. Redirects are followed only within the same rules.
"""

from __future__ import annotations

import hashlib
import http.client
import importlib.metadata
import json
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from fantadamus.core.clock import Clock
from fantadamus.core.urls import host_allowed, url_host

ROBOTS_AGENT = "Fantadamus"
USER_AGENT = (
    f"{ROBOTS_AGENT}/{importlib.metadata.version('fantadamus')} (+https://github.com/cpav/fantadamus)"
)
DEFAULT_ROBOTS_CACHE = Path("data/local/collect/robots")
_BLOCK_STATUSES = {401, 403, 407, 429, 451, 503}
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_BOT_CHECK_MARKERS = ("captcha", "just a moment", "access denied", "cf-chl")
_BOT_CHECK_MAX_BYTES = 50_000
_MAX_REDIRECTS = 3


@dataclass(frozen=True)
class Response:
    status: int
    headers: Mapping[str, str]
    body: bytes


Transport = Callable[[str, Mapping[str, str], float], Response]


@dataclass(frozen=True)
class Page:
    url: str
    status: int
    fetched_at: object
    text: str
    content_sha256: str


class FetchError(Exception):
    """A page that wasn't fetched; the message says why."""


class NotAllowedError(FetchError):
    """The host isn't on the allowlist."""


class DisallowedError(FetchError):
    """robots.txt disallows the path."""


class HostBlockedError(FetchError):
    """The host answered with a block, a bot check or "too many requests"; it's stopped for the run."""


class FetchFailedError(FetchError):
    """A timeout, a network error or an unexpected status."""


def http_transport(url: str, headers: Mapping[str, str], timeout: float) -> Response:
    """One GET with the standard library's `http.client`, which never follows redirects by itself."""
    parts = urlsplit(url)
    connection_type = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    connection = connection_type(parts.hostname or "", parts.port, timeout=timeout)
    try:
        connection.request(
            "GET", (parts.path or "/") + (f"?{parts.query}" if parts.query else ""), headers=dict(headers)
        )
        answer = connection.getresponse()
        return Response(answer.status, dict(answer.getheaders()), answer.read())
    finally:
        connection.close()


class Fetcher:
    def __init__(
        self,
        *,
        allowed_hosts: Iterable[str],
        clock: Clock,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        transport: Transport = http_transport,
        robots_cache: Path = DEFAULT_ROBOTS_CACHE,
        timeout: float = 15.0,
        interval: float = 1.0,
    ) -> None:
        self._allowed = tuple(allowed_hosts)
        self._clock, self._monotonic, self._sleep = clock, monotonic, sleep
        self._transport, self._cache, self._timeout, self._interval = (
            transport,
            robots_cache,
            timeout,
            interval,
        )
        self._last: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}
        self._blocked: dict[str, str] = {}

    def fetch(self, url: str) -> Page:
        """The page at `url`, or a `FetchError` saying why not."""
        for _ in range(_MAX_REDIRECTS + 1):
            answer = self._get(url)
            location = answer.headers.get("Location") or answer.headers.get("location")
            if answer.status in _REDIRECT_STATUSES and location:
                url = urljoin(url, location)
                continue
            if answer.status != 200:
                raise FetchFailedError(f"{url} answered {answer.status}")
            return Page(
                url=url,
                status=200,
                fetched_at=self._clock(),
                text=answer.body.decode(_charset(answer.headers), errors="replace"),
                content_sha256=hashlib.sha256(answer.body).hexdigest(),
            )
        raise FetchFailedError(f"{url}: more than {_MAX_REDIRECTS} redirects")

    def _get(self, url: str) -> Response:
        host = url_host(url)
        if host is None or not host_allowed(url, self._allowed):
            raise NotAllowedError(f"{host or url} is not on the allowlist")
        if host in self._blocked:
            raise HostBlockedError(f"{host} stopped for this run: {self._blocked[host]}")
        if not self._rules(url, host).can_fetch(ROBOTS_AGENT, url):
            raise DisallowedError(f"robots.txt disallows {url}")
        answer = self._request(url, host)
        if answer.status in _BLOCK_STATUSES:
            self._blocked[host] = f"it answered {answer.status}"
            raise HostBlockedError(f"{host} answered {answer.status}; stopped for this run")
        if len(answer.body) < _BOT_CHECK_MAX_BYTES and any(
            marker in answer.body.decode("utf-8", errors="replace").lower() for marker in _BOT_CHECK_MARKERS
        ):
            self._blocked[host] = "a bot check"
            raise HostBlockedError(f"{host} showed a bot check; stopped for this run")
        return answer

    def _request(self, url: str, host: str) -> Response:
        wait = self._last.get(host, float("-inf")) + self._interval - self._monotonic()
        if wait > 0:
            self._sleep(wait)
        self._last[host] = self._monotonic()
        try:
            return self._transport(url, {"User-Agent": USER_AGENT}, self._timeout)
        except (OSError, ValueError) as error:  # timeouts and network errors are OSErrors
            raise FetchFailedError(f"{url}: {error}") from error

    def _rules(self, url: str, host: str) -> RobotFileParser:
        """The host's robots.txt, from today's cache or fetched now; unreadable means nothing is allowed."""
        if host in self._robots:
            return self._robots[host]
        today = self._clock().date().isoformat()
        cached = self._cache / f"{host}.json"
        status, text = None, ""
        if cached.is_file():
            entry = json.loads(cached.read_text(encoding="utf-8"))
            if entry["date"] == today:
                status, text = entry["status"], entry["text"]
        if status is None:
            robots_url = f"{urlsplit(url).scheme}://{urlsplit(url).netloc}/robots.txt"
            try:
                answer = self._request(robots_url, host)
                status, text = answer.status, answer.body.decode("utf-8", errors="replace")
            except FetchFailedError:
                status, text = 0, ""
            self._cache.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps({"date": today, "status": status, "text": text}), encoding="utf-8")
        rules = RobotFileParser()
        if status == 200:
            rules.parse(text.splitlines())
        elif status in (404, 410):
            rules.parse([])  # no robots.txt: everything is allowed
        else:
            rules.parse(["User-agent: *", "Disallow: /"])  # blocked, failed or unexpected: fetch nothing here
        self._robots[host] = rules
        return rules


def _charset(headers: Mapping[str, str]) -> str:
    content_type = headers.get("Content-Type") or headers.get("content-type") or ""
    for part in content_type.split(";"):
        name, _, value = part.strip().partition("=")
        if name.lower() == "charset" and value:
            return value.strip('"')
    return "utf-8"
