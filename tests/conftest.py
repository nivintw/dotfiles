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

import pytest

from dotfiles_install import brew_bundle, cli, ollama, privileged, verify_install
from dotfiles_install.os_detect import OS

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _pin_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the OS-branching installer modules' ``current_os()`` to macOS on any host.

    The installer's phase bodies and probes branch on ``current_os()``; without a pin the
    same test would exercise different branches on the macOS dev box vs the Linux CI runner.
    The historical tests assert the macOS shapes, so macOS is the default; tests for the
    Linux/WSL shapes re-pin inside their own bodies (a later setattr wins). ``os_detect``
    itself is untouched, so its own detection tests still see the real platform.
    """
    for mod in (brew_bundle, cli, ollama, privileged, verify_install):
        monkeypatch.setattr(mod, "current_os", lambda: OS.MACOS)


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
