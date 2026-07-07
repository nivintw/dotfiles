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

import os
import sys
from enum import Enum
from pathlib import Path

_WSL_OSRELEASE = Path("/proc/sys/kernel/osrelease")
_WSL_VERSION = Path("/proc/version")
_WSL_MARKERS = ("microsoft", "wsl")


class OS(Enum):
    """A target operating system the installer supports (or plans to)."""

    MACOS = "macos"
    LINUX = "linux"
    WSL = "wsl"


def is_wsl() -> bool:
    """Report whether the current Linux kernel is running under WSL.

    Checks three signals, any one of which is conclusive: the ``$WSL_DISTRO_NAME`` env
    fast-path (exported inside every WSL distro), then a Microsoft/WSL marker in either
    ``/proc/sys/kernel/osrelease`` or ``/proc/version`` (Microsoft's canonical recommended
    marker). Both files stay injectable (``_WSL_OSRELEASE`` / ``_WSL_VERSION``) so the suite
    can point them at fixtures on any host.
    """
    if not sys.platform.startswith("linux"):
        return False
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    for source in (_WSL_OSRELEASE, _WSL_VERSION):
        try:
            text = source.read_text(encoding="utf-8").lower()
        except OSError:
            continue
        if any(marker in text for marker in _WSL_MARKERS):
            return True
    return False


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
