# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""The hand-maintained install manifests stay well-formed.

Brewfile and uv_tools.txt are parsed by `brew bundle` and install.sh respectively;
a stray line is a runtime failure on a fresh machine. Cheap to assert their shape.
"""

import re
from typing import TYPE_CHECKING

from conftest import REPO

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

# Brewfiles are Ruby; `if`/`end` bracket the `OS.mac?` blocks that gate macOS-only
# formulae/casks/extensions off Linuxbrew (Homebrew evaluates them at bundle time).
BREW_DIRECTIVES = ("tap", "brew", "cask", "mas", "vscode", "if", "end")
# A tool name, optionally with a uv/pip extras suffix like `reuse[charset-normalizer]`.
TOOL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9._,-]+\])?$")


def _meaningful_lines(path: Path) -> Iterator[tuple[int, str]]:
    """Non-blank, non-comment lines (stripped), with their 1-based line numbers."""
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if line and not line.startswith("#"):
            yield n, line


def _brewfiles() -> list[Path]:
    """The baseline Brewfile plus every opt-in bundle (Brewfile.d/<name>.brewfile)."""
    return [REPO / "Brewfile", *sorted((REPO / "Brewfile.d").glob("*.brewfile"))]


def test_brewfile_lines_have_known_directives() -> None:
    """Every meaningful line in the Brewfile and its opt-in bundles is a known directive."""
    bad = [
        (path.name, n, line)
        for path in _brewfiles()
        for n, line in _meaningful_lines(path)
        if line.split(" ", 1)[0] not in BREW_DIRECTIVES
    ]
    assert not bad, f"Brewfile lines with unknown directive: {bad}"


def test_brewfile_os_conditionals_are_balanced_and_mac_only() -> None:
    """Each Brewfile's ``if``/``end`` gates are balanced and gate exactly on ``OS.mac?``.

    The macOS-only formulae/casks/extensions are wrapped in ``if OS.mac? … end`` so ``brew
    bundle`` skips them on Linuxbrew. ``if`` and ``end`` are accepted as line directives (see
    BREW_DIRECTIVES), but the line-shape check alone would let an orphan ``if``/``end`` or a
    typo'd condition (``if OS.linux?``) through — and a wrong condition silently skips the whole
    macOS block *on a Mac* with no other test failing. Pin both balance and the exact condition.
    These blocks are flat (no nesting/else), so a simple count comparison is sufficient.
    """
    for path in _brewfiles():
        lines = [line for _n, line in _meaningful_lines(path)]
        ifs = [line for line in lines if line.split(maxsplit=1)[0] == "if"]
        ends = [line for line in lines if line == "end"]
        assert len(ifs) == len(ends), (
            f"{path.name}: unbalanced Brewfile if/end ({len(ifs)} if vs {len(ends)} end)"
        )
        bad_conditions = [line for line in ifs if line != "if OS.mac?"]
        assert not bad_conditions, (
            f"{path.name}: only `if OS.mac?` gates are allowed; got {bad_conditions}"
        )


def test_uv_tools_first_token_is_a_tool_name() -> None:
    """Each uv_tools.txt line begins with a plausible tool name (optionally extras)."""
    bad = [
        (n, line)
        for n, line in _meaningful_lines(REPO / "uv_tools.txt")
        if not TOOL_NAME.match(line.split()[0])
    ]
    assert not bad, f"uv_tools.txt lines with implausible tool name: {bad}"


def test_uv_tools_with_flags_are_paired() -> None:
    """Every `--with` flag in uv_tools.txt is followed by a package argument."""
    # Each `--with` must be followed by a package argument, not end-of-line.
    for n, line in _meaningful_lines(REPO / "uv_tools.txt"):
        toks = line.split()
        for i, t in enumerate(toks):
            if t == "--with":
                assert i + 1 < len(toks), f"uv_tools.txt:{n}: dangling --with"
