# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for the installer CLI: flag surface, exit codes, and the stub run loop."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from dotfiles_install import cli
from dotfiles_install.cli import app, discover_bundles
from dotfiles_install.os_detect import OS

if TYPE_CHECKING:
    import pytest

runner = CliRunner()

USAGE_ERROR_EXIT = 2
RUNTIME_ERROR_EXIT = 1


def test_discover_bundles_matches_the_repo() -> None:
    """Bundle discovery returns the sorted ``Brewfile.d`` basenames."""
    assert discover_bundles() == ["1password", "homelab", "personal"]


def test_help_exits_zero_and_lists_bundles() -> None:
    """``--help`` succeeds and shows the discovered opt-in bundles."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Opt-in Brewfile bundles" in result.output
    assert "1password" in result.output


def test_unknown_bundle_is_a_usage_error() -> None:
    """An unrecognized ``--bundle`` value exits 2."""
    result = runner.invoke(app, ["--bundle", "nope"])
    assert result.exit_code == USAGE_ERROR_EXIT


def test_bundle_without_value_is_a_usage_error() -> None:
    """``--bundle`` with no value exits 2."""
    result = runner.invoke(app, ["--bundle"])
    assert result.exit_code == USAGE_ERROR_EXIT


def test_keep_bundles_conflicts_with_no_bundles() -> None:
    """``--keep-bundles`` combined with ``--no-bundles`` exits 2."""
    result = runner.invoke(app, ["--keep-bundles", "--no-bundles"])
    assert result.exit_code == USAGE_ERROR_EXIT


def test_keep_bundles_conflicts_with_bundle() -> None:
    """``--keep-bundles`` combined with ``--bundle`` exits 2."""
    result = runner.invoke(app, ["--keep-bundles", "--bundle", "1password"])
    assert result.exit_code == USAGE_ERROR_EXIT


def test_unexpected_argument_is_a_usage_error() -> None:
    """An unknown flag exits 2."""
    result = runner.invoke(app, ["--bogus"])
    assert result.exit_code == USAGE_ERROR_EXIT


def test_run_on_non_macos_exits_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Off macOS the run aborts with exit 1 (the installer is macOS-only today)."""
    monkeypatch.setattr(cli, "current_os", lambda: OS.LINUX)
    result = runner.invoke(app, [])
    assert result.exit_code == RUNTIME_ERROR_EXIT
    assert "macOS only" in result.output


def test_run_on_unsupported_platform_exits_one_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    """An exotic platform (current_os raises) exits 1 with a message, not a traceback."""

    def _raise() -> OS:
        msg = "unsupported platform: 'freebsd14'"
        raise RuntimeError(msg)

    monkeypatch.setattr(cli, "current_os", _raise)
    result = runner.invoke(app, [])
    assert result.exit_code == RUNTIME_ERROR_EXIT
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert "macOS" in result.output


def test_run_on_macos_walks_stub_phases(monkeypatch: pytest.MonkeyPatch) -> None:
    """On macOS the run completes, reporting each phase as not-yet-ported."""
    monkeypatch.setattr(cli, "current_os", lambda: OS.MACOS)
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "dotfiles bootstrap" in result.output
    assert "not yet ported" in result.output
    # Every phase header is printed.
    assert "[0] Bootstrap toolchain (Homebrew + uv)" in result.output
    assert "[17] Verification & summary" in result.output


def test_valid_bundle_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """A known ``--bundle`` value passes validation and the run proceeds."""
    monkeypatch.setattr(cli, "current_os", lambda: OS.MACOS)
    result = runner.invoke(app, ["--bundle", "1password"])
    assert result.exit_code == 0
    assert "unknown bundle" not in result.output
