"""Task 4.2: every suppression names its rule, gives a reason and has an approved register row (R6)."""

from __future__ import annotations

from scripts.checks import suppressions as sup

HEADER = "| ID | Path | Rule | Reason | Approved |\n|---|---|---|---|---|\n"


def _register(*rows: tuple[str, str, str, str]) -> str:
    lines = [
        f"| S-{i:03d} | `{path}` | ruff `{rule}` | {reason} | {approved} |"
        for i, (path, rule, reason, approved) in enumerate(rows, start=1)
    ]
    return HEADER + "\n".join(lines) + "\n"


def _problems(source: str, register: str, path: str = "pkg/mod.py") -> list[str]:
    found = sup.find_in_python(path, source)
    return sup.problems(found, sup.parse_register(register))


APPROVED = _register(("pkg/mod.py", "S603", "fixed args", "2026-10-24"))


def test_noqa_without_code_fails() -> None:
    problems = _problems("run()  # noqa  # reason: fixed args\n", APPROVED)
    assert any("names no rule" in p for p in problems)


def test_noqa_without_reason_fails() -> None:
    problems = _problems("run()  # noqa: S603\n", APPROVED)
    assert any("no reason" in p for p in problems)


def test_reason_on_line_above_is_accepted() -> None:
    assert _problems("# reason: fixed args\nrun()  # noqa: S603\n", APPROVED) == []


def test_type_ignore_without_code_fails() -> None:
    register = _register(("pkg/mod.py", "attr-defined", "stub gap", "2026-10-24"))
    problems = _problems("x.y = 1  # type: ignore  # reason: stub gap\n", register)
    assert any("names no rule" in p for p in problems)


def test_unregistered_suppression_fails() -> None:
    problems = _problems("run()  # noqa: S607  # reason: git from PATH\n", APPROVED)
    assert any("no register row" in p for p in problems)


def test_blank_approval_date_fails() -> None:
    register = _register(("pkg/mod.py", "S603", "fixed args", ""))
    problems = _problems("run()  # noqa: S603  # reason: fixed args\n", register)
    assert any("no approval date" in p for p in problems)


def test_stale_register_row_fails() -> None:
    problems = _problems("run()\n", APPROVED)
    assert any("matches no suppression" in p for p in problems)


def test_skip_without_reason_fails() -> None:
    register = _register(("pkg/mod.py", "skip", "flaky upstream", "2026-10-24"))
    source = "import pytest\n\n@pytest.mark.skip\ndef test_x() -> None: ...\n"
    problems = _problems(source, register)
    assert any("no reason" in p for p in problems)


def test_skip_with_reason_and_row_passes() -> None:
    register = _register(("pkg/mod.py", "skip", "needs private data", "2026-10-24"))
    source = 'import pytest\n\n@pytest.mark.skip(reason="needs private data")\ndef test_x() -> None: ...\n'
    assert _problems(source, register) == []


def test_noqa_text_inside_a_string_is_not_a_suppression() -> None:
    assert sup.find_in_python("pkg/mod.py", 'text = "run()  # noqa"\n') == []


def test_checkov_skip_needs_reason() -> None:
    found = sup.find_in_terraform("infra/s.tf", "#checkov:skip=CKV_AWS_18\nresource {}\n")
    register = _register(("infra/s.tf", "CKV_AWS_18", "log bucket", "2026-10-24"))
    assert any("no reason" in p for p in sup.problems(found, sup.parse_register(register)))


def test_per_file_ignores_need_register_rows() -> None:
    pyproject = '[tool.ruff.lint.per-file-ignores]\n"tests/**" = ["S101"]\n'
    found = sup.find_per_file_ignores(pyproject)
    assert any("no register row" in p for p in sup.problems(found, sup.parse_register(HEADER)))
