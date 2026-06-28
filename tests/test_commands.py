# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for the subprocess + retry helpers.

The seam phase bodies depend on: ``which`` (PATH lookup), ``run`` (env layering + the
capture/input wiring passed to :func:`subprocess.run`), ``fetch`` (capture the installer
script, treating a failed or empty download as ``None``), and ``retry`` (call until success,
sleeping between attempts).
"""

from __future__ import annotations

import io
import subprocess
from typing import TYPE_CHECKING

from rich.console import Console

from dotfiles_install import commands
from dotfiles_install.ui import UI

if TYPE_CHECKING:
    import pytest


def _ui() -> UI:
    """Build a UI writing to in-memory consoles (no terminal, plain output)."""
    return UI(stdout=Console(file=io.StringIO()), stderr=Console(file=io.StringIO()))


def test_which_delegates_to_shutil(monkeypatch: pytest.MonkeyPatch) -> None:
    """``which`` returns whatever ``shutil.which`` resolves."""
    monkeypatch.setattr(commands.shutil, "which", lambda name: f"/opt/bin/{name}")
    assert commands.which("brew") == "/opt/bin/brew"


def test_run_layers_env_over_the_inherited_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """A passed ``env`` is merged over ``os.environ``, not used as a replacement."""
    merged_env: dict[str, str] = {}
    recorded: dict[str, object] = {}

    def _fake(
        argv: list[str],
        *,
        env: dict[str, str],
        capture_output: bool,
        check: bool,
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        merged_env.update(env)
        recorded["argv"] = argv
        recorded["capture_output"] = capture_output
        recorded["input"] = kwargs["input"]
        recorded["check"] = check
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(commands.subprocess, "run", _fake)
    monkeypatch.setenv("INHERITED", "yes")
    commands.run(["brew", "bundle"], env={"NONINTERACTIVE": "1"}, capture=True, input_text="x")

    assert recorded["argv"] == ["brew", "bundle"]
    assert merged_env["NONINTERACTIVE"] == "1"
    assert merged_env["INHERITED"] == "yes"
    assert recorded["capture_output"] is True
    assert recorded["input"] == "x"
    assert recorded["check"] is False


def test_run_without_env_inherits_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no ``env`` the subprocess inherits the parent environment (``env=None``)."""
    captured: dict[str, object] = {}

    def _fake(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured.update(kwargs)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(commands.subprocess, "run", _fake)
    commands.run(["uname"])
    assert captured["env"] is None


def test_run_ok_reports_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """``run_ok`` returns True only when the underlying run exits zero."""
    codes = iter([0, 1])
    monkeypatch.setattr(
        commands,
        "run",
        lambda argv, **_kw: subprocess.CompletedProcess(list(argv), next(codes)),
    )
    assert commands.run_ok(["brew", "bundle"]) is True
    assert commands.run_ok(["brew", "bundle"]) is False


def test_fetch_returns_captured_script(monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful, non-empty download returns its stdout."""
    monkeypatch.setattr(
        commands,
        "run",
        lambda argv, **_kw: subprocess.CompletedProcess(argv, 0, stdout="#!/bin/sh\n"),
    )
    assert commands.fetch(["curl", "-fsSL", "https://x"]) == "#!/bin/sh\n"


def test_fetch_returns_none_on_failed_download(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-zero curl exit yields ``None`` (a failed attempt, not a silent no-op)."""
    monkeypatch.setattr(
        commands,
        "run",
        lambda argv, **_kw: subprocess.CompletedProcess(argv, 1, stdout="partial"),
    )
    assert commands.fetch(["curl", "https://x"]) is None


def test_fetch_returns_none_on_empty_download(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty body is treated as a failed download."""
    monkeypatch.setattr(
        commands,
        "run",
        lambda argv, **_kw: subprocess.CompletedProcess(argv, 0, stdout=""),
    )
    assert commands.fetch(["curl", "https://x"]) is None


def test_retry_succeeds_on_first_attempt() -> None:
    """A function that succeeds immediately runs exactly once and returns True."""
    attempts: list[str] = []

    def _succeed() -> bool:
        attempts.append("call")
        return True

    assert commands.retry("task", 3, _succeed, ui=_ui()) is True
    assert attempts == ["call"]


def test_retry_keeps_trying_until_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retries continue (sleeping between) until a later attempt succeeds."""
    monkeypatch.setattr(commands.time, "sleep", lambda _s: None)
    outcomes = iter([False, False, True])

    assert commands.retry("task", 3, lambda: next(outcomes), ui=_ui()) is True


def test_retry_gives_up_after_the_attempt_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """All attempts failing returns False after exactly ``attempts`` tries."""
    monkeypatch.setattr(commands.time, "sleep", lambda _s: None)
    attempts: list[str] = []

    def _fail() -> bool:
        attempts.append("call")
        return False

    assert commands.retry("task", 2, _fail, ui=_ui()) is False
    assert attempts == ["call", "call"]
