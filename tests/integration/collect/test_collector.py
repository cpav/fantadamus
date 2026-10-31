"""mvp-collect task 4.2: the collector reads the round page and stores its facts as `collector` (design C6;
R1.1, R1.4, R2.4, R2.5, R3.4)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from fantadamus.domains.availability.silver import OUTLET_VIEWS
from fantadamus.domains.facts import read_silver
from fantadamus.domains.odds.silver import ODDS
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.web.collector import ROUND_FACTS
from fantadamus.web.fetch import Response
from tests.collect_harness import HTML, ROUND_ROUTE, FakeWeb, local_site, round_collector
from tests.collect_pages import FcoMatch, fco_round_page


def _page(**percents: tuple[int | None, ...]) -> bytes:
    alfa = FcoMatch("Alfa", "Beta", percents=percents)
    return fco_round_page(alfa, FcoMatch("Gamma", "Delta", kickoff="31/10/2026 18:00")).encode()


def test_collect_round_from_local_pages(tmp_path: Path) -> None:
    routes = {"/robots.txt": (404, {}, b""), ROUND_ROUTE: (200, HTML, _page())}
    with local_site(routes) as site:
        store = LakeStore(tmp_path / "lake")
        collector = round_collector(store, site.base_url, tmp_path / "robots")
        [first] = collector.collect().pages
        routes[ROUND_ROUTE] = (200, HTML, _page(**{"Alfa Nove": (90, 90, 55, 90)}))  # one outlet moves
        [second] = collector.collect().pages
    assert first.url == site.base_url + ROUND_ROUTE
    assert (first.outcome, first.reason, first.problems) == ("stored", None, [])
    assert first.stored == {"fixtures": 2, "odds": 2, "outlet_views": 224}  # 28 rows per outlet per match
    envelopes = [record.envelope for record in store.read_bronze(OUTLET_VIEWS.source)]
    assert {(envelope.submitted_by, envelope.source_url) for envelope in envelopes} == {
        ("collector", first.url)
    }
    assert first.fetched_at is not None
    assert min(envelope.captured_at for envelope in envelopes) == first.fetched_at
    [alfa_odds] = [
        record.envelope
        for record in store.read_bronze(ODDS.source)
        if isinstance(record.envelope.payload, dict) and record.envelope.payload["home"] == "Alfa"
    ]
    assert alfa_odds.published_at == dt.datetime(
        2026, 10, 30, 17, 13, tzinfo=dt.UTC
    )  # the page's update time
    assert [row.p_over for row in read_silver(store, ODDS)] == [pytest.approx(0.53)] * 2
    assert (second.outcome, second.stored) == ("stored", {"outlet_views": 224})  # only what changed


def test_switched_off_source(tmp_path: Path) -> None:
    web = FakeWeb({})
    collector = round_collector(
        LakeStore(tmp_path / "lake"),
        "https://example.org",
        tmp_path,
        transport=web,
        hosts=["example.org"],
        enabled=False,
    )
    [read] = collector.collect().pages
    assert (read.outcome, read.for_claude) == ("switched off", list(ROUND_FACTS))
    assert web.calls == []


def test_failures_named(tmp_path: Path) -> None:
    base = "https://example.org"
    web = FakeWeb(
        {
            f"{base}/robots.txt": Response(
                200, {}, b"User-agent: *\nDisallow: /probabili-formazioni/10-giornata\n"
            ),
            f"{base}{ROUND_ROUTE}": Response(429, {}, b""),
        }
    )
    store = LakeStore(tmp_path / "lake")
    collector = round_collector(store, base, tmp_path / "robots", transport=web, hosts=["example.org"])
    [numbered] = collector.collect(round=10).pages
    assert (numbered.url, numbered.outcome) == (f"{base}/probabili-formazioni/10-giornata", "disallowed")
    [blocked] = collector.collect().pages
    assert blocked.outcome == "blocked"
    assert blocked.reason is not None
    assert "429" in blocked.reason
    assert blocked.for_claude == list(ROUND_FACTS)
    assert not (tmp_path / "lake" / "bronze").exists()
    unknown = fco_round_page(FcoMatch("Omega", "Zeta"), round=11).encode()
    web.routes = {**web.routes, f"{base}/probabili-formazioni/11-giornata": Response(200, HTML, unknown)}
    [refused] = collector.collect(round=11).pages
    assert (refused.outcome, refused.reason, refused.for_claude) == (
        "rejected",
        "every payload was refused",
        list(ROUND_FACTS),
    )
    assert "unknown club 'Omega'" in refused.problems[0]
