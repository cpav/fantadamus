"""mvp-store task 4.1: a log's file is parsed once while it's unchanged, and a read can start at a month
(design C6; R3.4)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from pydantic import BaseModel

from fantadamus.lake import jsonl
from fantadamus.lake.jsonl import read_lines


class Line(BaseModel):
    at: dt.datetime
    text: str


def at(month: int, day: int, hour: int = 12) -> dt.datetime:
    return dt.datetime(2026, month, day, hour, tzinfo=dt.UTC)


def write(root: Path, *lines: Line) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for line in lines:
        with (root / f"{line.at:%Y-%m}.jsonl").open("a", encoding="utf-8") as log:
            log.write(line.model_dump_json() + "\n")


@pytest.fixture
def parsed(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The files parsed, by name, from an empty cache."""
    monkeypatch.setattr(jsonl, "_PARSED", {})
    parse = jsonl._parse
    seen: list[str] = []

    def counting(path: Path, model: type[Line]) -> list[Line]:
        seen.append(path.name)
        return parse(path, model)

    monkeypatch.setattr(jsonl, "_parse", counting)
    return seen


def test_a_file_is_parsed_once_while_unchanged(tmp_path: Path, parsed: list[str]) -> None:
    write(tmp_path, Line(at=at(10, 3), text="one"), Line(at=at(11, 3), text="two"))
    first = read_lines(tmp_path, Line)
    assert read_lines(tmp_path, Line) == first
    assert [line.text for line in first] == ["one", "two"]
    assert parsed == ["2026-10.jsonl", "2026-11.jsonl"]  # each once, for both reads


def test_an_appended_line_is_seen(tmp_path: Path, parsed: list[str]) -> None:
    write(tmp_path, Line(at=at(10, 3), text="one"), Line(at=at(11, 3), text="two"))
    read_lines(tmp_path, Line)
    write(tmp_path, Line(at=at(11, 4), text="three"))
    assert [line.text for line in read_lines(tmp_path, Line)] == ["one", "two", "three"]
    assert parsed == ["2026-10.jsonl", "2026-11.jsonl", "2026-11.jsonl"]  # only the file that grew, again


def test_a_read_from_a_month_skips_older_files(tmp_path: Path, parsed: list[str]) -> None:
    """From the month of the day before: a run that started late on the last day of a month is in that
    month's file, and may have read its pages after midnight."""
    write(
        tmp_path,
        Line(at=at(9, 20), text="september"),
        Line(at=at(10, 31, 23), text="october"),
        Line(at=at(11, 3), text="november"),
    )
    (tmp_path / "notes.jsonl").write_text(Line(at=at(8, 1), text="other").model_dump_json() + "\n")
    assert [line.text for line in read_lines(tmp_path, Line, since=at(11, 10))] == ["november", "other"]
    assert [line.text for line in read_lines(tmp_path, Line, since=at(11, 1, 0))] == [
        "october",
        "november",
        "other",
    ]
    assert len(read_lines(tmp_path, Line)) == 4
    assert "2026-09.jsonl" in parsed
    assert parsed.count("2026-11.jsonl") == 1


def test_a_caller_cant_change_what_is_kept(tmp_path: Path, parsed: list[str]) -> None:
    write(tmp_path, Line(at=at(11, 3), text="one"), Line(at=at(11, 4), text="two"))
    found = read_lines(tmp_path, Line)
    found.clear()
    found.append(Line(at=at(11, 5), text="not in the log"))
    assert [line.text for line in read_lines(tmp_path, Line)] == ["one", "two"]
    assert parsed == ["2026-11.jsonl"]


def test_a_line_it_cant_read_is_skipped_once(
    tmp_path: Path, parsed: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    write(tmp_path, Line(at=at(11, 3), text="one"))
    with (tmp_path / "2026-11.jsonl").open("a", encoding="utf-8") as log:
        log.write('{"at": "half a line\n')
    assert [line.text for line in read_lines(tmp_path, Line)] == ["one"]
    assert [line.text for line in read_lines(tmp_path, Line)] == ["one"]
    assert [record.message for record in caplog.records] == ["Skipped 2026-11.jsonl line 2: it can't be read"]
