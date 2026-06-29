# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for phase 4 (seed machine-local overlay files) and the commit-signing fallback.

The behaviors that matter: seed_overlays creates all nine overlay files when absent, each
emitting active("created ...") and ending with a trailing newline; the two JSON overlays
parse as exactly {}; files already on disk are never overwritten and emit no "created" message;
~/.ssh/config.local is unconditionally chmod 0600 (even when pre-existing at 0644); parent
directories are created as needed; _disable_signing_without_1password writes
commit.gpgsign=false when op-ssh-sign is absent and the value is unset, emits a detail and
skips the write when the value is already set, and is entirely bypassed when op-ssh-sign is
executable; seed_overlays finishes with ok("overlay files ready").

File-creation tests repoint _OP_SSH_SIGN at a +x temp file so the git fallback is skipped
cleanly. Signing tests monkeypatch commands.run to control what the git config probe returns.
"""

from __future__ import annotations

import io
import json
import stat
import subprocess
from types import SimpleNamespace
from typing import TYPE_CHECKING

from rich.console import Console

from dotfiles_install import commands, overlays
from dotfiles_install.context import InstallContext
from dotfiles_install.ui import UI

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import pytest


def _ctx() -> tuple[InstallContext, io.StringIO]:
    """Build an install context over a wide in-memory console (wide so lines don't wrap)."""
    out = io.StringIO()
    ui = UI(stdout=Console(file=out, width=200), stderr=Console(file=io.StringIO(), width=200))
    return InstallContext(ui=ui), out


def _make_op_executable(tmp_path: Path) -> Path:
    """Return a +x file under tmp_path standing in for op-ssh-sign (skips signing fallback)."""
    fake_op = tmp_path / "op-ssh-sign"
    fake_op.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_op.chmod(0o755)
    return fake_op


_SSH_CONFIG_MODE = 0o600  # required by ssh(1): group/world-readable includes are ignored

_NINE_PATHS = [
    ".ssh/config.local",
    ".gitconfig_local",
    ".config/dotfiles/local.fish",
    ".config/dotfiles/Brewfile.local",
    ".config/dotfiles/CLAUDE.local.md",
    ".config/dotfiles/claude_mcp.local.json",
    ".config/dotfiles/claude_settings.local.json",
    ".config/dotfiles/claude-hooks.local/README.md",
    ".config/dotfiles/macos.local.sh",
]


def _git_config_fake(
    calls: list[SimpleNamespace],
    *,
    get_rc: int = 1,
    get_stdout: str = "",
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Build a commands.run replacement for signing-fallback tests.

    The ``--get commit.gpgsign`` probe returns ``get_rc`` / ``get_stdout``.
    All other argv (including the ``commit.gpgsign false`` write) return rc 0.
    """

    def run(
        argv: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        argv = list(argv)
        calls.append(SimpleNamespace(argv=argv))
        if argv[-2:] == ["--get", "commit.gpgsign"]:
            return subprocess.CompletedProcess(argv, get_rc, stdout=get_stdout, stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    return run


# --- file-creation tests -----------------------------------------------------------------------


def test_seed_overlays_creates_all_nine_files_on_clean_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A clean $HOME gets all nine overlay files, each with an active('created ...') message."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(overlays, "_OP_SSH_SIGN", _make_op_executable(tmp_path))
    ctx, out = _ctx()

    overlays.seed_overlays(ctx)

    output = out.getvalue()
    for rel in _NINE_PATHS:
        full = tmp_path / rel
        assert full.is_file(), f"missing: {full}"
        assert f"created {full}" in output, f"no 'created' message for {rel}"


def test_seeded_json_overlays_contain_empty_object(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The two JSON overlays parse as exactly {} (not null, not an empty string)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(overlays, "_OP_SSH_SIGN", _make_op_executable(tmp_path))
    ctx, _ = _ctx()

    overlays.seed_overlays(ctx)

    for rel in (
        ".config/dotfiles/claude_mcp.local.json",
        ".config/dotfiles/claude_settings.local.json",
    ):
        content = (tmp_path / rel).read_text(encoding="utf-8")
        assert json.loads(content) == {}, f"{rel} did not parse as an empty object"


def test_seeded_files_all_end_with_trailing_newline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Every seeded overlay ends with a trailing newline."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(overlays, "_OP_SSH_SIGN", _make_op_executable(tmp_path))
    ctx, _ = _ctx()

    overlays.seed_overlays(ctx)

    for rel in _NINE_PATHS:
        content = (tmp_path / rel).read_text(encoding="utf-8")
        assert content.endswith("\n"), f"{rel} does not end with a newline"


def test_seed_overlays_is_idempotent_existing_file_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An existing overlay is not overwritten and emits no 'created' message."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(overlays, "_OP_SSH_SIGN", _make_op_executable(tmp_path))

    # Pre-create one overlay with sentinel content that must survive the run.
    pre_existing = tmp_path / ".gitconfig_local"
    pre_existing.parent.mkdir(parents=True, exist_ok=True)
    sentinel = "# my custom content — must survive\n"
    pre_existing.write_text(sentinel, encoding="utf-8")

    ctx, out = _ctx()
    overlays.seed_overlays(ctx)

    assert pre_existing.read_text(encoding="utf-8") == sentinel
    assert f"created {pre_existing}" not in out.getvalue()


def test_ssh_config_local_chmod_0600_is_unconditional(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """~/.ssh/config.local is chmod 0600 even when it already existed with mode 0644."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(overlays, "_OP_SSH_SIGN", _make_op_executable(tmp_path))

    # Pre-create with lax permissions — the post-run mode must still be 0600.
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    ssh_local = ssh_dir / "config.local"
    ssh_local.write_text("# pre-existing\n", encoding="utf-8")
    ssh_local.chmod(0o644)

    ctx, _ = _ctx()
    overlays.seed_overlays(ctx)

    assert stat.S_IMODE(ssh_local.stat().st_mode) == _SSH_CONFIG_MODE


def test_seed_overlays_creates_parent_dirs_for_nested_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Nested parent directories that don't yet exist are created alongside the overlay."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(overlays, "_OP_SSH_SIGN", _make_op_executable(tmp_path))
    ctx, _ = _ctx()

    overlays.seed_overlays(ctx)

    hooks_readme = tmp_path / ".config" / "dotfiles" / "claude-hooks.local" / "README.md"
    assert hooks_readme.is_file()
    assert hooks_readme.parent.is_dir()


def test_seed_overlays_ends_with_ok_overlay_files_ready(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """seed_overlays concludes with ok('overlay files ready')."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(overlays, "_OP_SSH_SIGN", _make_op_executable(tmp_path))
    ctx, out = _ctx()

    overlays.seed_overlays(ctx)

    assert "overlay files ready" in out.getvalue()


# --- commit-signing fallback tests -------------------------------------------------------------


def test_signing_fallback_disables_when_op_absent_and_value_unset(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """With no op-ssh-sign and commit.gpgsign unset, the disable write runs and a warn fires."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Non-existent path → os.access returns False → fallback proceeds.
    monkeypatch.setattr(overlays, "_OP_SSH_SIGN", tmp_path / "no-op-ssh-sign")
    calls: list[SimpleNamespace] = []
    # rc=1 (not set) + empty stdout → must write the disable.
    monkeypatch.setattr(commands, "run", _git_config_fake(calls, get_rc=1, get_stdout=""))
    ctx, _ = _ctx()

    overlays.seed_overlays(ctx)

    gitconfig_local = tmp_path / ".gitconfig_local"
    write_calls = [
        c
        for c in calls
        if c.argv[-2:] == ["commit.gpgsign", "false"] and str(gitconfig_local) in c.argv
    ]
    assert len(write_calls) == 1, f"expected exactly one write, got: {write_calls}"
    assert any("disabled commit signing" in w for w in ctx.ui.warnings)


def test_signing_fallback_skipped_when_value_already_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """With no op-ssh-sign but commit.gpgsign already set, no write and a detail is emitted."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(overlays, "_OP_SSH_SIGN", tmp_path / "no-op-ssh-sign")
    calls: list[SimpleNamespace] = []
    # rc=0 + non-empty stdout → already configured, leave as-is.
    monkeypatch.setattr(commands, "run", _git_config_fake(calls, get_rc=0, get_stdout="true\n"))
    ctx, out = _ctx()

    overlays.seed_overlays(ctx)

    write_calls = [c for c in calls if c.argv[-2:] == ["commit.gpgsign", "false"]]
    assert write_calls == [], f"should not write when value is already set, got: {write_calls}"
    assert "leaving it as-is" in out.getvalue()


def test_signing_fallback_entirely_skipped_when_op_executable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When op-ssh-sign is executable, _disable_signing_without_1password returns immediately."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(overlays, "_OP_SSH_SIGN", _make_op_executable(tmp_path))
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _git_config_fake(calls))
    ctx, _ = _ctx()

    overlays.seed_overlays(ctx)

    git_calls = [c for c in calls if c.argv[:1] == ["git"]]
    assert git_calls == [], f"expected no git calls when op-ssh-sign is present, got: {git_calls}"
