"""Each scored round's report and its calibration set, by round number, and the last recalibration proposal,
under the git-ignored `data/local/calibration/`."""

from __future__ import annotations

import re
from pathlib import Path

from fantadamus.core.files import temporary_beside
from fantadamus.domains.calibration import CalibrationSet, RoundReport
from fantadamus.domains.recalibration import Proposal

DEFAULT_ROOT = Path("data/local/calibration")
_REPORT = re.compile(r"round-(\d+)\.json")
_SET = re.compile(r"round-(\d+)\.set\.json")


class CalibrationStore:
    """One report and one set per round, derived and so recomputable: they aren't part of the decision log."""

    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root

    def _path(self, round: int) -> Path:
        return self.root / f"round-{round}.json"

    def _set_path(self, round: int) -> Path:
        return self.root / f"round-{round}.set.json"

    def get(self, round: int) -> RoundReport | None:
        path = self._path(round)
        return RoundReport.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None

    def set(self, report: RoundReport) -> None:
        self._write(self._path(report.round), report.model_dump_json(indent=2))

    def calibration_set(self, round: int) -> CalibrationSet | None:
        path = self._set_path(round)
        return (
            CalibrationSet.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None
        )

    def keep_set(self, kept: CalibrationSet) -> None:
        """Kept compact: it's for a fit to read, not for reading."""
        self._write(self._set_path(kept.round), kept.model_dump_json())

    def set_rounds(self) -> list[int]:
        """The rounds with a calibration set stored, in order."""
        found = (_SET.fullmatch(path.name) for path in self.root.glob("round-*.set.json"))
        return sorted(int(match[1]) for match in found if match)

    def proposal(self) -> Proposal | None:
        """The last recalibration proposal (mvp-recalibrate C8)."""
        path = self.root / "proposal.json"
        return Proposal.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else None

    def keep_proposal(self, proposal: Proposal) -> None:
        self._write(self.root / "proposal.json", proposal.model_dump_json(indent=2))

    def _write(self, path: Path, text: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = temporary_beside(path)
        temporary.write_text(text + "\n", encoding="utf-8")
        temporary.replace(path)

    def latest(self) -> RoundReport | None:
        rounds = [
            int(found[1])
            for path in self.root.glob("round-*.json")
            if (found := _REPORT.fullmatch(path.name))
        ]
        return self.get(max(rounds)) if rounds else None
