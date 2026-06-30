# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""The installer's ordered phase registry.

Each :class:`Phase` declares its display name, the operating systems it applies to (for
per-phase gating), and a ``privileged`` flag. That flag marks the **dedicated sudo-gated
block** (phase 2) — the one that acquires and drops a sudo ticket — not merely "any phase that
may invoke sudo": phase 1 also makes an optional ``sudo`` call (the pre-bundle Touch-ID enable)
yet is not ``privileged``. :data:`REGISTRY` mirrors ``install.sh``'s phases 0-17 in order.
Every phase now carries a ``run`` callable and **executes real work** — the port is complete
(#67-#72) and this registry, driven by ``dotfiles-install``, is the installer; ``install.sh`` is
a thin stub that hands off to it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from dotfiles_install.bootstrap import bootstrap_toolchain
from dotfiles_install.brew_bundle import install_packages
from dotfiles_install.claude_setup import register_mcp_servers, write_user_settings
from dotfiles_install.ollama import install_ollama_models
from dotfiles_install.os_detect import OS, current_os
from dotfiles_install.overlays import seed_overlays
from dotfiles_install.post_stow import (
    configure_iterm2,
    import_atuin_history,
    install_claude_cli,
    install_fish_plugins,
    install_tmux_plugins,
    install_uv_tools,
    report_clone_hook,
)
from dotfiles_install.privileged import privileged_setup
from dotfiles_install.stow import stow_dotfiles
from dotfiles_install.system_setup import apply_dock_layout, apply_macos_defaults
from dotfiles_install.verify_install import verify_and_summarize

if TYPE_CHECKING:
    from collections.abc import Callable

    from dotfiles_install.context import InstallContext

    PhaseRun = Callable[[InstallContext], None]


@dataclass(frozen=True)
class Phase:
    """One install phase: its position, name, OS gating, body, and privilege need."""

    number: int
    name: str
    os: frozenset[OS]
    run: PhaseRun
    privileged: bool = False

    def applies(self, target: OS) -> bool:
        """Report whether this phase runs on ``target``."""
        return target in self.os


_MAC = frozenset({OS.MACOS})
# Phases whose bodies carry no OS-specific assumption — they run identically on macOS, Linux, and
# WSL2. The macOS-only phases that *touch* OS internals (the Homebrew bootstrap/bundle, the
# Touch-ID/firewall privileged block, iTerm2 `defaults`, the Ollama memory/version probe, the
# `macos.sh`/`dock.sh` system tweaks, and the dscl/socketfilterfw verification) stay `_MAC`; their
# Linux ports are tracked follow-ups (#112 packages, #113 privileged/verify) under the #34 epic.
_ALL = frozenset({OS.MACOS, OS.LINUX, OS.WSL})

REGISTRY: tuple[Phase, ...] = (
    Phase(0, "Bootstrap toolchain (Homebrew + uv)", _MAC, run=bootstrap_toolchain),
    Phase(1, "Homebrew packages (brew bundle)", _MAC, run=install_packages),
    Phase(
        2,
        "Privileged setup (fish shell, firewall, Touch ID)",
        _MAC,
        privileged=True,
        run=privileged_setup,
    ),
    Phase(3, "dotfiles symlinks (stow)", _ALL, run=stow_dotfiles),
    Phase(4, "Machine-local overlay files", _ALL, run=seed_overlays),
    Phase(5, "Fish plugins (fisher)", _ALL, run=install_fish_plugins),
    Phase(6, "tmux plugins (TPM)", _ALL, run=install_tmux_plugins),
    Phase(7, "atuin history import", _ALL, run=import_atuin_history),
    Phase(8, "iTerm2 preferences", _MAC, run=configure_iterm2),
    Phase(9, "Python CLI tools (uv)", _ALL, run=install_uv_tools),
    Phase(10, "Git clone hook (notify-on-clone)", _ALL, run=report_clone_hook),
    Phase(11, "Claude Code CLI", _ALL, run=install_claude_cli),
    Phase(12, "Claude Code MCP servers", _ALL, run=register_mcp_servers),
    Phase(13, "Claude Code user settings", _ALL, run=write_user_settings),
    Phase(14, "Ollama model for GitLens", _MAC, run=install_ollama_models),
    Phase(15, "macOS system defaults (macos.sh)", _MAC, run=apply_macos_defaults),
    Phase(16, "Dock layout (dock.sh)", _MAC, run=apply_dock_layout),
    Phase(17, "Verification & summary", _MAC, run=verify_and_summarize),
)


def phases_for(target: OS | None = None) -> list[Phase]:
    """Return the registry phases applicable to ``target`` (default: the current OS)."""
    resolved = target if target is not None else current_os()
    return [phase for phase in REGISTRY if phase.applies(resolved)]
