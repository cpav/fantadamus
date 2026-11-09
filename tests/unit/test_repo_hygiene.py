"""Private data can't be committed: these paths are git-ignored, shared files aren't (R2.10)."""

from __future__ import annotations

import json
import plistlib
import tomllib
from pathlib import Path

import pytest
from scripts.checks._common import run_command

ROOT = Path(__file__).resolve().parents[2]
PROMPT_BUDGET = 13_000
"""Characters. Our own budget, not a limit of Claude's: Claude reads the prompt on every question."""

MUST_BE_IGNORED = [
    "data/local/league/owner-squads.json",
    "private.toml",
    "config.private.toml",
    ".env",
    ".env.local",
    "data/private/rosters.csv",
    "data/local/lake/bronze/x.parquet",
    "bin/terraform",
    "infra/bootstrap/terraform.tfstate",
    "infra/bootstrap/terraform.tfstate.backup",
    "infra/stack/.terraform/providers/x",
    "plan.tfplan",
    ".claude/settings.local.json",
    ".claude/launch.json",
]
MUST_BE_TRACKABLE = [
    ".terraform.lock.hcl",
    "infra/bootstrap/.terraform.lock.hcl",
    "private.example.toml",
    ".claude/settings.json",
]


def _ignored(path: str) -> bool:
    return run_command(["git", "-C", str(ROOT), "check-ignore", "--no-index", "-q", path]).returncode == 0


@pytest.mark.parametrize("path", MUST_BE_IGNORED)
def test_private_paths_ignored(path: str) -> None:
    assert _ignored(path), f"{path} must be git-ignored"


@pytest.mark.parametrize("path", MUST_BE_TRACKABLE)
def test_committed_paths_not_ignored(path: str) -> None:
    assert not _ignored(path), f"{path} must stay committable"


def test_readme_claude_desktop_setup() -> None:
    """mvp-x-or-y task 7.4 (R13.3): the README shows the Claude Desktop entry, with uv's full path."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    block = readme.split("claude_desktop_config.json", 1)[1].split("```json\n", 1)[1].split("```", 1)[0]
    server = json.loads(block)["mcpServers"]["fantadamus"]
    assert server["command"].startswith("/")
    assert server["command"].endswith("/uv")
    assert server["args"][:2] == ["--directory", "/path/to/fantadamus"]
    assert server["args"][2:] == ["run", "--frozen", "fantadamus", "serve", "--user", "owner"]


def test_player_guide_setup() -> None:
    """mvp-x-or-y task 9.2 (R13.4): a second player can set Fantadamus up from the guide alone."""
    guide = (ROOT / "docs" / "player-setup.md").read_text(encoding="utf-8")
    assert "git clone https://github.com/cpav/fantadamus.git" in guide
    block = guide.split("```json\n", 1)[1].split("```", 1)[0]
    server = json.loads(block)["mcpServers"]["fantadamus"]
    assert server["command"].endswith("/.local/bin/uv")
    assert server["args"][0] == "--directory"
    assert server["args"][2:] == ["run", "--frozen", "--no-dev", "fantadamus", "serve", "--user", "your-name"]
    assert "Project" in guide
    assert "docs/agent-prompt.md" in guide


def test_player_guide_schedule() -> None:
    """mvp-collect task 7.2 (R7.2): the guide has the player install a launchd agent that runs `collect --due`
    every 15 minutes, with their own paths filled in by the shell, and shows how to switch it off."""
    guide = (ROOT / "docs" / "player-setup.md").read_text(encoding="utf-8")
    heredoc = guide.split("<<EOF\n", 1)[1].split("\nEOF\n", 1)[0]
    filled = heredoc.replace("$(which uv)", "/Users/you/.local/bin/uv").replace("$HOME", "/Users/you")
    plist = plistlib.loads(filled.encode())
    assert plist["StartInterval"] == 900
    assert plist["ProgramArguments"] == [
        "/Users/you/.local/bin/uv",
        "--directory",
        "/Users/you/fantadamus",
        "run",
        "--frozen",
        "--no-dev",
        "fantadamus",
        "collect",
        "--due",
    ]
    switch_on = guide.split("launchctl bootstrap", 1)[1].split("\n", 1)[0]
    assert f"{plist['Label']}.plist" in switch_on
    assert f"launchctl bootout gui/$(id -u)/{plist['Label']}" in guide


def test_docs_name_every_role() -> None:
    """mvp-roles task 7.1 (R7.1): the answer formats give a keeper's lines, and the README the new tool."""
    formats = (ROOT / "docs" / "answer-formats.md").read_text(encoding="utf-8")
    assert "clean sheet" in formats.split("## 2. The full lineup")[0]
    assert "clean sheet" in formats.split("## 4. One player")[1].split("## 5.")[0]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "`player_outlook`" in readme
    assert "statistics page" in readme.split("## Status")[0]


def _agent_prompt() -> str:
    """What a player pastes into their Project, its lines joined wherever they break."""
    text = (ROOT / "docs" / "agent-prompt.md").read_text(encoding="utf-8")
    return " ".join(text.split("\n---\n", 1)[1].split())


