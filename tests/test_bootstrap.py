# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for phase 0 (bootstrap toolchain).

The behaviors that matter when porting the bash: the ``command -v`` idempotency guard skips a
present tool, the captured-then-run installers report success only when both the fetch and the
run succeed, and the hard post-check aborts the run (exit 1) when a tool is still missing after
the install attempt.
"""

from __future__ import annotations

import io
import subprocess
from typing import TYPE_CHECKING

import pytest
from rich.console import Console

from dotfiles_install import bootstrap, commands
from dotfiles_install.context import InstallContext
from dotfiles_install.ui import UI

if TYPE_CHECKING:
    from collections.abc import Iterator


def _ctx() -> InstallContext:
    """Build an install context over in-memory consoles."""
    ui = UI(stdout=Console(file=io.StringIO()), stderr=Console(file=io.StringIO()))
    return InstallContext(ui=ui)


def test_bootstrap_skips_installs_when_tools_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """With brew and uv already on PATH, no installer runs."""
    monkeypatch.setattr(commands, "which", lambda name: f"/usr/bin/{name}")

    def _no_retry(*_args: object, **_kwargs: object) -> bool:
        msg = "retry should not run when the tool is already present"
        raise AssertionError(msg)

    monkeypatch.setattr(commands, "retry", _no_retry)
    bootstrap.bootstrap_toolchain(_ctx())  # must not raise


def test_homebrew_installs_when_absent_then_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing brew triggers the retried install, then the post-check passes."""
    presence: Iterator[str | None] = iter([None, "/opt/homebrew/bin/brew"])
    monkeypatch.setattr(commands, "which", lambda _name: next(presence))
    monkeypatch.setattr(bootstrap, "_activate_homebrew", lambda: None)
    called: list[str] = []

    def _retry(description: str, _attempts: int, _func: object, **_kwargs: object) -> bool:
        called.append(description)
        return True

    monkeypatch.setattr(commands, "retry", _retry)
    bootstrap._ensure_homebrew(_ctx())  # must not raise
    assert called == ["Homebrew install"]


def test_homebrew_hard_fails_when_still_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """If brew is still missing after the install attempt, the run aborts with exit 1."""
    monkeypatch.setattr(commands, "which", lambda _name: None)
    monkeypatch.setattr(bootstrap, "_activate_homebrew", lambda: None)
    monkeypatch.setattr(commands, "retry", lambda *_a, **_k: False)

    with pytest.raises(SystemExit) as excinfo:
        bootstrap._ensure_homebrew(_ctx())
    assert excinfo.value.code == 1


def test_install_homebrew_runs_the_captured_script(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Homebrew installer runs the fetched script under bash with NONINTERACTIVE set."""
    captured: dict[str, object] = {}
    monkeypatch.setattr(commands, "fetch", lambda _argv: "INSTALL_SCRIPT")

    def _run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        captured["env"] = kwargs.get("env")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(commands, "run", _run)
    assert bootstrap._install_homebrew() is True
    assert captured["argv"] == ["/bin/bash", "-c", "INSTALL_SCRIPT"]
    assert captured["env"] == {"NONINTERACTIVE": "1"}


def test_install_homebrew_fails_on_failed_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed download means the install attempt fails without running anything."""
    monkeypatch.setattr(commands, "fetch", lambda _argv: None)

    def _run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        msg = "run must not be called when the fetch failed"
        raise AssertionError(msg)

    monkeypatch.setattr(commands, "run", _run)
    assert bootstrap._install_homebrew() is False


def test_install_uv_pipes_the_captured_script_to_sh(monkeypatch: pytest.MonkeyPatch) -> None:
    """The uv installer pipes the fetched script into ``sh`` via stdin."""
    captured: dict[str, object] = {}
    monkeypatch.setattr(commands, "fetch", lambda _argv: "UV_SCRIPT")

    def _run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        captured["input_text"] = kwargs.get("input_text")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(commands, "run", _run)
    assert bootstrap._install_uv() is True
    assert captured["argv"] == ["sh"]
    assert captured["input_text"] == "UV_SCRIPT"
