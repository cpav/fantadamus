"""Allowlist matching on a URL's real host (R16.11).

A URL passes only if it is http(s), carries no user-info (`https://fantacalcio.it@evil.example`), has a
well-formed host, and that host equals an allowed host or is a subdomain of one. Matching is on whole DNS
labels, so `fantacalcio.it.evil.example` and `evilfantacalcio.it` fail.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import urlsplit

_HOST = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*")


def _normalise_host(host: str) -> str:
    return host.lower().rstrip(".")


def url_host(url: str) -> str | None:
    """The URL's host, lower-cased and without a trailing dot, or None if the URL isn't acceptable."""
    try:
        parts = urlsplit(url)
        _ = parts.port  # raises ValueError on a malformed port
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or "@" in parts.netloc or not parts.hostname:
        return None
    host = _normalise_host(parts.hostname)
    return host if _HOST.fullmatch(host) else None


def host_allowed(url: str, allowed_hosts: Iterable[str]) -> bool:
    """True if the URL's host is an allowed host or a subdomain of one."""
    host = url_host(url)
    if host is None:
        return False
    for allowed in filter(None, map(_normalise_host, allowed_hosts)):
        if host == allowed or host.endswith("." + allowed):
            return True
    return False
