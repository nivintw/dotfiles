# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for the installer CLI: flag surface, exit codes, and the stub run loop."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from dotfiles_install import cli, commands, privileged
from dotfiles_install.cli import app, discover_bundles
from dotfiles_install.os_detect import OS
from dotfiles_install.phases import Phase

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

USAGE_ERROR_EXIT = 2
RUNTIME_ERROR_EXIT = 1


@pytest.fixture
def _no_real_installs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Neutralize the ported phase 0-13 bodies: stub command execution and isolate ``$HOME``.

    The macOS walk now runs the real bootstrap through Claude-settings phases, so
    ``commands.which`` reports every tool present (skipping installs) and ``commands.run`` is a
    no-op success; ``$HOME`` is redirected to a tmp dir so the stow/overlay/settings phases write
    only into a throwaway home and never touch the real one.
    """

    def _ok(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(commands, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(commands, "run", _ok)
    monkeypatch.setenv("HOME", str(tmp_path))
    # Phase 2 (privileged) now runs in the walk; repoint its /etc touchpoints at tmp files so the
    # CLI tests never read the host's real /etc/pam.d/sudo, sudo_local, or /etc/shells.
    pam_sudo = tmp_path / "sudo"
    pam_sudo.write_text("auth  include  sudo_local\n", encoding="utf-8")
    monkeypatch.setattr(privileged, "_PAM_SUDO", pam_sudo)
    monkeypatch.setattr(privileged, "_PAM_SUDO_LOCAL", tmp_path / "sudo_local")
    etc_shells = tmp_path / "shells"
    etc_shells.write_text("/bin/zsh\n", encoding="utf-8")
    monkeypatch.setattr(privileged, "_ETC_SHELLS", etc_shells)


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


@pytest.mark.usefixtures("_no_real_installs")
def test_run_on_macos_walks_all_phases(monkeypatch: pytest.MonkeyPatch) -> None:
    """On macOS the run completes; the still-unported phases report not-yet-ported."""
    monkeypatch.setattr(cli, "current_os", lambda: OS.MACOS)
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "dotfiles bootstrap" in result.output
    # Phases 14-17 are still stubs, so the not-yet-ported notice is still emitted.
    assert "not yet ported" in result.output
    # Every phase header is printed, including the now-ported phase 0.
    assert "[0] Bootstrap toolchain (Homebrew + uv)" in result.output
    assert "[17] Verification & summary" in result.output


def test_run_drops_the_sudo_ticket_when_a_phase_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """The run-level finally drops the sudo ticket (bash's EXIT-trap analog) even on an abort."""
    monkeypatch.setattr(cli, "current_os", lambda: OS.MACOS)
    calls: list[list[str]] = []

    def _record(argv: list[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(commands, "run", _record)

    def _boom(_ctx: object) -> None:
        msg = "phase exploded"
        raise RuntimeError(msg)

    raising = Phase(0, "boom", frozenset({OS.MACOS}), run=_boom)
    monkeypatch.setattr(cli, "phases_for", lambda _target=None: [raising])

    result = runner.invoke(app, [])

    assert result.exit_code != 0  # the abort surfaces
    assert ["sudo", "-k"] in calls  # ...but the ticket was still dropped


@pytest.mark.usefixtures("_no_real_installs")
def test_valid_bundle_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """A known ``--bundle`` value passes validation and the run proceeds."""
    monkeypatch.setattr(cli, "current_os", lambda: OS.MACOS)
    result = runner.invoke(app, ["--bundle", "1password"])
    assert result.exit_code == 0
    assert "unknown bundle" not in result.output


@pytest.mark.usefixtures("_no_real_installs")
def test_repeated_bundle_is_deduplicated(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``--bundle`` value passed twice is recorded once (matching bash's add_requested_bundle)."""
    monkeypatch.setattr(cli, "current_os", lambda: OS.MACOS)
    result = runner.invoke(app, ["--bundle", "1password", "--bundle", "1password"])
    assert result.exit_code == 0
    assert "1password, 1password" not in result.output
