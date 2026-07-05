# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Behavior tests for the login-shell selection helpers.

The invariant: ``write_shell``/``read_shell`` round-trip a choice, ``resolve_shell``
prioritizes an explicit request over the persisted file over the fish default, and
``select_shell`` (the phase body) persists whatever it resolves.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    import pytest

from dotfiles_install import shell_select
from dotfiles_install.context import InstallContext
from dotfiles_install.shell_select import (
    DEFAULT_SHELL,
    VALID_SHELLS,
    read_shell,
    resolve_shell,
    select_shell,
    shell_file,
    write_shell,
)
from dotfiles_install.ui import UI

if TYPE_CHECKING:
    from pathlib import Path


def _ctx(*, shell: str | None = None) -> tuple[InstallContext, io.StringIO]:
    """Build an install context over an in-memory console, so ui.ok() output is assertable."""
    out = io.StringIO()
    ui = UI(stdout=Console(file=out, width=200), stderr=Console(file=io.StringIO(), width=200))
    return InstallContext(ui=ui, shell=shell), out


def test_valid_shells_are_fish_and_zsh() -> None:
    """Exactly fish and zsh are recognized; fish is the default."""
    assert {"fish", "zsh"} == VALID_SHELLS
    assert DEFAULT_SHELL == "fish"


def test_write_then_read_roundtrips_the_choice(tmp_path: Path) -> None:
    """The shell written is the shell read back."""
    write_shell(tmp_path, "zsh")
    assert read_shell(tmp_path) == "zsh"


def test_read_rejects_a_corrupted_persisted_value(tmp_path: Path) -> None:
    """A persisted value outside VALID_SHELLS reads as None (falls back to fish).

    Not passed through verbatim — corruption/a hand-edit typo must not flow into a
    downstream chsh/commands.which call.
    """
    path = shell_file(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("bash\n", encoding="utf-8")
    assert read_shell(tmp_path) is None
    assert resolve_shell(None, tmp_path) == DEFAULT_SHELL


def test_read_missing_file_yields_none(tmp_path: Path) -> None:
    """No persisted file (a fresh machine) reads as None, not an error."""
    assert read_shell(tmp_path) is None


def test_read_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    """A hand-edited file's comments and blank lines are skipped."""
    path = shell_file(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("# a comment\n\nzsh\n", encoding="utf-8")
    assert read_shell(tmp_path) == "zsh"


def test_written_file_documents_how_to_change_it(tmp_path: Path) -> None:
    """The written file explains itself (a hand-editor knows what the file is for)."""
    write_shell(tmp_path, "fish")
    text = shell_file(tmp_path).read_text(encoding="utf-8")
    assert "--shell" in text
    assert "fish" in text.splitlines()[-1]  # the bare choice is the last line


def test_resolve_prefers_the_explicit_request(tmp_path: Path) -> None:
    """An explicit --shell value wins over a persisted choice."""
    write_shell(tmp_path, "fish")
    assert resolve_shell("zsh", tmp_path) == "zsh"


def test_resolve_falls_back_to_the_persisted_choice(tmp_path: Path) -> None:
    """With no explicit request, a persisted choice from a prior run is repeated."""
    write_shell(tmp_path, "zsh")
    assert resolve_shell(None, tmp_path) == "zsh"


def test_resolve_defaults_to_fish_on_a_fresh_machine(tmp_path: Path) -> None:
    """With no request and nothing persisted, fish remains the default."""
    assert resolve_shell(None, tmp_path) == "fish"


def test_select_shell_persists_the_resolved_choice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The phase body writes whatever it resolves, so later phases can re-read it."""
    monkeypatch.setattr(shell_select.Path, "home", lambda: tmp_path)
    ctx, _out = _ctx(shell="zsh")  # noqa: S604 -- our shell= field, not subprocess's

    select_shell(ctx)

    assert read_shell(tmp_path) == "zsh"


def test_select_shell_reports_the_default_distinctly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Choosing the fish default is reported as such, distinct from an explicit zsh pick."""
    monkeypatch.setattr(shell_select.Path, "home", lambda: tmp_path)
    ctx, out = _ctx()

    select_shell(ctx)

    assert "login shell: fish (default)" in out.getvalue()
