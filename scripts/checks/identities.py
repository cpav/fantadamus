"""Fail when a FantaCreator identity appears in the repository (R10.3 to R10.6).

The identities come from $FANTADAMUS_CREATOR_IDENTITIES (one per line; CI secret) or, failing that, from
`[creators] identities = [...]` in the private configuration ($FANTADAMUS_PRIVATE_CONFIG, default
~/.config/fantadamus/private.toml). If neither is available the check fails closed. Matching ignores case,
accents and spacing; findings are reported as path and line only, never the matched text.

Usage: python -m scripts.checks.identities (--tree | --staged | --range LOG_OPTS)
"""

from __future__ import annotations

import argparse
import os
import re
import shlex
import tomllib
import unicodedata
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path

from scripts.checks._common import CheckResult, report, run_command

ROOT = Path(__file__).resolve().parents[2]
ENV_VAR = "FANTADAMUS_CREATOR_IDENTITIES"
CONFIG_VAR = "FANTADAMUS_PRIVATE_CONFIG"
DEFAULT_CONFIG = Path.home() / ".config" / "fantadamus" / "private.toml"

Line = tuple[str, int, str]


def normalise(text: str) -> str:
    """NFKD, without combining marks, case-folded, with whitespace collapsed to single spaces."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.casefold().split())


def config_path(env: Mapping[str, str]) -> Path:
    return Path(env[CONFIG_VAR]).expanduser() if env.get(CONFIG_VAR) else DEFAULT_CONFIG


def load_identities(env: Mapping[str, str], config: Path) -> list[str] | None:
    """The normalised identities, or None when no list is available (the caller fails closed)."""
    raw = env.get(ENV_VAR, "")
    if raw.strip():
        return [normalise(item) for item in raw.splitlines() if item.strip()]
    if config.is_file():
        creators = tomllib.loads(config.read_text(encoding="utf-8")).get("creators", {})
        if "identities" in creators:
            return [normalise(item) for item in creators["identities"] if str(item).strip()]
    return None


def _pattern(identities: Sequence[str]) -> re.Pattern[str] | None:
    if not identities:
        return None
    alternatives = "|".join(re.escape(identity) for identity in sorted(identities, key=len, reverse=True))
    return re.compile(rf"(?<![0-9a-z])(?:{alternatives})(?![0-9a-z])")


def check_lines(lines: Iterable[Line], env: Mapping[str, str], config: Path) -> CheckResult:
    """Scan (path, line number, text) triples; report locations only."""
    identities = load_identities(env, config)
    if identities is None:
        return CheckResult(
            "identities",
            ok=False,
            message=(
                f"no FantaCreator identity list: set {ENV_VAR} (CI secret) or add "
                f"[creators] identities = [...] to the private configuration at {CONFIG_VAR} "
                f"(default {DEFAULT_CONFIG}); an empty list is allowed"
            ),
        )
    pattern = _pattern(identities)
    hits = [f"{path}:{number}" for path, number, text in lines if pattern and pattern.search(normalise(text))]
    if hits:
        return CheckResult(
            "identities", ok=False, message="FantaCreator identity found at " + ", ".join(hits)
        )
    return CheckResult("identities", ok=True)


def _git(*args: str, root: Path) -> str:
    completed = run_command(["git", "-C", str(root), *args])
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout


def _file_lines(path: str, text: str) -> Iterator[Line]:
    for number, line in enumerate(text.splitlines(), start=1):
        yield path, number, line


def tree_lines(root: Path | None = None) -> Iterator[Line]:
    """Every line of every tracked or new, non-ignored file."""
    root = root or ROOT
    for name in _git("ls-files", "--cached", "--others", "--exclude-standard", root=root).splitlines():
        path = root / name
        try:
            yield from _file_lines(name, path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue


def staged_lines(root: Path | None = None) -> Iterator[Line]:
    """Every line of every staged file, as staged."""
    root = root or ROOT
    names = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", root=root).splitlines()
    for name in names:
        try:
            yield from _file_lines(name, _git("show", f":{name}", root=root))
        except (RuntimeError, UnicodeDecodeError):
            continue


_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,\d+)? @@")


def range_lines(log_opts: str, root: Path | None = None) -> Iterator[Line]:
    """Every line added by the commits in a git log range; the path is `<commit> <file>`."""
    root = root or ROOT
    output = _git(
        "log", "-p", "--unified=0", "--no-color", "--format=commit:%H", *shlex.split(log_opts), root=root
    )
    commit, path, number = "", "", 0
    for line in output.splitlines():
        if line.startswith("commit:"):
            commit = line.removeprefix("commit:")[:12]
        elif line.startswith("+++ "):
            path = line.removeprefix("+++ b/").removeprefix("+++ ")
        elif match := _HUNK.match(line):
            number = int(match.group("start"))
        elif line.startswith("+"):
            yield f"{commit} {path}", number, line[1:]
            number += 1


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--tree", action="store_true", help="scan every tracked or new file")
    mode.add_argument("--staged", action="store_true", help="scan the staged files")
    mode.add_argument("--range", metavar="LOG_OPTS", help="scan lines added in this git log range")
    args = parser.parse_args(argv)
    env = os.environ if env is None else env
    if args.tree:
        lines: Iterable[Line] = tree_lines()
    elif args.staged:
        lines = staged_lines()
    else:
        lines = range_lines(args.range)
    return report(check_lines(lines, env=env, config=config_path(env)))


if __name__ == "__main__":
    raise SystemExit(main())
