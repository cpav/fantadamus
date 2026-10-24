"""Task 3.3: the installer only installs tools whose download matches the pinned checksum (R1.8)."""

from __future__ import annotations

import hashlib
import io
import stat
import zipfile
from pathlib import Path

import pytest

from scripts.tools import install

BINARY = b"#!/bin/sh\necho 'Terraform v1.17.0'\n"


def _zip_with(name: str, content: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, content)
    return buffer.getvalue()


def _tool(sha256: str) -> install.Tool:
    return install.Tool(
        name="terraform",
        version="1.17.0",
        url="https://example.org/terraform_{version}_{asset}.zip",
        binary="terraform",
        version_args=("version",),
        assets={"darwin_amd64": "darwin_amd64"},
        sha256={"darwin_amd64": sha256},
    )


def test_checksum_mismatch_refused(tmp_path: Path) -> None:
    archive = _zip_with("terraform", BINARY)
    tool = _tool("0" * 64)
    with pytest.raises(install.ChecksumMismatchError):
        install.install_tool(tool, "darwin_amd64", tmp_path, fetch=lambda _url: archive)
    assert not (tmp_path / "terraform").exists()


def test_installs_executable_when_checksum_matches(tmp_path: Path) -> None:
    archive = _zip_with("terraform", BINARY)
    tool = _tool(hashlib.sha256(archive).hexdigest())
    fetched: list[str] = []

    def fetch(url: str) -> bytes:
        fetched.append(url)
        return archive

    installed = install.install_tool(tool, "darwin_amd64", tmp_path, fetch=fetch)
    assert fetched == ["https://example.org/terraform_1.17.0_darwin_amd64.zip"]
    assert installed.read_bytes() == BINARY
    assert installed.stat().st_mode & stat.S_IXUSR


def test_platform_key_maps_os_and_machine() -> None:
    assert install.platform_key("darwin", "x86_64") == "darwin_amd64"
    assert install.platform_key("darwin", "arm64") == "darwin_arm64"
    assert install.platform_key("linux", "x86_64") == "linux_amd64"
    with pytest.raises(install.UnsupportedPlatformError):
        install.platform_key("win32", "AMD64")


def test_loads_pins_from_repository_file() -> None:
    tools = install.load_tools(Path(__file__).resolve().parents[3] / "tool-versions.toml")
    assert {tool.name for tool in tools} == {"terraform", "tflint", "gitleaks", "actionlint"}
    assert all(len(tool.sha256) == 3 for tool in tools)
