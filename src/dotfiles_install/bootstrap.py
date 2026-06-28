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
    from collections.abc import Callable

    from dotfiles_install.context import InstallContext

_RETRY_ATTEMPTS = 3
_BREW_INSTALL_URL = "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"
_UV_INSTALL_URL = "https://astral.sh/uv/install.sh"
# Apple-Silicon prefix first, then Intel — mirrors the bash `brew shellenv` candidate loop.
_BREW_BINARIES = (Path("/opt/homebrew/bin/brew"), Path("/usr/local/bin/brew"))


def bootstrap_toolchain(ctx: InstallContext) -> None:
    """Install Homebrew and uv if absent, aborting (exit 1) if either fails to land."""
    _ensure_tool(
        ctx,
        command="brew",
        label="Homebrew",
        install=_install_homebrew,
        activate=_activate_homebrew,
    )
    _ensure_tool(ctx, command="uv", label="uv", install=_install_uv, activate=_activate_uv)


def _ensure_tool(
    ctx: InstallContext,
    *,
    command: str,
    label: str,
    install: Callable[[], bool],
    activate: Callable[[], None],
) -> None:
    """Install ``command`` when absent, then hard-fail the run if it's still not on PATH.

    ``label`` derives the user-facing strings to match ``install.sh`` exactly: the step header
    (``Installing <label>``), the retry description and the abort message (``<label> install``).
    """
    if commands.which(command) is None:
        ctx.ui.step(f"Installing {label}")
        commands.retry(f"{label} install", _RETRY_ATTEMPTS, install, ui=ctx.ui)
        activate()
    if commands.which(command) is None:
        ctx.ui.err(f"{label} install failed.")
        raise SystemExit(1)


def _install_homebrew() -> bool:
    """Fetch and run the Homebrew installer non-interactively; report whether it succeeded."""
    script = commands.fetch(["curl", "-fsSL", _BREW_INSTALL_URL])
    if script is None:
        return False
    return commands.run_ok(["/bin/bash", "-c", script], env={"NONINTERACTIVE": "1"})


def _install_uv() -> bool:
    """Fetch and run the uv installer (piped into ``sh``); report whether it succeeded."""
    script = commands.fetch(["curl", "-LsSf", _UV_INSTALL_URL])
    if script is None:
        return False
    return commands.run_ok(["sh"], input_text=script)


def _activate_homebrew() -> None:
    """Put a freshly installed brew's ``bin`` and ``sbin`` on ``PATH`` (Apple Silicon vs Intel).

    Mirrors ``brew shellenv``'s PATH effect (both ``bin`` and ``sbin``) but not its
    ``HOMEBREW_*``/``MANPATH`` exports — nothing in the install path reads those, and ``brew``
    derives its prefix from its own location. A later phase needing the prefix should call
    ``brew --prefix`` rather than read the environment.
    """
    for brew_bin in _BREW_BINARIES:
        if os.access(brew_bin, os.X_OK):
            _prepend_path(brew_bin.parent.parent / "sbin")
            _prepend_path(brew_bin.parent)  # bin prepended last, so it sits ahead of sbin
            return


def _activate_uv() -> None:
    """Put a freshly installed uv on ``PATH`` (``~/.local/bin``, or older ``~/.cargo/bin``)."""
    home = Path.home()
    _prepend_path(home / ".cargo" / "bin")
    _prepend_path(home / ".local" / "bin")  # prepended last so it sits first, matching install.sh


def _prepend_path(directory: Path) -> None:
    """Prepend ``directory`` to this process's ``PATH`` so later ``which`` lookups find it."""
    os.environ["PATH"] = f"{directory}{os.pathsep}{os.environ.get('PATH', '')}"
