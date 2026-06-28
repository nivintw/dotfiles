# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Phase 0: bootstrap the base toolchain (Homebrew + uv).

Everything else the installer needs (fish, stow, the rest) comes from ``brew bundle`` in
phase 1, so this phase only lays down the two network ``curl|bash`` bootstraps. Each is
captured first then executed (a failed download fails the attempt instead of silently
no-opping a piped shell), retried a few times for a transient blip, and then guarded by a
hard ``command -v`` post-check that aborts the run if the tool is still absent.

Ported from ``install.sh`` phase 0 (the "Bootstrap toolchain" block).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from dotfiles_install import commands

if TYPE_CHECKING:
    from dotfiles_install.context import InstallContext

_RETRY_ATTEMPTS = 3
_BREW_INSTALL_URL = "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"
_UV_INSTALL_URL = "https://astral.sh/uv/install.sh"
# Apple-Silicon prefix first, then Intel — mirrors the bash `brew shellenv` candidate loop.
_BREW_BINARIES = (Path("/opt/homebrew/bin/brew"), Path("/usr/local/bin/brew"))


def bootstrap_toolchain(ctx: InstallContext) -> None:
    """Install Homebrew and uv if absent, aborting (exit 1) if either fails to land."""
    _ensure_homebrew(ctx)
    _ensure_uv(ctx)


def _ensure_homebrew(ctx: InstallContext) -> None:
    """Install Homebrew when missing, then hard-fail the run if ``brew`` is still not on PATH."""
    if commands.which("brew") is None:
        ctx.ui.step("Installing Homebrew")
        commands.retry("Homebrew install", _RETRY_ATTEMPTS, _install_homebrew, ui=ctx.ui)
        _activate_homebrew()
    if commands.which("brew") is None:
        ctx.ui.err("Homebrew install failed.")
        raise SystemExit(1)


def _ensure_uv(ctx: InstallContext) -> None:
    """Install uv when missing, then hard-fail the run if ``uv`` is still not on PATH."""
    if commands.which("uv") is None:
        ctx.ui.step("Installing uv")
        commands.retry("uv install", _RETRY_ATTEMPTS, _install_uv, ui=ctx.ui)
        _activate_uv()
    if commands.which("uv") is None:
        ctx.ui.err("uv install failed.")
        raise SystemExit(1)


def _install_homebrew() -> bool:
    """Fetch and run the Homebrew installer non-interactively; report whether it succeeded."""
    script = commands.fetch(["curl", "-fsSL", _BREW_INSTALL_URL])
    if script is None:
        return False
    result = commands.run(["/bin/bash", "-c", script], env={"NONINTERACTIVE": "1"})
    return not result.returncode


def _install_uv() -> bool:
    """Fetch and run the uv installer (piped into ``sh``); report whether it succeeded."""
    script = commands.fetch(["curl", "-LsSf", _UV_INSTALL_URL])
    if script is None:
        return False
    result = commands.run(["sh"], input_text=script)
    return not result.returncode


def _activate_homebrew() -> None:
    """Put a freshly installed brew on ``PATH`` for the rest of the run (Apple Silicon vs Intel)."""
    for brew_bin in _BREW_BINARIES:
        if os.access(brew_bin, os.X_OK):
            _prepend_path(brew_bin.parent)
            return


def _activate_uv() -> None:
    """Put a freshly installed uv on ``PATH`` (``~/.local/bin``, or older ``~/.cargo/bin``)."""
    home = Path.home()
    _prepend_path(home / ".cargo" / "bin")
    _prepend_path(home / ".local" / "bin")  # prepended last so it sits first, matching install.sh


def _prepend_path(directory: Path) -> None:
    """Prepend ``directory`` to this process's ``PATH`` so later ``which`` lookups find it."""
    os.environ["PATH"] = f"{directory}{os.pathsep}{os.environ.get('PATH', '')}"
