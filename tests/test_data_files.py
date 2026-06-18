# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Every tracked data file parses as the format it claims to be.

A typo'd TOML or a malformed JSON silently breaks the tool that reads it (uv,
atuin, Claude Code, VS Code) with no error until that tool runs. These tests make
the breakage loud and immediate.
"""

import json
import plistlib
import tomllib
from typing import TYPE_CHECKING

import json5
import pytest
from conftest import REPO, tracked

if TYPE_CHECKING:
    from pathlib import Path

# settings.json files are JSONC (comments + trailing commas); claude_mcp.json is
# strict JSON. json5 parses both supersets, so use it for the editor configs.
JSONC_FILES = tracked("**/settings.json")


@pytest.mark.parametrize(
    "path",
    tracked("*.toml"),
    ids=lambda p: str(p.relative_to(REPO)),
)
def test_toml_parses(path: Path) -> None:
    """Every tracked .toml file is syntactically valid TOML."""
    with path.open("rb") as fh:
        tomllib.load(fh)


def test_claude_mcp_is_strict_json() -> None:
    """claude_mcp.json is strict JSON (machine-generated input, no JSONC niceties)."""
    json.loads((REPO / "claude_mcp.json").read_text())


def test_claude_settings_is_strict_json() -> None:
    """claude_settings.json baseline is strict JSON — jq merges it at install time."""
    json.loads((REPO / "claude_settings.json").read_text())


@pytest.mark.parametrize("path", JSONC_FILES, ids=lambda p: str(p.relative_to(REPO)))
def test_settings_json_parses_as_jsonc(path: Path) -> None:
    """Every tracked settings.json parses as JSONC (comments + trailing commas)."""
    json5.loads(path.read_text())


def test_iterm_plist_is_valid() -> None:
    """The iTerm2 preferences plist parses to a non-empty dict."""
    plist = REPO / "iterm2" / "com.googlecode.iterm2.plist"
    with plist.open("rb") as fh:
        data = plistlib.load(fh)
    assert isinstance(data, dict), "iTerm plist is not a dict"
    assert data, "iTerm plist parsed but is empty"
