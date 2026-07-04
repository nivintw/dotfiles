# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Repo layout: the dotfiles root, the machine-private config dir, and opt-in bundle discovery.

A single source of truth for *where things live* — the repo root, ``~/.config/dotfiles``, and
the ``Brewfile.d/<name>.brewfile`` bundle set — shared by the CLI (which validates ``--bundle``
names) and the phases that read/write machine-local overlays, so they can never disagree about
where things live.
"""

from __future__ import annotations

from pathlib import Path

# Repo root: src/dotfiles_install/layout.py → parents[2] is the dotfiles checkout.
DOTFILES = Path(__file__).resolve().parents[2]
# Where opt-in bundles live; the one place the ``Brewfile.d`` location is spelled.
BUNDLES_DIR = DOTFILES / "Brewfile.d"


def config_dir() -> Path:
    """Return the machine-private dotfiles config dir (``~/.config/dotfiles``).

    Resolved lazily (not a module constant) so it honors ``$HOME`` at call time — correct in a
    long-lived process and redirectable in tests.
    """
    return Path.home() / ".config" / "dotfiles"


def discover_bundles(bundles_dir: Path = BUNDLES_DIR) -> list[str]:
    """Return the opt-in bundle names (``Brewfile.d/<name>.brewfile`` basenames), sorted."""
    return sorted(path.stem for path in bundles_dir.glob("*.brewfile"))
