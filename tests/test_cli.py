# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for the installer CLI: flag surface, exit codes, verify modes, and the run loop."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from dotfiles_install import brew_bundle, cli, commands, ollama, privileged, verify_install
from dotfiles_install.cli import app, discover_bundles
from dotfiles_install.os_detect import OS
from dotfiles_install.phases import Phase

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

runner = CliRunner()

USAGE_ERROR_EXIT = 2
RUNTIME_ERROR_EXIT = 1


@pytest.fixture
def _no_real_installs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Neutralize every phase body: stub command execution and isolate ``$HOME``.

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
    # Phase 18 (verify & summary) runs in the walk too; stub its emitter so the CLI tests don't
    # shell out to brew/dscl/socketfilterfw or read the host's /etc. The verify logic itself is
    # covered by tests/test_verify_install.py.
    monkeypatch.setattr(verify_install, "iter_records", lambda *_a, **_k: iter(()))


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


@pytest.mark.usefixtures("_no_real_installs")
def test_run_on_linux_walks_the_os_agnostic_phases(monkeypatch: pytest.MonkeyPatch) -> None:
    """Off macOS the run walks the OS-agnostic phases (now incl. Linuxbrew 0-1), not the macOS."""
    monkeypatch.setattr(cli, "current_os", lambda: OS.LINUX)
    # The OS-branching phase bodies resolve current_os() themselves; re-pin them to LINUX so
    # the walk exercises the Linux paths (overriding the fixture's macOS pin).
    for mod in (privileged, brew_bundle, ollama, verify_install):
        monkeypatch.setattr(mod, "current_os", lambda: OS.LINUX)
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "dotfiles bootstrap" in result.output
    # Packages (0-1), the privileged block (2), stow (3), ollama (14), and verify (18) all run...
    assert "[0] Bootstrap toolchain" in result.output
    assert "[1] Homebrew packages" in result.output
    assert "[2] Privileged setup" in result.output
    assert "[3] dotfiles symlinks (stow)" in result.output
    assert "[14] Ollama models" in result.output
    assert "[18] Verification & summary" in result.output
    # ...while the macOS-purpose phases (iTerm2, macos.sh, Dock, VS Code) are gated out.
    assert "[8] iTerm2 preferences" not in result.output
    assert "[15] macOS system defaults" not in result.output
    assert "[16] Dock layout" not in result.output
    assert "[17] VS Code user settings" not in result.output


def test_run_with_no_applicable_phases_exits_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A target with zero applicable phases exits 1 with a message (the empty-set safety net)."""
    monkeypatch.setattr(cli, "current_os", lambda: OS.LINUX)
    monkeypatch.setattr(cli, "phases_for", lambda _target=None: [])
    result = runner.invoke(app, [])
    assert result.exit_code == RUNTIME_ERROR_EXIT
    assert "no install phases apply" in result.output


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
    """On macOS the run completes and every phase executes (the port is complete)."""
    monkeypatch.setattr(cli, "current_os", lambda: OS.MACOS)
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "dotfiles bootstrap" in result.output
    # No phase is a stub any more, so the not-yet-ported notice is never emitted.
    assert "not yet ported" not in result.output
    # Every phase header is printed, from phase 0 through the final verification phase.
    assert "[0] Bootstrap toolchain (Homebrew + uv)" in result.output
    assert "[18] Verification & summary" in result.output


@pytest.mark.usefixtures("_no_real_installs")
def test_no_dock_flag_skips_the_dock_phase(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--no-dock`` still walks phase 16 (header prints) but its body skips dock.sh."""
    monkeypatch.setattr(cli, "current_os", lambda: OS.MACOS)
    result = runner.invoke(app, ["--no-dock"])
    assert result.exit_code == 0
    assert "[16] Dock layout (dock.sh)" in result.output
    assert "Dock layout skipped (--no-dock)" in result.output


def test_verify_flag_exits_zero_when_healthy(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--verify`` short-circuits the install and exits 0 when run_check finds no problems."""
    monkeypatch.setattr(verify_install, "run_check", lambda _ctx: 0)
    result = runner.invoke(app, ["--verify"])
    assert result.exit_code == 0


def test_verify_flag_exits_one_when_problems(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--verify`` exits 1 when run_check reports any problem (the doctor's failure signal)."""
    monkeypatch.setattr(verify_install, "run_check", lambda _ctx: 3)
    result = runner.invoke(app, ["--verify"])
    assert result.exit_code == 1


def test_verify_flag_does_not_run_the_install(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--verify`` must not walk the phase registry (it's a read-only re-check)."""
    monkeypatch.setattr(verify_install, "run_check", lambda _ctx: 0)

    def _boom() -> OS:
        msg = "the install walk must not start under --verify"
        raise AssertionError(msg)

    monkeypatch.setattr(cli, "current_os", _boom)
    assert runner.invoke(app, ["--verify"]).exit_code == 0


def test_verify_stream_flag_emits_records_and_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--verify-stream`` writes the raw records via typer.echo and exits 0 for the harness."""

    def _emit(*, core: bool, write: Callable[[str], object]) -> None:  # noqa: ARG001
        write("OK\tfine")
        write("VERIFY_DONE\t0")

    monkeypatch.setattr(verify_install, "emit_stream", _emit)
    result = runner.invoke(app, ["--verify-stream"])
    assert result.exit_code == 0
    assert "OK\tfine" in result.output
    assert "VERIFY_DONE\t0" in result.output


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

    raising = Phase("boom", frozenset({OS.MACOS}), run=_boom)
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
