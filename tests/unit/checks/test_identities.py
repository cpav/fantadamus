"""Task 6.3: the FantaCreator-identity check fails closed and never prints its match (R10.3 to R10.6)."""

from __future__ import annotations

from pathlib import Path

from scripts.checks import identities as ids

IDENTITY = "Creatore Fittizio"


def test_missing_list_fails_closed(tmp_path: Path) -> None:
    result = ids.check_lines([], env={}, config=tmp_path / "absent.toml")
    assert not result.ok
    assert "FANTADAMUS_PRIVATE_CONFIG" in result.message
    assert "FANTADAMUS_CREATOR_IDENTITIES" in result.message


def test_empty_environment_variable_counts_as_missing(tmp_path: Path) -> None:
    assert ids.load_identities({"FANTADAMUS_CREATOR_IDENTITIES": "  \n"}, tmp_path / "absent.toml") is None


def test_private_config_list_is_used(tmp_path: Path) -> None:
    config = tmp_path / "private.toml"
    config.write_text(f'[creators]\nidentities = ["{IDENTITY}", "@canale_fittizio"]\n', encoding="utf-8")
    assert ids.load_identities({}, config) == ["creatore fittizio", "@canale_fittizio"]
    config.write_text("[creators]\nidentities = []\n", encoding="utf-8")
    assert ids.load_identities({}, config) == []


def test_environment_variable_wins_over_config(tmp_path: Path) -> None:
    env = {"FANTADAMUS_CREATOR_IDENTITIES": f"{IDENTITY}\n\nAltro Nome\n"}
    assert ids.load_identities(env, tmp_path / "absent.toml") == ["creatore fittizio", "altro nome"]


def test_match_reports_path_and_line_only() -> None:
    lines = [("docs/a.md", 1, "nothing here"), ("docs/a.md", 2, "Video di  CREATÒRE   fittizio, oggi")]
    result = ids.check_lines(lines, env={"FANTADAMUS_CREATOR_IDENTITIES": IDENTITY}, config=Path("/absent"))
    assert not result.ok
    assert result.message == "FantaCreator identity found at docs/a.md:2"
    assert "fittizio" not in result.message.casefold()


def test_word_boundaries_avoid_false_positives() -> None:
    env = {"FANTADAMUS_CREATOR_IDENTITIES": "Ann"}
    assert ids.check_lines([("x.py", 1, "annual report")], env=env, config=Path("/absent")).ok
    assert not ids.check_lines([("x.py", 1, "by ann, today")], env=env, config=Path("/absent")).ok


def test_clean_lines_pass() -> None:
    env = {"FANTADAMUS_CREATOR_IDENTITIES": IDENTITY}
    assert ids.check_lines([("x.py", 1, "print('hello')")], env=env, config=Path("/absent")).ok
