# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""The installer's ordered phase registry.

Each :class:`Phase` declares its display name, the operating systems it applies to (for
per-phase gating), and whether it needs root. :data:`REGISTRY` mirrors ``install.sh``'s
phases 0-17 in order. Phase *bodies* are ported one slice at a time (#67-#72): phases 0-1
(bootstrap toolchain + brew bundle) carry a ``run`` callable and **execute real installs**;
the rest are still ``None`` stubs. ``install.sh`` stays the default entry point until the
cutover (#72), but running the ported phases via this registry performs real work now.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from dotfiles_install.bootstrap import bootstrap_toolchain
from dotfiles_install.brew_bundle import install_packages
from dotfiles_install.os_detect import OS, current_os

if TYPE_CHECKING:
    from collections.abc import Callable

    from dotfiles_install.context import InstallContext

    PhaseRun = Callable[[InstallContext], None]


@dataclass(frozen=True)
class Phase:
    """One install phase: its position, name, OS gating, privilege need, and (stub) body."""

    number: int
    name: str
    os: frozenset[OS]
    privileged: bool = False
    run: PhaseRun | None = None

    def applies(self, target: OS) -> bool:
        """Report whether this phase runs on ``target``."""
        return target in self.os


_MAC = frozenset({OS.MACOS})

REGISTRY: tuple[Phase, ...] = (
    Phase(0, "Bootstrap toolchain (Homebrew + uv)", _MAC, run=bootstrap_toolchain),
    Phase(1, "Homebrew packages (brew bundle)", _MAC, run=install_packages),
    Phase(2, "Privileged setup (fish shell, firewall, Touch ID)", _MAC, privileged=True),
    Phase(3, "dotfiles symlinks (stow)", _MAC),
    Phase(4, "Machine-local overlay files", _MAC),
    Phase(5, "Fish plugins (fisher)", _MAC),
    Phase(6, "tmux plugins (TPM)", _MAC),
    Phase(7, "atuin history import", _MAC),
    Phase(8, "iTerm2 preferences", _MAC),
    Phase(9, "Python CLI tools (uv)", _MAC),
    Phase(10, "Git clone hook (notify-on-clone)", _MAC),
    Phase(11, "Claude Code CLI", _MAC),
    Phase(12, "Claude Code MCP servers", _MAC),
    Phase(13, "Claude Code user settings", _MAC),
    Phase(14, "Ollama model for GitLens", _MAC),
    Phase(15, "macOS system defaults (macos.sh)", _MAC),
    Phase(16, "Dock layout (dock.sh)", _MAC),
    Phase(17, "Verification & summary", _MAC),
)


def phases_for(target: OS | None = None) -> list[Phase]:
    """Return the registry phases applicable to ``target`` (default: the current OS)."""
    resolved = target if target is not None else current_os()
    return [phase for phase in REGISTRY if phase.applies(resolved)]
