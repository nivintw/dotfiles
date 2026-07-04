# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for phases 15-16: macOS defaults + Dock layout (system_setup).

Both are thin, non-fatal delegations to top-level bash scripts: success → ok line, non-zero →
warn-and-continue. The subprocess seam is stubbed; the assertions cover the message + the argv.
"""

from __future__ import annotations

import io
import subprocess
from typing import TYPE_CHECKING

from rich.console import Console

from dotfiles_install import commands, system_setup
from dotfiles_install.context import InstallContext
from dotfiles_install.ui import UI

if TYPE_CHECKING:
    import pytest


def _ctx() -> tuple[InstallContext, io.StringIO]:
    """An install context over an in-memory console (wide so lines don't wrap)."""
    out = io.StringIO()
    ui = UI(stdout=Console(file=out, width=200), stderr=Console(file=io.StringIO(), width=200))
    return InstallContext(ui=ui), out


def _completed(returncode: int) -> subprocess.CompletedProcess[str]:
    """A ``commands.run`` stub result carrying only the exit code (streamed output, no capture)."""
    return subprocess.CompletedProcess([], returncode=returncode, stdout=None, stderr=None)


def test_macos_defaults_ok_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """A zero exit reports applied and warns nothing."""
    monkeypatch.setattr(commands, "run_ok", lambda *_a, **_k: True)
    ctx, out = _ctx()
    system_setup.apply_macos_defaults(ctx)
    assert "macOS defaults applied" in out.getvalue()
    assert ctx.ui.warnings == []


def test_macos_defaults_warns_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-zero exit warns and continues (never raises)."""
    monkeypatch.setattr(commands, "run_ok", lambda *_a, **_k: False)
    ctx, _ = _ctx()
    system_setup.apply_macos_defaults(ctx)
    assert any("macos.sh exited non-zero" in w for w in ctx.ui.warnings)


def test_macos_defaults_runs_macos_sh(monkeypatch: pytest.MonkeyPatch) -> None:
    """It shells out to `bash <DOTFILES>/macos.sh`."""
    captured: dict[str, list[str]] = {}

    def _run_ok(argv: list[str], **_k: object) -> bool:
        captured["argv"] = list(argv)
        return True

    monkeypatch.setattr(commands, "run_ok", _run_ok)
    ctx, _ = _ctx()
    system_setup.apply_macos_defaults(ctx)
    assert captured["argv"][0] == "bash"
    assert captured["argv"][1].endswith("/macos.sh")


def test_dock_ok_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """A zero exit reports the Dock applied."""
    monkeypatch.setattr(commands, "run", lambda *_a, **_k: _completed(0))
    ctx, out = _ctx()
    system_setup.apply_dock_layout(ctx)
    assert "Dock layout applied" in out.getvalue()
    assert ctx.ui.warnings == []


def test_dock_warns_on_genuine_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-zero, non-skip exit warns and continues (e.g. a mid-rebuild dockutil failure)."""
    monkeypatch.setattr(commands, "run", lambda *_a, **_k: _completed(1))
    ctx, _ = _ctx()
    system_setup.apply_dock_layout(ctx)
    assert any("dock.sh exited non-zero" in w for w in ctx.ui.warnings)


def test_dock_skipped_when_dock_sh_bails(monkeypatch: pytest.MonkeyPatch) -> None:
    """dock.sh's own no-op bail (exit 2) reports as skipped, NOT as applied or a warning.

    Regression coverage for the bug three review passes independently caught: a plain
    zero-exit check couldn't tell a deliberate no-op bail from a real rebuild.
    """
    monkeypatch.setattr(commands, "run", lambda *_a, **_k: _completed(2))
    ctx, out = _ctx()
    system_setup.apply_dock_layout(ctx)
    assert "Dock layout skipped" in out.getvalue()
    assert "Dock layout applied" not in out.getvalue()
    assert ctx.ui.warnings == []


def test_dock_runs_dock_sh(monkeypatch: pytest.MonkeyPatch) -> None:
    """It shells out to `bash <DOTFILES>/dock.sh`."""
    captured: dict[str, list[str]] = {}

    def _run(argv: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        captured["argv"] = list(argv)
        return _completed(0)

    monkeypatch.setattr(commands, "run", _run)
    ctx, _ = _ctx()
    system_setup.apply_dock_layout(ctx)
    assert captured["argv"][0] == "bash"
    assert captured["argv"][1].endswith("/dock.sh")


def test_dock_skipped_when_no_dock(monkeypatch: pytest.MonkeyPatch) -> None:
    """``--no-dock`` skips the phase entirely, never shelling out to dock.sh."""

    def _boom(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        msg = "dock.sh must not run under --no-dock"
        raise AssertionError(msg)

    monkeypatch.setattr(commands, "run", _boom)
    ctx, out = _ctx()
    ctx.no_dock = True
    system_setup.apply_dock_layout(ctx)
    assert "Dock layout skipped" in out.getvalue()
    assert ctx.ui.warnings == []
