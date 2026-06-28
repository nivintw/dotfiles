# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for the OS-detection helpers that drive per-phase gating."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from dotfiles_install import os_detect
from dotfiles_install.os_detect import OS, current_os, is_wsl

if TYPE_CHECKING:
    from pathlib import Path


def test_macos_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    """``darwin`` resolves to macOS."""
    monkeypatch.setattr(os_detect.sys, "platform", "darwin")
    assert current_os() is OS.MACOS


def test_plain_linux_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-WSL Linux kernel resolves to Linux."""
    monkeypatch.setattr(os_detect.sys, "platform", "linux")
    monkeypatch.setattr(os_detect, "is_wsl", lambda: False)
    assert current_os() is OS.LINUX


def test_wsl_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Linux kernel reporting WSL resolves to WSL."""
    monkeypatch.setattr(os_detect.sys, "platform", "linux")
    monkeypatch.setattr(os_detect, "is_wsl", lambda: True)
    assert current_os() is OS.WSL


def test_unsupported_platform_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """An untargeted platform raises rather than guessing."""
    monkeypatch.setattr(os_detect.sys, "platform", "sunos5")
    with pytest.raises(RuntimeError, match="unsupported platform"):
        current_os()


def test_is_wsl_false_off_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    """``is_wsl`` is False on a non-Linux platform without touching the filesystem."""
    monkeypatch.setattr(os_detect.sys, "platform", "darwin")
    assert is_wsl() is False


def test_is_wsl_reads_microsoft_marker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``is_wsl`` is True when the kernel osrelease names Microsoft."""
    osrelease = tmp_path / "osrelease"
    osrelease.write_text("5.15.0-microsoft-standard-WSL2\n")
    monkeypatch.setattr(os_detect.sys, "platform", "linux")
    monkeypatch.setattr(os_detect, "_WSL_OSRELEASE", osrelease)
    assert is_wsl() is True


def test_is_wsl_false_on_bare_metal_linux(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``is_wsl`` is False for a stock Linux osrelease."""
    osrelease = tmp_path / "osrelease"
    osrelease.write_text("6.8.0-generic\n")
    monkeypatch.setattr(os_detect.sys, "platform", "linux")
    monkeypatch.setattr(os_detect, "_WSL_OSRELEASE", osrelease)
    assert is_wsl() is False


def test_is_wsl_false_when_osrelease_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A missing osrelease file reads as not-WSL, not an error."""
    monkeypatch.setattr(os_detect.sys, "platform", "linux")
    monkeypatch.setattr(os_detect, "_WSL_OSRELEASE", tmp_path / "missing")
    assert is_wsl() is False
