"""mvp-alerts task 3.2: `[alerts] enabled = false` in the private configuration turns alerts off; without it,
or when the file can't be read, they stay on (design C7; R3.4)."""

from __future__ import annotations

from pathlib import Path

from fantadamus.cli.notify import CONFIG_VAR, alerts_enabled


def _with(tmp_path: Path, text: str | bytes) -> dict[str, str]:
    path = tmp_path / "private.toml"
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")
    return {CONFIG_VAR: str(path)}


def test_on_without_the_file(tmp_path: Path) -> None:
    assert alerts_enabled({CONFIG_VAR: str(tmp_path / "missing.toml")}) == (True, None)


def test_off_with_the_switch(tmp_path: Path) -> None:
    assert alerts_enabled(_with(tmp_path, "[alerts]\nenabled = false\n")) == (
        False,
        "Alerts are switched off in the private configuration.",
    )


def test_on_with_the_switch_on_or_absent(tmp_path: Path) -> None:
    assert alerts_enabled(_with(tmp_path, "[alerts]\nenabled = true\n")) == (True, None)
    assert alerts_enabled(_with(tmp_path, '[creators]\nidentities = ["x"]\n')) == (True, None)
    assert alerts_enabled(_with(tmp_path, 'alerts = "off"\n')) == (True, None)


def test_on_when_the_file_cant_be_read(tmp_path: Path) -> None:
    assert alerts_enabled(_with(tmp_path, "[alerts\nenabled = false")) == (
        True,
        "Alerts stay on: the private configuration can't be read (TOMLDecodeError).",
    )
    assert alerts_enabled(_with(tmp_path, b"\xff\xfe")) == (
        True,
        "Alerts stay on: the private configuration can't be read (UnicodeDecodeError).",
    )


def test_on_with_a_switch_that_isnt_true_or_false(tmp_path: Path) -> None:
    assert alerts_enabled(_with(tmp_path, '[alerts]\nenabled = "false"\n')) == (
        True,
        "Alerts stay on: `enabled` under [alerts] must be true or false.",
    )
