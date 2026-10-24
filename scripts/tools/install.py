"""Install the pinned non-Python tools into bin/, refusing any download whose SHA-256 differs (R1.8).

Usage: python -m scripts.tools.install [--only TOOL ...]
"""

from __future__ import annotations

import argparse
import hashlib
import io
import platform
import sys
import tarfile
import tomllib
import urllib.request
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PINS = ROOT / "tool-versions.toml"
BIN = ROOT / "bin"

Fetch = Callable[[str], bytes]


class ChecksumMismatchError(Exception):
    """A download's SHA-256 differs from the pinned value; nothing was installed."""


class UnsupportedPlatformError(Exception):
    """This machine's OS and CPU have no pinned download."""


@dataclass(frozen=True)
class Tool:
    """One pinned tool from tool-versions.toml."""

    name: str
    version: str
    url: str
    binary: str
    version_args: tuple[str, ...]
    assets: Mapping[str, str]
    sha256: Mapping[str, str]

    def download_url(self, key: str) -> str:
        return self.url.format(version=self.version, asset=self.assets[key])


def platform_key(system: str | None = None, machine: str | None = None) -> str:
    """Map an OS and CPU to our key: darwin_amd64, darwin_arm64 or linux_amd64."""
    system = (system or sys.platform).lower()
    machine = (machine or platform.machine()).lower()
    os_name = {"darwin": "darwin", "linux": "linux"}.get(system)
    arch = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64", "aarch64": "arm64"}.get(machine)
    key = f"{os_name}_{arch}"
    if os_name is None or arch is None or key not in {"darwin_amd64", "darwin_arm64", "linux_amd64"}:
        raise UnsupportedPlatformError(f"no pinned tools for {system}/{machine}")
    return key


def load_tools(path: Path = PINS) -> list[Tool]:
    """Read the downloadable tools from tool-versions.toml (entries with a `url`)."""
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return [
        Tool(
            name=name,
            version=entry["version"],
            url=entry["url"],
            binary=entry["binary"],
            version_args=tuple(entry["version_args"]),
            assets=entry["assets"],
            sha256=entry["sha256"],
        )
        for name, entry in data.items()
        if "url" in entry
    ]


def _fetch(url: str) -> bytes:
    if not url.startswith("https://"):
        raise ValueError(f"refusing non-HTTPS download: {url}")
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310  # reason: HTTPS-only URLs from tool-versions.toml, verified by SHA-256 before use
        data: bytes = response.read()
        return data


def _extract(archive: bytes, url: str, binary: str) -> bytes:
    """Return the bytes of the named binary from a .zip or .tar.gz, without extracting anything else."""
    if url.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            member = next(n for n in zipped.namelist() if Path(n).name == binary)
            return zipped.read(member)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tarred:
        info = next(m for m in tarred.getmembers() if m.isfile() and Path(m.name).name == binary)
        extracted = tarred.extractfile(info)
        if extracted is None:
            raise FileNotFoundError(f"{binary} not found in {url}")
        return extracted.read()


def install_tool(tool: Tool, key: str, bin_dir: Path, fetch: Fetch = _fetch) -> Path:
    """Download, verify and install one tool; raise ChecksumMismatchError before writing anything."""
    if key not in tool.sha256:
        raise UnsupportedPlatformError(f"{tool.name} has no pin for {key}")
    url = tool.download_url(key)
    archive = fetch(url)
    actual = hashlib.sha256(archive).hexdigest()
    if actual != tool.sha256[key]:
        raise ChecksumMismatchError(f"{tool.name} {tool.version}: expected {tool.sha256[key]}, got {actual}")
    bin_dir.mkdir(parents=True, exist_ok=True)
    target = bin_dir / tool.binary
    target.write_bytes(_extract(archive, url, tool.binary))
    target.chmod(0o755)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", help="install only these tools")
    args = parser.parse_args(argv)
    key = platform_key()
    for tool in load_tools():
        if args.only and tool.name not in args.only:
            continue
        path = install_tool(tool, key, BIN)
        print(f"installed {tool.name} {tool.version} → {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
