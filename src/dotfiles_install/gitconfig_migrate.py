# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Safe one-time adoption of a pre-existing ``~/.gitconfig`` before stow.

Before stow symlinks the repo's tracked ``.gitconfig`` over a fresh machine's real one,
``gitconfig_migrate`` backs the real file up (never clobbering an earlier backup) and folds
its contents into the machine-local overlay (``~/.gitconfig_local``), which the baseline
``[include]``s last so the user's settings win. The fold happens *before* the original is
moved aside, so a write failure leaves the original untouched — never destroyed-and-unmigrated.

A migrated ``[include]`` of the overlay itself is stripped to avoid an include loop. A
symlinked or absent target is a strict no-op (already-managed machine).

Ported from ``scripts/gitconfig_migrate.sh`` (behavior pinned by ``tests/gitconfig_migrate.bats``).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_SECTION_RE = re.compile(r"^\s*\[")
_INCLUDE_RE = re.compile(r"^\s*\[\s*include(\s|\]|if)", re.IGNORECASE)
_PATH_RE = re.compile(r"^\s*path\s*=", re.IGNORECASE)


def gitconfig_migrate(target: Path, overlay: Path, baseline: Path) -> str:
    """Adopt a pre-existing ``target`` gitconfig, returning a human-readable result line.

    No-op (returns ``""``) when ``target`` is a symlink or not a regular file. Removes
    ``target`` when it is byte-identical to ``baseline``. Otherwise folds its contents into
    ``overlay`` and moves it aside to a non-clobbering ``*.pre-stow.bak`` backup. Raises
    ``OSError`` on a filesystem failure, before ``target`` is moved, so nothing is lost.
    """
    if target.is_symlink() or not target.is_file():
        return ""
    raw = target.read_bytes()
    if raw == baseline.read_bytes():
        target.unlink()
        return f"removed {target} (identical to the repo baseline)"
    backup = _next_backup_path(target)
    # Decode byte-faithfully: surrogateescape round-trips non-UTF-8 bytes through str ops and
    # back out on the encode below, matching the byte-safe cmp/awk the bash original used.
    migrated = _strip_self_include(raw.decode("utf-8", errors="surrogateescape"), overlay.name)
    _append_to_overlay(overlay, target, backup, migrated)
    target.rename(backup)
    return f"backed up {target} -> {backup} and migrated its contents into {overlay}"


def _next_backup_path(target: Path) -> Path:
    """Return the first free ``<target>.pre-stow.bak[.N]`` path, never clobbering."""
    backup = target.with_name(f"{target.name}.pre-stow.bak")
    counter = 1
    while backup.exists():
        backup = target.with_name(f"{target.name}.pre-stow.bak.{counter}")
        counter += 1
    return backup


def _append_to_overlay(overlay: Path, target: Path, backup: Path, migrated: str) -> None:
    """Append the migrated config to ``overlay`` under a provenance banner."""
    overlay.parent.mkdir(parents=True, exist_ok=True)
    banner = f"\n# --- migrated from {target} by install.sh (see {backup}) ---\n"
    with overlay.open("a", encoding="utf-8", errors="surrogateescape") as handle:
        handle.write(f"{banner}{migrated}\n")


def _strip_self_include(content: str, overlay_basename: str) -> str:
    """Return ``content`` with any ``[include]`` section targeting the overlay removed."""
    # Split on \n only (not str.splitlines, which also breaks on \r, \v, \f, … and would strip
    # \r from CRLF files) so the round-tripped bytes match the bash awk (RS="\n").
    lines = content.split("\n")
    out: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if _SECTION_RE.match(line) is None:
            out.append(line)
            continue
        section = [line]
        while index < len(lines) and _SECTION_RE.match(lines[index]) is None:
            section.append(lines[index])
            index += 1
        if not (_INCLUDE_RE.match(line) and _section_targets(section, overlay_basename)):
            out.extend(section)
    return "\n".join(out)


def _section_targets(section: list[str], overlay_basename: str) -> bool:
    """Report whether any ``path =`` line in ``section`` resolves to the overlay basename."""
    wanted = overlay_basename.lower()
    for line in section:
        if _PATH_RE.match(line) is None:
            continue
        value = _PATH_RE.sub("", line.lower())
        value = re.sub(r"\s*[#;].*$", "", value).strip().strip('"')
        if value.rsplit("/", 1)[-1] == wanted:
            return True
    return False
