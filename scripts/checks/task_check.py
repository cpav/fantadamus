"""Before a task starts: are its dependencies done, its requirements and tests named, its ADRs Accepted?
(R17.4, R18.4)

Reads `.kiro/specs/engineering-foundation/tasks.md`. A task or sub-task is done when its box is ticked
(`- [x]`), which happens on its own branch and reaches `main` with the owner's merge. Every sub-task needs
a `_Test:_` line and a `_Requirements:_` line whose R-IDs exist in requirements.md; an **Owner** step may
name a gate instead of R-IDs. If anything is missing the check fails, and the agent stops and asks the owner.

Usage: python -m scripts.checks.task_check <task id, e.g. 9 or 9.3>   (make task-check TASK=9)
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from scripts.checks._common import CheckResult, report

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / ".kiro" / "specs" / "engineering-foundation"
TASKS = SPEC / "tasks.md"
REQUIREMENTS = SPEC / "requirements.md"
ADR_DIR = ROOT / "docs" / "adr"

_TASK = re.compile(r"^- \[(?P<done>[ xX])\] (?P<id>\d+)\. (?P<title>.*)$")
_SUBTASK = re.compile(r"^  - \[(?P<done>[ xX])\] (?P<id>\d+\.\d+) (?P<title>.*)$")
_FIELD = re.compile(r"^    - _(?P<name>Requirements|Test):\s*(?P<text>.*)$")
_META = re.compile(r"Depends on:\s*(?P<deps>[^·]*?)\s*·\s*ADRs:\s*(?P<adrs>.*)$")
_REQUIREMENT = re.compile(r"\bR\d+\.\d+\b")
_ADR = re.compile(r"\bADR-\d{4}\b")
_STATUS = re.compile(r"^- \*\*Status:\*\*\s*(?P<status>\w+)", re.M)


@dataclass
class SubTask:
    id: str
    title: str
    done: bool
    requirements_text: str | None = None
    test: str | None = None

    @property
    def owner(self) -> bool:
        return self.title.startswith("**Owner")

    @property
    def requirements(self) -> list[str]:
        return _REQUIREMENT.findall(self.requirements_text or "")


@dataclass
class Task:
    id: str
    title: str
    done: bool
    depends: list[str] = field(default_factory=list)
    adrs: list[str] = field(default_factory=list)
    subtasks: list[SubTask] = field(default_factory=list)


def parse_tasks(text: str) -> dict[str, Task]:
    """Tasks by ID, with dependencies, ADRs and sub-tasks. Field lines may continue on indented lines."""
    tasks: dict[str, Task] = {}
    task: Task | None = None
    sub: SubTask | None = None
    current: str | None = None
    for line in text.splitlines():
        if match := _TASK.match(line):
            task = Task(match["id"], match["title"], match["done"] != " ")
            tasks[task.id] = task
            sub, current = None, None
        elif task is None:
            continue
        elif match := _SUBTASK.match(line):
            sub = SubTask(match["id"], match["title"], match["done"] != " ")
            task.subtasks.append(sub)
            current = None
        elif sub is None and (match := _META.search(line)):
            deps = match["deps"].strip()
            task.depends = [] if deps.lower() in {"none", ""} else [dep.strip() for dep in deps.split(",")]
            task.adrs = _ADR.findall(match["adrs"])
        elif sub is not None and (match := _FIELD.match(line)):
            current = match["name"]
            _append(sub, current, match["text"])
        elif sub is not None and current is not None and line.startswith("      ") and line.strip():
            _append(sub, current, line.strip())
        else:
            current = None
    return tasks


def _append(sub: SubTask, name: str, text: str) -> None:
    text = text.rstrip("_").strip()
    if name == "Requirements":
        sub.requirements_text = f"{sub.requirements_text} {text}" if sub.requirements_text else text
    else:
        sub.test = f"{sub.test} {text}" if sub.test else text


def done_ids(tasks: Mapping[str, Task]) -> set[str]:
    done = {task.id for task in tasks.values() if task.done}
    done |= {sub.id for task in tasks.values() for sub in task.subtasks if sub.done}
    return done


def requirement_ids(text: str) -> set[str]:
    return set(re.findall(r"^- \*\*(R\d+\.\d+)\*\*", text, re.M))


def adr_statuses(adr_dir: Path) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for path in sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md")):
        match = _STATUS.search(path.read_text(encoding="utf-8"))
        statuses[f"ADR-{path.name[:4]}"] = match["status"] if match else "without a status"
    return statuses


def _subtask_problems(sub: SubTask, known: set[str]) -> list[str]:
    issues: list[str] = []
    if not sub.requirements and not (sub.owner and sub.requirements_text):
        issues.append(f"{sub.id} names no requirement IDs")
    issues.extend(
        f"{sub.id} names {rid}, which is not in requirements.md"
        for rid in sub.requirements
        if rid not in known
    )
    if not sub.test:
        issues.append(f"{sub.id} names no test")
    return issues


def problems(task_id: str, tasks: Mapping[str, Task], known: set[str], adrs: Mapping[str, str]) -> list[str]:
    """What stops this task (or sub-task) from starting."""
    task = tasks.get(task_id.split(".")[0])
    subs = [sub for sub in task.subtasks if sub.id == task_id] if task else []
    if task is None or ("." in task_id and not subs):
        return [f"no task {task_id} in tasks.md"]
    done = done_ids(tasks)
    issues = [f"dependency {dep} is not complete" for dep in task.depends if dep not in done]
    for adr in task.adrs:
        status = adrs.get(adr)
        if status is None:
            issues.append(f"{adr} does not exist")
        elif status != "Accepted":
            issues.append(f"{adr} is {status}, not Accepted")
    for sub in subs or task.subtasks:
        issues.extend(_subtask_problems(sub, known))
    return issues


def check(task_id: str) -> CheckResult:
    issues = problems(
        task_id,
        parse_tasks(TASKS.read_text(encoding="utf-8")),
        requirement_ids(REQUIREMENTS.read_text(encoding="utf-8")),
        adr_statuses(ADR_DIR),
    )
    if issues:
        return CheckResult("task-check", ok=False, message=f"task {task_id}: " + "; ".join(issues))
    return CheckResult("task-check", ok=True, message=f"task {task_id} is ready to start")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", help="task or sub-task ID, e.g. 9 or 9.3")
    return report(check(parser.parse_args(argv).task))


if __name__ == "__main__":
    raise SystemExit(main())