def test_agent_prompt_covers_the_lineup() -> None:
    """mvp-lineup task 8.1 (R9.1, R9.4, R6.2): Claude knows it can pick the lineup, and how to say it."""
    prompt = _agent_prompt()
    for part in (
        "`set_squad`",
        "`best_lineup`",
        # What the tools can answer with.
        "`squad`",
        "`choose`",
        "`refused`",
        "a league-mate's",
        # Formats 2, 3 and 6.
        "**How to answer a full lineup**",
        "eight rounds out of ten",
        "the bench in order",
        "the higher ceiling",
        '"Which formation?"',
        '"How do I order my bench?"',
        # The league profile.
        "**If the Project has a league profile**",
        "ask only for what it leaves out",
        "never the numbers",
        # Warnings, what could improve them and the user's own choice.
        "Give every warning",
        "`improve`",
        "Try it once",
        "state the cost once and then help with their choice",
        # How the last round went.
        "last_round",
        "Say it once",
        # Two roles, with a squad.
        "formation call, which `best_lineup` makes",
        # The translator (mvp-rules R4).
        "ready_made",
        "`priced` and left_out",
        "never guess a value",
        "what it needs",
        # Formula rules and the captain in the answer.
        "rules_worth",
        "the captain and the vice",
        "start, leave_out, formation or captain",
    ):
        assert part in prompt, part
    for gone in ("A lineup has a setup step of its own", "start, leave_out or formation"):
        assert gone not in prompt, gone
    for stale in ("aren't supported yet", "in a later slice", "For now they answer two questions"):
        assert stale not in prompt, stale
    assert len(prompt) < PROMPT_BUDGET


def test_player_guide_covers_the_lineup() -> None:
    """mvp-lineup task 8.3 (R9.2): what it now answers, how to give a squad and rules, and where the profile
    goes."""
    guide = " ".join((ROOT / "docs" / "player-setup.md").read_text(encoding="utf-8").split())
    for part in (
        "the full lineup",
        "docs/league-profile-template.md",
        "below the agent prompt",
        "your squad",
        "your league's rules",
        "Who do I field this round?",
        "paste it again",
        "fantadamus calibrate --round",
    ):
        assert part in guide, part
    assert "come in later versions" not in guide

    readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").split())
    for part in (
        "`best_lineup`",
        "`set_squad`",
        "docs/league-profile-template.md",
        "fantadamus calibrate --round",
        "`mvp-lineup`",
    ):
        assert part in readme, part
    assert "then the full lineup with the bench and the formation | In progress" not in readme

    formats = (ROOT / "docs" / "answer-formats.md").read_text(encoding="utf-8")
    full = formats.split("## 2. The full lineup", 1)[1].split("## 3. The formation call", 1)[0]
    assert "Built in `mvp-lineup`" in full
    assert "Next slices" not in full
    for part in (
        "What that costs",
        "Round 10's forecasts",
    ):  # the user's own choice, and the line on the last round
        assert part in full, part
    assert "Built in `mvp-lineup`" in formats.split("## 3. The formation call", 1)[1].split("## 4.", 1)[0]
    assert "Built in `mvp-lineup`" in formats.split("## 6. The bench order", 1)[1].split("## Later", 1)[0]


def test_league_rules_guide_covers_the_vocabulary() -> None:
    """mvp-rules task 5.3 (R5.3, R4.5): every event and every part of a formula rule, worked examples, and the
    one case that needs code."""
    from typing import get_args

    from fantadamus.contracts.xy.league import EventName, FormulaRule, Unit

    guide = " ".join((ROOT / "docs" / "league-rules.md").read_text(encoding="utf-8").split())
    for event in get_args(EventName):
        assert f"`{event}`" in guide, event
    for field in (*FormulaRule.model_fields, *Unit.model_fields):
        assert f"`{field}`" in guide, field
    for value in ("`average`", "`sum`", "`each`", "`nobody`", "`bonus_or_goal`", "`captain`"):
        assert value in guide, value
    for part in (
        "## Worked examples",
        "## What's left out",
        "## Adding an event with a new estimate",
        "`other_rules`",
        "src/fantadamus/contracts/xy/league.py",
        "src/fantadamus/league/rules.py",
    ):
        assert part in guide, part
    method = " ".join((ROOT / "docs" / "method.md").read_text(encoding="utf-8").split())
    assert "formula rules" in method.split("## A1.", 1)[1].split("## A2.", 1)[0]
    assert "formula rules" in method.split("## A7.", 1)[1].split("## A8.", 1)[0]
    assert "saved penalt" in method.split("## A6.", 1)[1].split("## A7.", 1)[0]


def test_mutation_run_stays_fast() -> None:
    """Phase gate (`quality.md`). `mutmut` forks for each change and DuckDB hangs in a fork, so any test that
    reaches the lake hangs until its timeout and counts as a kill. A real run spent 97% of its time on that,
    and the score was false. The run uses fast tests only, and stops itself."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    mutmut = config["tool"]["mutmut"]
    assert mutmut["only_mutate"] == ["src/fantadamus/engine/*", "src/fantadamus/domains/calibration.py"]

    selected: set[Path] = set()
    for path in mutmut["pytest_add_cli_args_test_selection"]:
        selected.update((ROOT / path).glob("test_*.py"))
    ignored = {
        ROOT / arg.removeprefix("--ignore=")
        for arg in mutmut["pytest_add_cli_args"]
        if arg.startswith("--ignore=")
    }
    assert ignored <= selected
    assert len(selected - ignored) > 25
    for test in selected - ignored:
        text = test.read_text(encoding="utf-8")
        for slow in ("LakeStore", "duckdb", "_harness", "fantadamus.mcp"):
            assert slow not in text, f"{test.name} reaches the lake or the tools: {slow}"
    assert "--timeout=30" in mutmut["pytest_add_cli_args"]

    target = (ROOT / "Makefile").read_text(encoding="utf-8").split("\nmutate:", 1)[1].split("\n\n", 1)[0]
    assert "alarm" in target
    assert "600" in target
    assert "HYPOTHESIS_PROFILE=dev" in target
    assert "--group mutation" in target
    assert "mutants/" in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
