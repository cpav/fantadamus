"""One of two runs storing at once (mvp-store AT-3): `python -m tests.store_runs <lake> <name> <count> <go>`
says it's ready, waits for the file `go` to appear, then stores `count` reads of its own page, one after
another, by the real clock."""

from __future__ import annotations

import sys
import time
from collections.abc import Sequence
from pathlib import Path

from fantadamus.core.clock import utc_now
from fantadamus.domains import facts
from fantadamus.domains.fixtures.silver import FIXTURES
from fantadamus.lake.duckdb_store import LakeStore
from tests.store_lake import HOSTS, fixtures
from tests.xy_harness import CLUBS


def page_of(name: str) -> str:
    return f"https://example.org/{name}"


def main(argv: Sequence[str]) -> int:
    lake, name, count, go = Path(argv[0]), argv[1], int(argv[2]), Path(argv[3])
    store = LakeStore(lake)
    (go.parent / f"{name}.ready").touch()
    while not go.exists():
        time.sleep(0.005)
    for index in range(count):
        facts.submit(
            store,
            FIXTURES,
            fixtures(1 + index % 38, hours=24 + len(name)),
            source_url=page_of(name),
            captured_at=utc_now(),
            published_at=None,
            allowed_hosts=HOSTS,
            clock=utc_now,
            submitted_by=name,
            clubs=CLUBS,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
