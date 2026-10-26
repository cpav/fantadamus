"""Task 9.5: `make task-check TASK=<id>` before every task (R17.4, R18.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.checks import task_check

REQUIREMENTS = (
    "- **R1.1** THE SYSTEM SHALL a.\n- **R1.2** THE SYSTEM SHALL b.\n- **R2.1** THE SYSTEM SHALL c.\n"
)
TASKS = """# Implementation Plan

- [x] 1. First task
  - Branch: `chore/ef-1-first` · Depends on: none · ADRs: none
  - [x] 1.1 Do the first thing
    - _Requirements: R1.1_
    - _Test: `tests/unit/test_a.py::test_a`_
  - [ ] 1.2 Do the second thing, over
    two lines
    - _Requirements: R1.2,
      R2.1_
    - _Test: `tests/unit/test_b.py::test_b`,
      `::test_c`_

- [ ] 2. Second task
  - Branch: `feat/ef-2-second` · Depends on: 1 · ADRs: ADR-0001
  - [ ] 2.1 Build it
    - _Requirements: R2.1_
    - _Test: `tests/unit/test_d.py::test_d`_
  - [ ] 2.2 **Owner:** approve it
    - _Requirements: Phase gate (`quality.md`)_
    - _Test: sign-off recorded_

- [ ] 3. Third task
  - Branch: `feat/ef-3-third` · Depends on: 1.1 · ADRs: ADR-0001, ADR-0002
  - [ ] 3.1 Build more
    - _Requirements: R9.9_
  - [ ] 3.2 Build without saying why
    - _Test: `tests/unit/test_e.py::test_e`_
"""


@pytest.fixture
def adr_dir(tmp_path: Path) -> Path:
    adrs = tmp_path / "adr"
    adrs.mkdir()
    (adrs / "0001-tools.md").write_text(
        "# ADR-0001\n\n- **Status:** Accepted by the owner, 2026-10-24\n", encoding="utf-8"
    )
    (adrs / "0002-iac.md").write_text("# ADR-0002\n\n- **Status:** Proposed, 2026-10-25\n", encoding="utf-8")
    return adrs


def _problems(task: str, tasks: str, adr_dir: Path) -> list[str]:
    return task_check.problems(
        task,
        task_check.parse_tasks(tasks),
        task_check.requirement_ids(REQUIREMENTS),
        task_check.adr_statuses(adr_dir),
    )


def test_ready_task_passes(adr_dir: Path) -> None:
    assert _problems("2", TASKS, adr_dir) == []
    assert _problems("2.1", TASKS, adr_dir) == []


def test_unfinished_dependency_fails(adr_dir: Path) -> None:
    tasks = TASKS.replace("- [x] 1. First task", "- [ ] 1. First task")
    assert _problems("2", tasks, adr_dir) == ["dependency 1 is not complete"]
    assert "dependency 1.1 is not complete" in _problems(
        "3", TASKS.replace("- [x] 1.1", "- [ ] 1.1"), adr_dir
    )


def test_unaccepted_adr_fails(adr_dir: Path) -> None:
    assert "ADR-0002 is Proposed, not Accepted" in _problems("3", TASKS, adr_dir)
    (adr_dir / "0002-iac.md").unlink()
    assert "ADR-0002 does not exist" in _problems("3", TASKS, adr_dir)


def test_missing_requirements_fails(adr_dir: Path) -> None:
    issues = _problems("3", TASKS, adr_dir)
    assert "3.1 names R9.9, which is not in requirements.md" in issues
    assert "3.1 names no test" in issues
    assert "3.2 names no requirement IDs" in issues
    assert _problems("3.2", TASKS, adr_dir) == [
        "ADR-0002 is Proposed, not Accepted",
        "3.2 names no requirement IDs",
    ]


def test_multi_line_fields_and_owner_steps_parse() -> None:
    tasks = task_check.parse_tasks(TASKS)
    second = tasks["1"].subtasks[1]
    assert second.requirements == ["R1.2", "R2.1"]
    assert second.test is not None
    assert "::test_c" in second.test
    owner = tasks["2"].subtasks[1]
    assert owner.owner
    assert owner.requirements == []
    assert tasks["3"].depends == ["1.1"]
    assert tasks["3"].adrs == ["ADR-0001", "ADR-0002"]
    assert task_check.done_ids(tasks) == {"1", "1.1"}


def test_unknown_task_fails(adr_dir: Path) -> None:
    assert _problems("99", TASKS, adr_dir) == ["no task 99 in tasks.md"]


@pytest.mark.parametrize("spec", task_check.specs())
def test_repo_tasks_are_well_formed(spec: str) -> None:
    tasks_md, requirements_md = task_check.spec_files(spec)
    tasks = task_check.parse_tasks(tasks_md.read_text(encoding="utf-8"))
    known = task_check.requirement_ids(requirements_md.read_text(encoding="utf-8"))
    assert tasks, spec
    for task in tasks.values():
        assert task.subtasks, (spec, task.id)
        for sub in task.subtasks:
            assert sub.test, (spec, sub.id)
            assert sub.owner or sub.requirements, (spec, sub.id)
            assert set(sub.requirements) <= known, (spec, sub.id)


def test_each_spec_has_its_own_tasks() -> None:
    assert {"engineering-foundation", "mvp-x-or-y"} <= set(task_check.specs())
    assert task_check.check("1", "engineering-foundation").ok  # finished long ago
    assert task_check.check("99", "mvp-x-or-y").message == "mvp-x-or-y task 99: no task 99 in tasks.md"


def test_main_reports(capsys: pytest.CaptureFixture[str]) -> None:
    assert task_check.main(["--spec", "engineering-foundation", "1"]) == 0
    assert capsys.readouterr().out.startswith("PASS task-check: engineering-foundation task 1")
    assert task_check.main(["--spec", "engineering-foundation", "99"]) == 1
    assert "no task 99" in capsys.readouterr().err
