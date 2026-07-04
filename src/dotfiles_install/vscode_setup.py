# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Phase 17: generate VS Code's user settings.json (macOS) from baseline ⊕ overlay.

Reuses the same baseline ⊕ machine-local overlay engine (:mod:`dotfiles_install.settings_merge`)
that Claude Code's user settings already use — VS Code's settings.json is no longer a stowed
static file, so the one genuinely per-machine value it carried (an absolute path to ``rg``,
needed because VS Code's bundled ripgrep keeps moving between releases and the todo-tree
extension's lookup doesn't track it) never lands in the tracked baseline.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from dotfiles_install import commands
from dotfiles_install.layout import DOTFILES, config_dir
from dotfiles_install.settings_merge import SettingsSpec, generate_settings

if TYPE_CHECKING:
    from dotfiles_install.context import InstallContext
    from dotfiles_install.settings_merge import JSONValue

_RIPGREP_KEY = "todo-tree.ripgrep.ripgrep"


def _ripgrep_overlay_addition(ctx: InstallContext) -> dict[str, JSONValue]:
    """Resolve this machine's ``rg`` (normally Homebrew's) as an overlay addition, or ``{}``.

    Empty when ``rg`` isn't on PATH — warned, since the merged output then omits the setting
    and todo-tree falls back to its own broken bundled-ripgrep lookup. Never touches the overlay
    file itself: :func:`generate_settings` seeds this in (if the key isn't already present) and
    does the one read + one atomic write.
    """
    rg = commands.which("rg")
    if rg is None:
        ctx.ui.warn(
            "rg not found on PATH — todo-tree's ripgrep lookup will likely fail (expected "
            "ripgrep from the core Brewfile; re-run brew bundle or check PATH)",
        )
        return {}
    return {_RIPGREP_KEY: rg}


def write_vscode_settings(ctx: InstallContext) -> None:
    """Phase 17: generate VS Code's user settings.json from the baseline ⊕ machine-local overlay."""
    generate_settings(
        ctx,
        SettingsSpec(
            baseline_path=DOTFILES / "vscode_settings.json",
            overlay_path=config_dir() / "vscode_settings.local.json",
            output_path=Path.home() / "Library/Application Support/Code/User/settings.json",
            label="VS Code settings",
        ),
        extra_overlay=_ripgrep_overlay_addition(ctx),
    )
