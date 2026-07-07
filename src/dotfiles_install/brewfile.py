# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Pure Brewfile text parsers used by the brew-bundle phase.

``brewfile_taps`` lists the third-party taps a Brewfile declares (Homebrew refuses to load
formulae/casks from an untrusted tap, which aborts ``brew bundle`` on a clean machine, so the
phase trusts them first). ``brewfile_core`` returns the ``--core`` subset — taps + CLI
formulae only, with the GUI-bound entries (casks, VS Code extensions, Mac App Store apps,
whalebrew) stripped — so a headless/minimal install can skip the heavy cask downloads.

Ported from install.sh's Brewfile tap/core filtering (behavior pinned by
``tests/test_brewfile.py``); these operate on Brewfile *text* so the caller owns reading the
file (and the "missing file is empty, not an error" guard).
"""

from __future__ import annotations

import re

# A tap line: optional indent, the literal `tap`, whitespace, then a double-quoted name. Only
# the first quoted argument (the tap name) is captured; a trailing `, "url"` or comment, and
# any commented-out (`# tap ...`) or `untap` line, are excluded by anchoring `tap` as the first
# non-space token.
_TAP = re.compile(r'^[ \t]*tap[ \t]+"([^"]+)"')

# A GUI-bound directive line whose first non-space token is one of these — dropped under --core.
_GUI_DIRECTIVE = re.compile(r"^[ \t]*(?:cask|vscode|mas|whalebrew)[ \t]")

# A VS Code extension line: first non-space token is `vscode`. Settings Sync installs these
# out-of-band (not brew), so `brew bundle check` reports them missing on a healthy machine.
_VSCODE_DIRECTIVE = re.compile(r"^[ \t]*vscode[ \t]")


def brewfile_taps(text: str) -> list[str]:
    """Return the tap names declared in Brewfile ``text``, one per ``tap`` line, in order."""
    return [match.group(1) for line in text.splitlines() if (match := _TAP.match(line))]


def brewfile_core(text: str) -> str:
    """Return Brewfile ``text`` with the GUI-bound directive lines removed, others verbatim.

    Tap, brew, and comment lines (and the file's exact line endings) are preserved; ``cask`` /
    ``vscode`` / ``mas`` / ``whalebrew`` directive lines are dropped.
    """
    return "".join(
        line for line in text.splitlines(keepends=True) if not _GUI_DIRECTIVE.match(line)
    )


def brewfile_without_vscode(text: str) -> str:
    """Return Brewfile ``text`` with the ``vscode`` extension lines removed, others verbatim.

    VS Code extensions are managed by Settings Sync, not brew, so ``brew bundle check``
    routinely reports them missing even on a correctly-set-up machine. Everything else —
    taps, brews, casks, mas, whalebrew, comments, blank lines — is preserved (unlike
    :func:`brewfile_core`, which also strips the other GUI-bound directives).
    """
    return "".join(
        line for line in text.splitlines(keepends=True) if not _VSCODE_DIRECTIVE.match(line)
    )
