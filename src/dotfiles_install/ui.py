# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Rich-backed terminal UI mirroring the bash installer's ``ui_*`` helpers.

Reproduces the installer's output vocabulary — a bold banner, a bold-blue ``==>`` step header,
and green / blue / yellow / red status lines with ✔ / ● / ⚠ / ✗ glyphs — degrading to plain
``[ok]`` / ``[..]`` / ``[!!]`` / ``[xx]`` tags when stdout is not a TTY or ``NO_COLOR`` is set
(https://no-color.org), exactly like ``install.sh``'s color gate. Warnings are shown live *and*
accumulated into a ledger that the end-of-run summary replays, matching the bash ``WARNINGS`` array.

Ported from the ``ui_*`` helpers in ``install.sh``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from rich.console import Console


@dataclass(frozen=True)
class _Status:
    """A status line's decorated glyph, plain-text tag, and color."""

    glyph: str
    tag: str
    color: str


_OK = _Status("✔", "[ok]", "green")
_ACTIVE = _Status("●", "[..]", "blue")
_WARN = _Status("⚠", "[!!]", "yellow")
_ERR = _Status("✗", "[xx]", "red")


class UI:
    """Stateful console UI: status helpers plus a warnings ledger and an end-of-run summary."""

    def __init__(self, stdout: Console | None = None, stderr: Console | None = None) -> None:
        """Build a UI over the given stdout/stderr consoles (real terminals by default)."""
        self.console = stdout if stdout is not None else Console()
        self.err_console = stderr if stderr is not None else Console(stderr=True)
        self.warnings: list[str] = []

    @property
    def decorated(self) -> bool:
        """Whether to emit color + glyphs: stdout is a TTY and ``NO_COLOR`` is unset."""
        return self.console.is_terminal and "NO_COLOR" not in os.environ

    def _print(self, console: Console, text: str, color: str | None) -> None:
        """Print one line, applying ``color`` only when decorated, never parsing markup."""
        console.print(text, style=color if self.decorated else None, markup=False, highlight=False)

    def _status(self, console: Console, status: _Status, message: str) -> None:
        """Print a glyph/tag-prefixed status line."""
        symbol = status.glyph if self.decorated else status.tag
        self._print(console, f"{symbol} {message}", status.color)

    def banner(self, message: str) -> None:
        """Print a bold section banner preceded by a blank line."""
        self.console.print()
        self._print(self.console, message, "bold")

    def step(self, message: str) -> None:
        """Print a bold-blue ``==>`` step header preceded by a blank line."""
        self.console.print()
        self._print(self.console, f"==> {message}", "bold blue")

    def ok(self, message: str) -> None:
        """Print a green success line."""
        self._status(self.console, _OK, message)

    def active(self, message: str) -> None:
        """Print a blue in-progress line."""
        self._status(self.console, _ACTIVE, message)

    def warn(self, message: str) -> None:
        """Print a yellow warning line and record it in the ledger for the summary."""
        self.warnings.append(message)
        self._status(self.console, _WARN, message)

    def err(self, message: str) -> None:
        """Print a red error line to stderr."""
        self._status(self.err_console, _ERR, message)

    def detail(self, message: str) -> None:
        """Print a dim, indented detail line (no glyph)."""
        self._print(self.console, f"   {message}", "dim")

    def summary(self, verified: list[str], problems: list[str]) -> None:
        """Print the closing summary: verified items, then problems then the collected warnings."""
        self.step("Verified")
        for item in verified:
            self.ok(item)
        # Concatenate (no dedup), matching install.sh's `attention=(problems warnings)`: the two
        # come from different sources (verify failures vs the runtime ledger), so rarely overlap.
        attention = [*problems, *self.warnings]
        self.step("Needs attention")
        if not attention:
            self.ok("nothing — everything checks out")
            return
        for item in attention:
            # Print without re-recording: these warnings were already collected during the run.
            self._status(self.console, _WARN, item)
