"""mvp-next-round AT-3: a page that shows the locked round for three weeks is read each day, never twice in 24
hours, and stores nothing new; the first read after it changes stores the next round (R1.2, R2.2).

"Nothing new" is no fact that wasn't stored before: an unchanged page's facts are stored once more after 14
days, so that answers still find them (`mvp-store`), and their hashes stay those of the first read."""

from __future__ import annotations

import itertools
from pathlib import Path

from fantadamus.domains.fixtures.silver import FIXTURES
from tests.next_round_harness import DAY, FIRST, HOUR, a_schedule, moving_on

CHANGES = FIRST + 21 * DAY


def test_at3_it_keeps_looking(tmp_path: Path) -> None:
    here = a_schedule(tmp_path, moving_on(CHANGES + 9 * DAY, at=CHANGES))
    here.runs(FIRST - HOUR, FIRST, HOUR)
    first = {record.envelope.content_sha256 for record in here.store.read_bronze(FIXTURES.source)}

    reads = here.runs(FIRST, CHANGES, 3 * HOUR)
    times = [when for when, _ in reads]
    assert len(times) == 20
    assert all(later - earlier >= DAY for earlier, later in itertools.pairwise(times))
    assert {report.pages[0].outcome for _, report in reads} <= {"unchanged", "stored"}
    assert {record.envelope.content_sha256 for record in here.store.read_bronze(FIXTURES.source)} == first
    assert here.next_round(CHANGES) is None

    here.runs(CHANGES, CHANGES + DAY, 3 * HOUR)
    assert here.next_round(CHANGES + DAY) == 11
