"""Each scored round's report, by round number, under the git-ignored `data/local/calibration/`."""

from __future__ import annotations

from pathlib import Path

from fantadamus.core.files import temporary_beside
from fantadamus.domains.calibration import RoundReport

DEFAULT_ROOT = Path("data/local/calibration")


class CalibrationStore:
    """One file per round, derived and so recomputable: it isn't part of the decision log."""

    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def _path(self, round: int) -> Path:
        return self.root / f"round-{round}.json"

    def get(self, round: int) -> RoundReport | None:
        path = self._path(round)
        return RoundReport.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None

    def set(self, report: RoundReport) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(report.round)
        temporary = temporary_beside(path)
        temporary.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    def latest(self) -> RoundReport | None:
        rounds = [int(path.stem.removeprefix("round-")) for path in self.root.glob("round-*.json")]
        return self.get(max(rounds)) if rounds else None
