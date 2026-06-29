# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Subprocess + retry helpers for the install phases.

Thin, injectable wrappers around :mod:`subprocess` and :func:`shutil.which` so the phase
bodies stay readable and unit tests can monkeypatch a single seam instead of patching the
standard library. Mirrors the bash installer's ``command -v`` checks, its ``retry`` helper,
and its "capture the curl|bash script, then run it" bootstrap doctrine (a failed download
must fail the attempt, not silently no-op).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

    from dotfiles_install.ui import UI

_RETRY_DELAY_SECONDS = 3.0
_COMMAND_NOT_FOUND = 127  # conventional shell exit code for a missing executable


def which(name: str) -> str | None:
    """Return the resolved path of ``name`` on ``PATH``, or ``None`` (bash ``command -v``)."""
    return shutil.which(name)


def run(
    argv: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    capture: bool = False,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``argv`` and return the completed process; never raises on a non-zero exit.

    With ``env`` the mapping is layered over the inherited environment (not a replacement).
    ``capture`` collects stdout/stderr as text; otherwise they stream to the terminal.
    ``input_text`` is fed to stdin (used to pipe a captured installer script into ``sh``).
    A missing executable is reported as exit ``127`` (like a shell's "command not found")
    rather than raising, so ``retry`` and the hard post-checks treat it as a failed attempt.
    """
    merged = {**os.environ, **env} if env is not None else None
    try:
        return subprocess.run(
            list(argv),
            env=merged,
            capture_output=capture,
            text=True,
            input=input_text,
            check=False,
        )
    except FileNotFoundError:
        empty = "" if capture else None
        return subprocess.CompletedProcess(
            list(argv),
            returncode=_COMMAND_NOT_FOUND,
            stdout=empty,
            stderr=empty,
        )


def run_ok(
    argv: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    capture: bool = False,
    input_text: str | None = None,
) -> bool:
    """Run ``argv`` and report whether it exited zero — for callers that need only success/failure.

    Folds the "did it succeed?" decision into the seam so callers don't open-code
    ``not result.returncode`` (and never flip its polarity by accident).
    """
    return run(argv, env=env, capture=capture, input_text=input_text).returncode == 0


def fetch(argv: Sequence[str]) -> str | None:
    """Capture stdout of ``argv`` (a ``curl`` invocation); return ``None`` if it fails or is empty.

    The captured-then-run pattern: piping ``curl`` straight into a shell hides a fetch failure
    as an empty no-op, so the bootstrap captures the script first and treats a failed or empty
    download as a failed attempt worth retrying.
    """
    result = run(argv, capture=True)
    if result.returncode:
        return None
    return result.stdout or None


def retry(description: str, attempts: int, func: Callable[[], bool], *, ui: UI) -> bool:
    """Call ``func`` up to ``attempts`` times until it returns ``True``; sleep between tries.

    Reports each failed attempt via ``ui.detail`` (matching the bash ``retry``) and returns
    whether any attempt succeeded. Callers that bootstrap a toolchain ignore the result and
    rely on a hard ``command -v`` post-check, so a persistent failure still aborts there.
    """
    for attempt in range(1, attempts + 1):
        if func():
            return True
        if attempt < attempts:
            ui.detail(
                f"{description} failed (attempt {attempt}/{attempts}) "
                f"— retrying in {int(_RETRY_DELAY_SECONDS)}s",
            )
            time.sleep(_RETRY_DELAY_SECONDS)
    return False


def read_text_or_empty(path: Path) -> str:
    """Read ``path`` as text, returning '' on any read error (bash ``cat ... 2>/dev/null``).

    Catches ``OSError`` broadly (missing, unreadable, not-a-directory) to mirror the bash
    degrade-to-empty, and decodes with ``surrogateescape`` so non-UTF-8 bytes round-trip
    instead of raising ``UnicodeDecodeError`` (a ``ValueError``, which ``OSError`` wouldn't
    catch). The shared home for the per-phase file reads that used to copy this idiom.
    """
    try:
        return path.read_text(encoding="utf-8", errors="surrogateescape")
    except OSError:
        return ""
