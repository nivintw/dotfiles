# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""The run-time context handed to every install phase.

Bundles the shared UI sink with the resolved CLI options (the ``--core`` profile and the
bundle-selection flags) so a phase body needs only this one object, not the CLI internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dotfiles_install.ui import UI


@dataclass
class InstallContext:
    """Shared state passed to each phase: the UI plus the resolved install options."""

    ui: UI
    core: bool = False
    no_bundles: bool = False
    keep_bundles: bool = False
    requested_bundles: tuple[str, ...] = field(default_factory=tuple)
    no_dock: bool = False
    shell: str | None = None
