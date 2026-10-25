"""Property P3: a URL passes only if its real host is an allowed host or a subdomain of one (R16.11)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from fantadamus.core.urls import host_allowed

ALLOWED = ("fantacalcio.it", "wikipedia.org")
LABEL = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=12).filter(
    lambda s: not s.startswith("-") and not s.endswith("-")
)


@given(sub=LABEL, path=st.text(alphabet="abcdef/", max_size=10))
def test_allowed_hosts_and_subdomains_pass(sub: str, path: str) -> None:
    assert host_allowed(f"https://fantacalcio.it/{path}", ALLOWED)
    assert host_allowed(f"https://{sub}.wikipedia.org/{path}", ALLOWED)


@given(evil=LABEL)
def test_allowlist_rejects_lookalikes(evil: str) -> None:
    for url in (
        f"https://fantacalcio.it.{evil}.example/x",
        f"https://{evil}fantacalcio.it/x",
        f"https://fantacalcio.it@{evil}.example/x",
        "https://user:pw@fantacalcio.it/x",
        f"ftp://fantacalcio.it/{evil}",
        f"https://{evil}.example/fantacalcio.it",
    ):
        assert not host_allowed(url, ALLOWED), url
