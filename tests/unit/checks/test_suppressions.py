"""Task 4.2: every suppression names its rule, gives a reason and has an approved register row (R6)."""

from __future__ import annotations

from pathlib import Path

from scripts.checks import suppressions as sup
from scripts.checks._common import run_command

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


def test_tflint_ignore_reason_inline_or_above() -> None:
    register = sup.parse_register(
        _register(("infra/s.tf", "aws_s3_bucket_name", "legacy name", "2026-10-24"))
    )
    inline = sup.find_in_terraform(
        "infra/s.tf", "# tflint-ignore: aws_s3_bucket_name  # reason: legacy name\n"
    )
    above = sup.find_in_terraform(
        "infra/s.tf", "# reason: legacy name\n# tflint-ignore: aws_s3_bucket_name\n"
    )
    missing = sup.find_in_terraform("infra/s.tf", "x = 1\n# tflint-ignore: aws_s3_bucket_name\n")
    assert sup.problems(inline, register) == []
    assert sup.problems(above, register) == []
    assert any("no reason" in p for p in sup.problems(missing, register))


def test_checkov_skip_with_reason_and_row_passes() -> None:
    found = sup.find_in_terraform(
        "infra/s.tf", "#checkov:skip=CKV_AWS_18:the log bucket cannot log to itself\n"
    )
    register = sup.parse_register(_register(("infra/s.tf", "CKV_AWS_18", "log bucket", "2026-10-24")))
    assert sup.problems(found, register) == []


def test_gitleaks_allowlist_needs_description() -> None:
    text = '[[allowlists]]\nid = "fixture-key"\npaths = ["tests/fixtures/x"]\n'
    found = sup.find_in_allowlists(".gitleaks.toml", text)
    register = sup.parse_register(_register((".gitleaks.toml", "fixture-key", "synthetic key", "2026-10-24")))
    assert any("no reason" in p for p in sup.problems(found, register))
    described = text.replace('id = "fixture-key"', 'id = "fixture-key"\ndescription = "synthetic test key"')
    assert sup.problems(sup.find_in_allowlists(".gitleaks.toml", described), register) == []


def test_audit_allowlist_needs_reason() -> None:
    path = "config/audit-allowlist.toml"
    found = sup.find_in_allowlists(path, '[[ignore]]\nid = "PYSEC-2026-1"\nexpires = 2026-12-31\n')
    register = sup.parse_register(_register((path, "PYSEC-2026-1", "no fix yet", "2026-10-24")))
    assert any("no reason" in p for p in sup.problems(found, register))


def test_non_skip_pytest_attributes_are_ignored() -> None:
    source = "import pytest\n\n@pytest.mark.parametrize('x', [1])\ndef test_x(x: int) -> None: ...\n"
    assert sup.find_in_python("pkg/mod.py", source) == []


def test_check_scans_a_repository(tmp_path: Path) -> None:
    def git(*args: str) -> None:
        assert run_command(["git", "-C", str(tmp_path), *args]).returncode == 0

    git("init", "-q")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("run()  # noqa: S603  # reason: fixed args\n", encoding="utf-8")
    (tmp_path / "infra").mkdir()
    (tmp_path / "infra" / "s.tf").write_text("#checkov:skip=CKV_AWS_18:log bucket\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.ruff.lint.per-file-ignores]\n"t/**" = ["S101"]\n', encoding="utf-8"
    )
    (tmp_path / ".gitleaks.toml").write_text(
        '[[allowlists]]\nid = "k"\ndescription = "d"\n', encoding="utf-8"
    )
    register = tmp_path / "register.md"
    register.write_text(
        _register(
            ("pkg/mod.py", "S603", "fixed args", "2026-10-24"),
            ("infra/s.tf", "CKV_AWS_18", "log bucket", "2026-10-24"),
            ("t/**", "S101", "pytest asserts", "2026-10-24"),
            (".gitleaks.toml", "k", "fixture", "2026-10-24"),
        ),
        encoding="utf-8",
    )
    assert sup.check(tmp_path, register).ok
    (tmp_path / "pkg" / "new.py").write_text("x  # noqa: E501\n", encoding="utf-8")
    result = sup.check(tmp_path, register)
    assert not result.ok
    assert "pkg/new.py:1: suppression of E501 gives no reason" in result.message
