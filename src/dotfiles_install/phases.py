# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""The installer's ordered phase registry.

Each :class:`Phase` declares its display name, the operating systems it applies to (for
per-phase gating), and a ``privileged`` flag. That flag marks the **dedicated sudo-gated
block** (phase 3) — the one that acquires and drops a sudo ticket — not merely "any phase that
may invoke sudo": phase 1 also makes an optional ``sudo`` call (the pre-bundle Touch-ID enable)
yet is not ``privileged``. :data:`REGISTRY` mirrors ``install.sh``'s original phases 0-17, plus
phase 17 (VS Code settings) added after the bash port completed, plus phase 2 (login-shell
selection, #35) inserted between the brew bundle and the privileged block — every phase from
there on shifted up by one — so the registry now runs 0-19.
Every phase now carries a ``run`` callable and **executes real work** — the port is complete
(#67-#72) and this registry, driven by ``dotfiles-install``, is the installer; ``install.sh`` is
a thin stub that hands off to it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
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
from dotfiles_install.shell_select import select_shell
from dotfiles_install.stow import stow_dotfiles
from dotfiles_install.system_setup import apply_dock_layout, apply_macos_defaults
from dotfiles_install.verify_install import verify_and_summarize
from dotfiles_install.vscode_setup import write_vscode_settings

if TYPE_CHECKING:
    from collections.abc import Callable

    from dotfiles_install.context import InstallContext

    PhaseRun = Callable[[InstallContext], None]


@dataclass(frozen=True)
class Phase:
    """One install phase: its name, OS gating, body, and privilege need.

    ``number`` is stamped in once, at :data:`REGISTRY` assembly below — never passed to a
    ``Phase(...)`` call directly — so inserting a phase means adding one entry to
    ``_UNNUMBERED`` at the right spot, not renumbering every entry after it. It defaults to
    ``-1`` for a ``Phase`` built outside ``REGISTRY`` (e.g. an ad-hoc one in a test).
    """

    name: str
    os: frozenset[OS]
    run: PhaseRun
    privileged: bool = False
    number: int = -1

    def applies(self, target: OS) -> bool:
        """Report whether this phase runs on ``target``."""
        return target in self.os


_MAC = frozenset({OS.MACOS})
# Phases that run on macOS, Linux, and WSL2. Most phase bodies are OS-agnostic; the ones that
# touch OS internals branch internally on `current_os()` — the privileged block (Touch ID and
# the app firewall on macOS, ufw on Linux, no firewall on WSL), the Ollama MLX gate (Apple-only),
# and the verification probes (dscl/socketfilterfw vs passwd/ufw). Only the phases whose entire
# purpose is macOS state stay `_MAC`: iTerm2 `defaults`, `macos.sh`, and the Dock.
_ALL = frozenset({OS.MACOS, OS.LINUX, OS.WSL})

# The phase bodies in pipeline order, unnumbered — inserting a phase means adding one entry
# here at the right spot, nothing else. REGISTRY (below) stamps in each ``number`` from position.
_UNNUMBERED: tuple[Phase, ...] = (
    Phase("Bootstrap toolchain (Homebrew + uv)", _ALL, run=bootstrap_toolchain),
    Phase("Homebrew packages (brew bundle)", _ALL, run=install_packages),
    Phase("Login shell selection (fish default; zsh opt-in)", _ALL, run=select_shell),
    Phase(
        "Privileged setup (login shell, firewall; Touch ID on macOS)",
        _ALL,
        privileged=True,
        run=privileged_setup,
    ),
    Phase("dotfiles symlinks (stow)", _ALL, run=stow_dotfiles),
    Phase("Machine-local overlay files", _ALL, run=seed_overlays),
    Phase("Fish plugins (fisher)", _ALL, run=install_fish_plugins),
    Phase("tmux plugins (TPM)", _ALL, run=install_tmux_plugins),
    Phase("atuin history import", _ALL, run=import_atuin_history),
    Phase("iTerm2 preferences", _MAC, run=configure_iterm2),
    Phase("Python CLI tools (uv)", _ALL, run=install_uv_tools),
    Phase("Git clone hook (notify-on-clone)", _ALL, run=report_clone_hook),
    Phase("Claude Code CLI", _ALL, run=install_claude_cli),
    Phase("Claude Code MCP servers", _ALL, run=register_mcp_servers),
    Phase("Claude Code user settings", _ALL, run=write_user_settings),
    Phase("Ollama models", _ALL, run=install_ollama_models),
    Phase("macOS system defaults (macos.sh)", _MAC, run=apply_macos_defaults),
    Phase("Dock layout (dock.sh)", _MAC, run=apply_dock_layout),
    Phase("VS Code user settings", _MAC, run=write_vscode_settings),
    Phase("Verification & summary", _ALL, run=verify_and_summarize),
)
REGISTRY: tuple[Phase, ...] = tuple(replace(phase, number=i) for i, phase in enumerate(_UNNUMBERED))


def phases_for(target: OS | None = None) -> list[Phase]:
    """Return the registry phases applicable to ``target`` (default: the current OS)."""
    resolved = target if target is not None else current_os()
    return [phase for phase in REGISTRY if phase.applies(resolved)]
