# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for the Rich-backed installer UI: color gating, warnings ledger, and summary."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from rich.console import Console

from dotfiles_install.ui import UI

if TYPE_CHECKING:
    import pytest


def _plain_ui() -> tuple[UI, io.StringIO, io.StringIO]:
    """Build a UI writing to non-TTY buffers (undecorated: plain tags, no ANSI)."""
    out, err = io.StringIO(), io.StringIO()
    ui = UI(
        stdout=Console(file=out, force_terminal=False),
        stderr=Console(file=err, force_terminal=False),
    )
    return ui, out, err


def _color_ui(monkeypatch: pytest.MonkeyPatch) -> tuple[UI, io.StringIO]:
    """Build a decorated UI (forced TTY, NO_COLOR cleared): glyphs + ANSI."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    out = io.StringIO()
    ui = UI(stdout=Console(file=out, force_terminal=True, color_system="standard"))
    return ui, out


def test_undecorated_uses_ascii_tags_without_ansi() -> None:
    """Without a TTY, status lines use ``[ok]``-style tags and no escape codes."""
    ui, out, _ = _plain_ui()
    ui.ok("done")
    text = out.getvalue()
    assert "[ok] done" in text
    assert "\x1b[" not in text
    assert "✔" not in text


def test_no_color_env_forces_plain(monkeypatch: pytest.MonkeyPatch) -> None:
    """``NO_COLOR`` disables decoration even on a TTY."""
    monkeypatch.setenv("NO_COLOR", "1")
    out = io.StringIO()
    ui = UI(stdout=Console(file=out, force_terminal=True, color_system="standard"))
    assert ui.decorated is False
    ui.ok("done")
    assert "[ok] done" in out.getvalue()


def test_decorated_uses_glyphs_and_ansi(monkeypatch: pytest.MonkeyPatch) -> None:
    """On a TTY with color, status lines use glyphs and ANSI escapes."""
    ui, out = _color_ui(monkeypatch)
    assert ui.decorated is True
    ui.ok("done")
    text = out.getvalue()
    assert "✔ done" in text
    assert "\x1b[" in text


def test_warn_records_in_ledger() -> None:
    """Each warning is both printed and appended to the ledger."""
    ui, out, _ = _plain_ui()
    ui.warn("first")
    ui.warn("second")
    assert ui.warnings == ["first", "second"]
    assert "[!!] first" in out.getvalue()


def test_err_writes_to_stderr_only() -> None:
    """Errors go to the stderr console, not stdout."""
    ui, out, err = _plain_ui()
    ui.err("boom")
    assert "[xx] boom" in err.getvalue()
    assert "boom" not in out.getvalue()


def test_summary_clean_run_reports_all_clear() -> None:
    """With no problems or warnings, the summary reports everything checks out."""
    ui, out, _ = _plain_ui()
    ui.summary(verified=["symlinks present"], problems=[])
    text = out.getvalue()
    assert "[ok] symlinks present" in text
    assert "everything checks out" in text


def test_summary_unions_problems_and_warnings_without_double_recording() -> None:
    """The summary lists problems plus collected warnings, and never re-records them."""
    ui, out, _ = _plain_ui()
    ui.warn("a flaky step")
    ui.summary(verified=[], problems=["firewall off"])
    text = out.getvalue()
    assert "[!!] firewall off" in text
    assert "[!!] a flaky step" in text
    # The ledger still holds exactly the one runtime warning, not the summary reprints.
    assert ui.warnings == ["a flaky step"]
