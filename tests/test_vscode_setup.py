# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for phase 17: VS Code user-settings generation (baseline ⊕ overlay).

Behaviors under test:
  1. Happy path: baseline + no overlay + no live, rg absent -> output == baseline, overlay == {}.
  2. rg found on PATH -> folded into the overlay AND present in the merged output.
  3. rg absent -> no ripgrep key anywhere (the baseline never carries it either).
  4. A hand-edited overlay value for the ripgrep key is a seed, not an overwrite — it survives
     a differing auto-detected ``rg``.
  5. ``_ripgrep_overlay_addition`` itself: the rg-resolution helper, in isolation (found and
     absent-with-a-warning).
"""

from __future__ import annotations

import io
import json
from typing import TYPE_CHECKING

from rich.console import Console

from dotfiles_install import commands, vscode_setup
from dotfiles_install.context import InstallContext
from dotfiles_install.ui import UI

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_RIPGREP_KEY = "todo-tree.ripgrep.ripgrep"


def _which_rg(path: str) -> object:
    """A ``commands.which`` stub reporting ``path`` for "rg" and nothing else."""
    return lambda name: path if name == "rg" else None


def _ctx() -> tuple[InstallContext, io.StringIO]:
    """Build an install context over a wide in-memory console (wide so lines don't wrap)."""
    out = io.StringIO()
    ui = UI(stdout=Console(file=out, width=200), stderr=Console(file=io.StringIO(), width=200))
    return InstallContext(ui=ui), out


def _setup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, baseline: dict) -> None:
    """Wire DOTFILES/HOME and a default no-rg ``commands.which``; write the baseline file."""
    tmp_repo = tmp_path / "repo"
    tmp_repo.mkdir()
    (tmp_repo / "vscode_settings.json").write_text(json.dumps(baseline), encoding="utf-8")
    monkeypatch.setattr(vscode_setup, "DOTFILES", tmp_repo)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(commands, "which", lambda _name: None)


def _output_path(tmp_path: Path) -> Path:
    return tmp_path / "home" / "Library/Application Support/Code/User/settings.json"


def _overlay_path(tmp_path: Path) -> Path:
    return tmp_path / "home" / ".config" / "dotfiles" / "vscode_settings.local.json"


def test_vscode_settings_happy_path_matches_baseline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """No rg on PATH, no overlay, no live: output == baseline, overlay stays empty."""
    baseline = {"editor.fontSize": 13}
    _setup(monkeypatch, tmp_path, baseline=baseline)
    ctx, out = _ctx()

    vscode_setup.write_vscode_settings(ctx)

    assert json.loads(_output_path(tmp_path).read_text()) == baseline
    assert json.loads(_overlay_path(tmp_path).read_text()) == {}
    assert "VS Code settings written" in out.getvalue()


def test_vscode_settings_seeds_ripgrep_path_when_rg_found(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Rg on PATH is folded into the overlay and shows up in the merged output."""
    _setup(monkeypatch, tmp_path, baseline={"editor.fontSize": 13})
    rg_path = "/opt/homebrew/bin/rg"
    monkeypatch.setattr(commands, "which", lambda name: rg_path if name == "rg" else None)
    ctx, _out = _ctx()

    vscode_setup.write_vscode_settings(ctx)

    overlay = json.loads(_overlay_path(tmp_path).read_text())
    assert overlay[_RIPGREP_KEY] == rg_path
    output = json.loads(_output_path(tmp_path).read_text())
    assert output[_RIPGREP_KEY] == rg_path


def test_vscode_settings_no_ripgrep_key_when_rg_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """No rg on PATH: the key is absent everywhere (the baseline never carries it either)."""
    _setup(monkeypatch, tmp_path, baseline={"editor.fontSize": 13})
    ctx, _out = _ctx()

    vscode_setup.write_vscode_settings(ctx)

    output = json.loads(_output_path(tmp_path).read_text())
    assert _RIPGREP_KEY not in output


def test_vscode_settings_seeds_but_never_overwrites_a_hand_edited_overlay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A pre-existing overlay value for the ripgrep key survives a differing auto-detected rg."""
    _setup(monkeypatch, tmp_path, baseline={"editor.fontSize": 13})
    monkeypatch.setattr(commands, "which", _which_rg("/opt/homebrew/bin/rg"))
    overlay_path = _overlay_path(tmp_path)
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    overlay_path.write_text(json.dumps({_RIPGREP_KEY: "/custom/rg"}), encoding="utf-8")
    ctx, _out = _ctx()

    vscode_setup.write_vscode_settings(ctx)

    overlay = json.loads(overlay_path.read_text())
    assert overlay[_RIPGREP_KEY] == "/custom/rg"
    output = json.loads(_output_path(tmp_path).read_text())
    assert output[_RIPGREP_KEY] == "/custom/rg"


def test_ripgrep_overlay_addition_returns_key_when_rg_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pure helper resolves rg's path with no file I/O of its own."""
    monkeypatch.setattr(commands, "which", _which_rg("/usr/local/bin/rg"))
    ctx, _out = _ctx()

    assert vscode_setup._ripgrep_overlay_addition(ctx) == {_RIPGREP_KEY: "/usr/local/bin/rg"}


def test_ripgrep_overlay_addition_warns_and_empty_when_rg_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No rg on PATH: nothing to add, and the installer warns why todo-tree will misbehave."""
    monkeypatch.setattr(commands, "which", lambda _name: None)
    ctx, out = _ctx()

    assert vscode_setup._ripgrep_overlay_addition(ctx) == {}
    assert "rg not found on PATH" in out.getvalue()
