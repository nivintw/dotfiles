# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Shared helpers for the config-validation test suite.

These tests assert that the repo's *declarative* config is well-formed and
internally consistent — the bug class (a malformed TOML, a resolved secret
replacing an op:// reference, a hook tool missing from the Brewfile) that the
static hooks and the bats behavior tests don't cover. Run with: uv run pytest
"""

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def tracked(*globs: str) -> list[Path]:
    """Repo-relative tracked files matching the given globs, as absolute Paths.

    Uses `git ls-files -z` so paths containing spaces (e.g. the VS Code settings
    path) survive intact.
    """
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z", *globs],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [REPO / p for p in out.split("\0") if p]
