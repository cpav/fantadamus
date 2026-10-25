"""Task 8.1: the injected clock and URL host matching."""

from __future__ import annotations

import datetime as dt

import pytest

from fantadamus.core.clock import fixed_clock, utc_now
from fantadamus.core.urls import host_allowed


def test_utc_now_is_timezone_aware() -> None:
    assert utc_now().tzinfo is dt.UTC


def test_fixed_clock_returns_its_instant_in_utc() -> None:
    instant = dt.datetime(2026, 10, 25, 12, 0, tzinfo=dt.UTC)
    assert fixed_clock(instant)() == instant
    with pytest.raises(ValueError, match="timezone-aware"):
        fixed_clock(dt.datetime(2026, 10, 25, 12, 0))


@pytest.mark.parametrize(
    "url",
    ["https://FANTACALCIO.IT/x", "https://www.fantacalcio.it./x", "http://fantacalcio.it:8443/x"],
)
def test_host_matching_normalises_case_dots_and_ports(url: str) -> None:
    assert host_allowed(url, ["fantacalcio.it"])


@pytest.mark.parametrize("url", ["not a url", "https:///nohost", "", "https://fantacalcio.it"])
def test_malformed_urls_are_rejected_unless_valid(url: str) -> None:
    assert host_allowed(url, ["fantacalcio.it"]) == (url == "https://fantacalcio.it")
