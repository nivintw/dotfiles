# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Operating-system detection for per-phase install gating.

The phase registry declares which OSes each phase applies to, so the OS-agnostic phases (stow,
fisher, atuin, the Claude/uv steps, …) run on macOS, Linux, and WSL2 while the macOS-specific
phases (Homebrew, the Touch-ID/firewall block, `defaults`, the Dock) stay gated to macOS — their
Linux ports are tracked under the #34 epic. This module gives that gating a small, testable
vocabulary, mirroring the bash installer's ``uname`` / ``is_wsl`` checks.
"""

from __future__ import annotations

import sys
from enum import Enum
from pathlib import Path

_WSL_OSRELEASE = Path("/proc/sys/kernel/osrelease")
_WSL_MARKERS = ("microsoft", "wsl")


class OS(Enum):
    """A target operating system the installer supports (or plans to)."""

    MACOS = "macos"
    LINUX = "linux"
    WSL = "wsl"


def is_wsl() -> bool:
    """Report whether the current Linux kernel is running under WSL."""
    if not sys.platform.startswith("linux"):
        return False
    try:
        release = _WSL_OSRELEASE.read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return any(marker in release for marker in _WSL_MARKERS)


def current_os() -> OS:
    """Return the OS this process is running on.

    Raises:
        RuntimeError: on a platform the installer does not target.
    """
    if sys.platform == "darwin":
        return OS.MACOS
    if sys.platform.startswith("linux"):
        return OS.WSL if is_wsl() else OS.LINUX
    msg = f"unsupported platform: {sys.platform!r}"
    raise RuntimeError(msg)
