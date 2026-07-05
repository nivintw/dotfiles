# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Phase 2: resolve and persist the login-shell choice.

fish stays the default login shell; zsh is a fully-supported, selectable, non-default
option. The choice is persisted at ``~/.config/dotfiles/shell`` (one word: ``fish`` or
``zsh``) so a plain re-run of install.sh (no ``--shell`` flag) repeats the same choice
rather than silently drifting back to the fish default — the same persisted-preference
shape as :mod:`dotfiles_install.bundle_select`. Downstream phases (``privileged.py``'s
chsh, ``verify_install.py``'s login-shell check) re-read the persisted file directly
rather than threading a resolved value through :class:`InstallContext`, mirroring how
the opt-in bundle selection is written once here and re-read independently later.

Both shells' config trees are always stowed (``stow.py`` doesn't gate on this choice) —
only which one becomes the *login* shell is selected here.

Net-new for #35 (no bash/install.sh precedent to port from). Deliberately deviates from
that issue's original text, which proposed zsh as the new default — sign-off kept fish
default, adding zsh as opt-in instead, to avoid changing the login shell of every existing
install out from under people.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dotfiles_install.context import InstallContext

VALID_SHELLS: frozenset[str] = frozenset({"fish", "zsh"})
DEFAULT_SHELL = "fish"

_HEADER = (
    "# The dotfiles-selected login shell (fish or zsh). Written by dotfiles-install; a\n"
    "# plain re-run with no --shell flag repeats this choice. Edit this file directly\n"
    "# (then re-run install.sh) or pass --shell fish|zsh to change it.\n"
)


def shell_file(home: Path) -> Path:
    """Return the persisted-choice file path under ``home``."""
    return home / ".config" / "dotfiles" / "shell"


def read_shell(home: Path) -> str | None:
    """Return the persisted shell choice, or ``None`` if never set or invalid.

    A value outside :data:`VALID_SHELLS` (a hand-edit typo, corruption, an unexpected
    writer) reads the same as "never set" — falling back to the fish default — rather
    than propagating garbage into a ``chsh``/``commands.which`` call downstream. The next
    :func:`select_shell` run then re-persists a valid choice, self-healing the file.
    """
    path = shell_file(home)
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped if stripped in VALID_SHELLS else None
    return None


def write_shell(home: Path, shell: str) -> None:
    """Persist ``shell`` as the chosen login shell."""
    path = shell_file(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{_HEADER}{shell}\n", encoding="utf-8")


def resolve_shell(requested: str | None, home: Path) -> str:
    """Resolve the effective shell: ``--shell`` flag > persisted choice > the fish default."""
    return requested or read_shell(home) or DEFAULT_SHELL


def select_shell(ctx: InstallContext) -> None:
    """Resolve the login-shell choice and persist it for downstream phases to re-read."""
    home = Path.home()
    shell = resolve_shell(ctx.shell, home)
    write_shell(home, shell)
    suffix = " (default)" if shell == DEFAULT_SHELL else ""
    ctx.ui.ok(f"login shell: {shell}{suffix}")
