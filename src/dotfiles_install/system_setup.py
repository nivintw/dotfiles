# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Phases 15-16: apply the macOS system defaults and the Dock layout.

Both shell out to the top-level ``macos.sh`` / ``dock.sh`` scripts (config-as-code that asserts
the declared prefs / Dock over whatever was set by hand). Each is **non-fatal**: a failure — for
example no GUI/Dock session in a headless VM — warns and continues, so it never aborts the run
right before the verification summary. Their output streams to the terminal as it did under bash.

Ported from ``install.sh`` phases 15-16.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dotfiles_install import commands
from dotfiles_install.layout import DOTFILES

if TYPE_CHECKING:
    from dotfiles_install.context import InstallContext


def apply_macos_defaults(ctx: InstallContext) -> None:
    """Phase 15: run ``macos.sh`` (curated ``defaults write`` tweaks); non-fatal."""
    ctx.ui.detail("applies the system preferences declared in macos.sh (overrides manual tweaks)")
    if commands.run_ok(["bash", str(DOTFILES / "macos.sh")]):
        ctx.ui.ok("macOS defaults applied")
    else:
        ctx.ui.warn(
            "macos.sh exited non-zero — continuing (check ~/.config/dotfiles/macos.local.sh; "
            "some defaults may not have applied)",
        )


def apply_dock_layout(ctx: InstallContext) -> None:
    """Phase 16: rebuild the Dock from ``dock.sh`` (dockutil); non-fatal."""
    if commands.run_ok(["bash", str(DOTFILES / "dock.sh")]):
        ctx.ui.ok("Dock layout applied")
    else:
        ctx.ui.warn(
            "dock.sh exited non-zero — continuing (the Dock may need a GUI session; "
            "re-run install.sh)",
        )
