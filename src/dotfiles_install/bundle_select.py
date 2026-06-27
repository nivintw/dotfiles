# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Opt-in Brewfile bundle-selection helpers.

The selection file (``~/.config/dotfiles/bundles``) records, one name per line,
which ``Brewfile.d/<name>.brewfile`` bundles to install on this machine.
``write_bundles`` and ``parse_bundles`` are exact inverses; ``fzf_preselect_bind``
builds the fzf ``load:`` binding that pre-selects the saved choices in the picker.

Ported from ``scripts/bundle_select.sh`` (behavior pinned by
``tests/bundle_select.bats``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_HEADER = (
    "# Opt-in Brewfile bundles for this machine, one name per line. Each maps\n"
    "# to <repo>/Brewfile.d/<name>.brewfile. Lines starting with # are ignored.\n"
    "# Edit and re-run install.sh to change what gets installed.\n"
    "#\n"
    "# Available bundles:\n"
)


def write_bundles(sel_file: Path, available: list[str], chosen: list[str]) -> None:
    """Write the selection file: a documented header then the chosen names.

    Every available bundle is listed as a ``#   <name>`` comment hint; each chosen
    name is written bare, one per line, so ``parse_bundles`` reads them back.
    """
    avail_hints = "".join(f"#   {name}\n" for name in available)
    chosen_lines = "".join(f"{name}\n" for name in chosen)
    sel_file.write_text(f"{_HEADER}{avail_hints}\n{chosen_lines}")


def parse_bundles(sel_file: Path) -> list[str]:
    """Read the chosen bundle names back, skipping comments and blank lines.

    A missing file reads as an empty selection (baseline only), never an error.
    """
    if not sel_file.is_file():
        return []
    return [line for line in sel_file.read_text().splitlines() if line and not line.startswith("#")]


def fzf_preselect_bind(available: list[str], chosen: list[str]) -> str:
    """Build the fzf ``load:`` binding pre-selecting ``chosen`` by menu position.

    Positions are 1-based and emitted in ``chosen`` order (which need not match the
    menu order); names absent from ``available`` are skipped. Returns ``""`` when
    nothing resolves.
    """
    positions: dict[str, int] = {}
    for index, name in enumerate(available, start=1):
        positions.setdefault(name, index)  # first occurrence wins, matching the bash loop
    parts = [f"pos({positions[name]})+select" for name in chosen if name in positions]
    if not parts:
        return ""
    return "load:" + "+".join(parts)
