"""mvp-store task 5.2: one process times every budget for a whole run, and each test reads its own number
(design C7; R5.1, R5.2)."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from tests.timings import shared


def test_one_process_for_a_whole_run(tmp_path: Path) -> None:
    """Four tests asking at once, as four workers do: the first measures, the others wait for it and read its
    result."""
    measured: list[int] = []

    def measure() -> dict[str, Any]:
        measured.append(threading.get_ident())
        time.sleep(0.2)  # long enough for the others to arrive while it measures
        return {"lineup": 0.5, "season": {"store": 0.4}}

    found: list[dict[str, Any]] = []

    def ask() -> None:
        found.append(shared(tmp_path / "timings.json", measure))

    workers = [threading.Thread(target=ask) for _ in range(4)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert len(measured) == 1
    assert found == [{"lineup": 0.5, "season": {"store": 0.4}}] * 4
    assert shared(tmp_path / "timings.json", measure) == found[0]  # and later, from the file alone
    assert len(measured) == 1
