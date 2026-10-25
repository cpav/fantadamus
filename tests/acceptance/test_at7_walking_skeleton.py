"""AT-7: the walking skeleton (R16.1 to R16.13).

A payload submitted through the MCP submit tool reaches gold and is read back through the MCP read tool with
its source URL; a payload from a host off the allowlist is rejected and nothing is written; the run takes
under 10 s and its gold product equals the committed golden file.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest
from mcp import Client

from fantadamus.cli import __main__ as cli
from fantadamus.core.clock import utc_now
from fantadamus.lake.duckdb_store import LakeStore
from fantadamus.mcp.server import build_server, load_allowed_hosts

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "skeleton"
GOLDEN = ROOT / "tests" / "golden" / "skeleton" / "role_counts.json"
TIME_BUDGET_SECONDS = 10


async def _submit_off_allowlist(lake: Path) -> object:
    fixture = json.loads((FIXTURE / "rows.json").read_text(encoding="utf-8"))
    server = build_server(
        LakeStore(lake),
        allowed_hosts=load_allowed_hosts(FIXTURE / "sources.toml"),
        clock=utc_now,
        submitted_by="at7",
    )
    async with Client(server, raise_exceptions=True) as client:
        result = await client.call_tool(
            "submit_skeleton_rows",
            {
                "rows": fixture["rows"],
                "source_url": "https://example.org.evil.example/skeleton",
                "captured_at": fixture["captured_at"],
            },
        )
    return result.structured_content


def test_at7_walking_skeleton(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lake = tmp_path / "lake"
    started = time.perf_counter()

    code = cli.main(["skeleton", "run", "--lake", str(lake), "--golden", str(GOLDEN)])
    output = capsys.readouterr()
    assert code == 0, output.err
    summary = json.loads(output.out)
    assert summary["rows"], "gold is empty"
    assert all(row["source_urls"] == ["https://example.org/skeleton"] for row in summary["rows"])
    assert summary["rows"] == json.loads(GOLDEN.read_text(encoding="utf-8"))

    before = sorted(path.relative_to(lake) for path in lake.rglob("*"))
    snapshot = {path: (lake / path).read_bytes() for path in before if (lake / path).is_file()}
    rejected = asyncio.run(_submit_off_allowlist(lake))
    assert rejected == {
        "accepted": 0,
        "rejected": [
            {"index": None, "reason": "source_url host example.org.evil.example is not on the allowlist"}
        ],
        "bronze_id": None,
    }
    assert sorted(path.relative_to(lake) for path in lake.rglob("*")) == before
    assert {path: (lake / path).read_bytes() for path in snapshot} == snapshot

    assert time.perf_counter() - started < TIME_BUDGET_SECONDS
