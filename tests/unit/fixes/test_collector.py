"""mvp-fixes task 1.2: each fetch error's outcome; a failed try is only a try that got no answer (design C1;
R1.1, R1.4)."""

from __future__ import annotations

from fantadamus.web.collector import _outcome
from fantadamus.web.fetch import (
    DisallowedError,
    FetchFailedError,
    HostBlockedError,
    NotAllowedError,
    OutOfTimeError,
    PageMissingError,
    RobotsUnreadableError,
)


def test_outcomes_by_error() -> None:
    assert _outcome(RobotsUnreadableError("robots.txt couldn't be read (timed out)")) == "failed"
    assert _outcome(FetchFailedError("https://site.example/page: timed out")) == "failed"
    assert _outcome(OutOfTimeError("out of time")) == "failed"
    assert _outcome(PageMissingError("https://site.example/page answered 404")) == "missing"
    assert _outcome(DisallowedError("robots.txt disallows https://site.example/page")) == "disallowed"
    assert _outcome(HostBlockedError("site.example answered 403")) == "blocked"
    assert _outcome(NotAllowedError("other.example is not on the allowlist")) == "not allowed"
