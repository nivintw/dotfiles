# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""The installer's ordered phase registry.

Each :class:`Phase` declares its display name, the operating systems it applies to (for
per-phase gating), and a ``privileged`` flag. That flag marks the **dedicated sudo-gated
block** (phase 2) — the one that acquires and drops a sudo ticket — not merely "any phase that
may invoke sudo": phase 1 also makes an optional ``sudo`` call (the pre-bundle Touch-ID enable)
yet is not ``privileged``. :data:`REGISTRY` mirrors ``install.sh``'s
phases 0-17 in order. Phase *bodies* are ported one slice at a time (#67-#72): phases 0-13
(bootstrap toolchain through the Claude Code MCP servers + user settings) carry a ``run``
callable and **execute real installs**; phases 14-17 are still ``None`` stubs. ``install.sh``
stays the default entry point until the cutover (#72), but running the ported phases via this
registry performs real work now.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from dotfiles_install.bootstrap import bootstrap_toolchain
from dotfiles_install.brew_bundle import install_packages
from dotfiles_install.claude_setup import register_mcp_servers, write_user_settings
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
    Phase(
        2,
        "Privileged setup (fish shell, firewall, Touch ID)",
        _MAC,
        privileged=True,
        run=privileged_setup,
    ),
    Phase(3, "dotfiles symlinks (stow)", _MAC, run=stow_dotfiles),
    Phase(4, "Machine-local overlay files", _MAC, run=seed_overlays),
    Phase(5, "Fish plugins (fisher)", _MAC, run=install_fish_plugins),
    Phase(6, "tmux plugins (TPM)", _MAC, run=install_tmux_plugins),
    Phase(7, "atuin history import", _MAC, run=import_atuin_history),
    Phase(8, "iTerm2 preferences", _MAC, run=configure_iterm2),
    Phase(9, "Python CLI tools (uv)", _MAC, run=install_uv_tools),
    Phase(10, "Git clone hook (notify-on-clone)", _MAC, run=report_clone_hook),
    Phase(11, "Claude Code CLI", _MAC, run=install_claude_cli),
    Phase(12, "Claude Code MCP servers", _MAC, run=register_mcp_servers),
    Phase(13, "Claude Code user settings", _MAC, run=write_user_settings),
    Phase(14, "Ollama model for GitLens", _MAC),
    Phase(15, "macOS system defaults (macos.sh)", _MAC),
    Phase(16, "Dock layout (dock.sh)", _MAC),
    Phase(17, "Verification & summary", _MAC),
)


def phases_for(target: OS | None = None) -> list[Phase]:
    """Return the registry phases applicable to ``target`` (default: the current OS)."""
    resolved = target if target is not None else current_os()
    return [phase for phase in REGISTRY if phase.applies(resolved)]
