"""Shared by the `mvp-collect` tests: a fake web for unit tests and a real local site for acceptance tests."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fantadamus.web.fetch import Response


@dataclass
class FakeTime:
    """A monotonic clock and a sleep that advances it, so rate limits cost no real time."""

    now: float = 1000.0
    slept: list[float] = field(default_factory=list)

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@dataclass
class FakeWeb:
    """A transport answering from `routes` (a Response, or an exception to raise), recording each call."""

    routes: Mapping[str, Response | Exception]
    time: FakeTime | None = None
    calls: list[tuple[str, dict[str, str], float]] = field(default_factory=list)

    def __call__(self, url: str, headers: Mapping[str, str], timeout: float) -> Response:
        self.calls.append((url, dict(headers), self.time.now if self.time else 0.0))
        answer = self.routes.get(url, Response(404, {}, b""))
        if isinstance(answer, Exception):
            raise answer
        return answer


@dataclass
class LocalSite:
    """A real HTTP server on 127.0.0.1: `routes` maps a path to (status, headers, body)."""

    routes: Mapping[str, tuple[int, dict[str, str], bytes]]
    requests: list[tuple[str, float]] = field(default_factory=list)
    base_url: str = ""


@contextmanager
def local_site(routes: Mapping[str, tuple[int, dict[str, str], bytes]]) -> Iterator[LocalSite]:
    site = LocalSite(routes)

    def get(handler: BaseHTTPRequestHandler) -> None:
        site.requests.append((handler.path, time.monotonic()))
        status, headers, body = site.routes.get(handler.path, (404, {}, b""))
        handler.send_response(status)
        for name, value in headers.items():
            handler.send_header(name, value)
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def quiet(handler: BaseHTTPRequestHandler, *args: object) -> None:
        pass

    # http.server calls a method named do_GET; building the class this way keeps that name a plain string.
    handler = type("Handler", (BaseHTTPRequestHandler,), {"do_GET": get, "log_message": quiet})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    site.base_url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield site
    finally:
        server.shutdown()
        server.server_close()
