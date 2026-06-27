# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Behavior tests for the pre-stow ~/.gitconfig migration helper.

Ported from ``tests/gitconfig_migrate.bats``. The risks guarded: a real ~/.gitconfig is
backed up (never clobbered) and its contents preserved in the overlay; the migrated text
never re-includes the overlay itself (git would hit "exceeded maximum include depth"); and
a managed machine (symlink) is a strict no-op.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from dotfiles_install.gitconfig_migrate import gitconfig_migrate

if TYPE_CHECKING:
    from pathlib import Path

BASELINE = "[core]\n\tpager = delta\n[include]\n\tpath = ~/.gitconfig_local\n"


def _paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Return (target, overlay, baseline) with the baseline written."""
    baseline = tmp_path / "baseline"
    baseline.write_text(BASELINE)
    return tmp_path / ".gitconfig", tmp_path / ".gitconfig_local", baseline


def test_symlinked_gitconfig_is_noop(tmp_path: Path) -> None:
    """A symlinked ~/.gitconfig (managed machine) is left untouched."""
    target, overlay, baseline = _paths(tmp_path)
    target.symlink_to(baseline)
    assert gitconfig_migrate(target, overlay, baseline) == ""
    assert target.is_symlink()
    assert not overlay.exists()


def test_absent_gitconfig_is_noop(tmp_path: Path) -> None:
    """An absent ~/.gitconfig is a no-op."""
    target, overlay, baseline = _paths(tmp_path)
    assert gitconfig_migrate(target, overlay, baseline) == ""
    assert not overlay.exists()


def test_identical_to_baseline_is_removed_not_backed_up(tmp_path: Path) -> None:
    """A real file byte-identical to the baseline is removed, not backed up."""
    target, overlay, baseline = _paths(tmp_path)
    target.write_text(BASELINE)
    gitconfig_migrate(target, overlay, baseline)
    assert not target.exists()
    assert not (tmp_path / ".gitconfig.pre-stow.bak").exists()
    assert not overlay.exists()


def test_differing_file_is_backed_up_and_migrated(tmp_path: Path) -> None:
    """A differing real file is moved to a backup and its contents folded into the overlay."""
    target, overlay, baseline = _paths(tmp_path)
    target.write_text("[user]\n\temail = me@work.example\n[alias]\n\tco = checkout\n")
    gitconfig_migrate(target, overlay, baseline)
    assert not target.exists()
    assert (tmp_path / ".gitconfig.pre-stow.bak").is_file()
    overlay_text = overlay.read_text()
    assert "me@work.example" in overlay_text
    assert "co = checkout" in overlay_text


def test_existing_backup_is_not_clobbered(tmp_path: Path) -> None:
    """A pre-existing backup is kept; the new one lands beside it, numbered."""
    target, overlay, baseline = _paths(tmp_path)
    (tmp_path / ".gitconfig.pre-stow.bak").write_text("old backup\n")
    target.write_text("[user]\n\temail = me@work.example\n")
    gitconfig_migrate(target, overlay, baseline)
    assert "old backup" in (tmp_path / ".gitconfig.pre-stow.bak").read_text()
    assert "me@work.example" in (tmp_path / ".gitconfig.pre-stow.bak.1").read_text()


def test_self_include_is_stripped(tmp_path: Path) -> None:
    """A migrated [include] of the overlay itself is stripped (no include loop)."""
    target, overlay, baseline = _paths(tmp_path)
    target.write_text(
        "[user]\n\temail = me@work.example\n[include]\n\tpath = ~/.gitconfig_local\n",
    )
    gitconfig_migrate(target, overlay, baseline)
    overlay_text = overlay.read_text()
    assert "me@work.example" in overlay_text
    assert "gitconfig_local" not in overlay_text


def test_self_include_stripped_regardless_of_casing(tmp_path: Path) -> None:
    """The self-include is stripped regardless of section/key casing."""
    target, overlay, baseline = _paths(tmp_path)
    target.write_text(
        "[user]\n\temail = me@work.example\n[Include]\n\tPath = ~/.gitconfig_local\n",
    )
    gitconfig_migrate(target, overlay, baseline)
    overlay_text = overlay.read_text()
    assert "me@work.example" in overlay_text
    assert "gitconfig_local" not in overlay_text.lower()


def test_self_include_with_quoted_path_stripped(tmp_path: Path) -> None:
    """A self-include with a quoted path is stripped."""
    target, overlay, baseline = _paths(tmp_path)
    target.write_text(
        '[user]\n\temail = me@work.example\n[include]\n\tpath = "~/.gitconfig_local"\n',
    )
    gitconfig_migrate(target, overlay, baseline)
    overlay_text = overlay.read_text()
    assert "me@work.example" in overlay_text
    assert "gitconfig_local" not in overlay_text


def test_self_include_with_inline_comment_stripped(tmp_path: Path) -> None:
    """A self-include with an inline comment on the path is stripped."""
    target, overlay, baseline = _paths(tmp_path)
    target.write_text(
        "[user]\n\temail = me@work.example\n[include]\n\tpath = ~/.gitconfig_local # local\n",
    )
    gitconfig_migrate(target, overlay, baseline)
    overlay_text = overlay.read_text()
    assert "me@work.example" in overlay_text
    assert "gitconfig_local" not in overlay_text


def test_foreign_includeif_is_preserved(tmp_path: Path) -> None:
    """A foreign includeIf pointing elsewhere is preserved."""
    target, overlay, baseline = _paths(tmp_path)
    target.write_text('[includeIf "gitdir:~/work/"]\n\tpath = ~/.gitconfig.work\n')
    gitconfig_migrate(target, overlay, baseline)
    overlay_text = overlay.read_text()
    assert "gitdir:~/work/" in overlay_text
    assert "gitconfig.work" in overlay_text


def test_appends_to_existing_overlay(tmp_path: Path) -> None:
    """Migration appends to an existing overlay without dropping its content."""
    target, overlay, baseline = _paths(tmp_path)
    overlay.write_text("# seeded\n[commit]\n\tgpgsign = false\n")
    target.write_text("[user]\n\temail = me@work.example\n")
    gitconfig_migrate(target, overlay, baseline)
    overlay_text = overlay.read_text()
    assert "gpgsign = false" in overlay_text
    assert "me@work.example" in overlay_text


def test_unwritable_overlay_fails_and_leaves_original(tmp_path: Path) -> None:
    """An unwritable overlay aborts with the original ~/.gitconfig untouched (no data loss)."""
    if os.geteuid() == 0:
        pytest.skip("root bypasses file permissions")
    target, overlay, baseline = _paths(tmp_path)
    target.write_text("[user]\n\temail = me@work.example\n")
    overlay.write_text("")
    overlay.chmod(0o000)
    try:
        with pytest.raises(OSError):  # noqa: PT011
            gitconfig_migrate(target, overlay, baseline)
    finally:
        overlay.chmod(0o644)
    assert target.is_file()
    assert "me@work.example" in target.read_text()
    assert not (tmp_path / ".gitconfig.pre-stow.bak").exists()


def test_non_utf8_gitconfig_round_trips(tmp_path: Path) -> None:
    """A non-UTF-8 ~/.gitconfig migrates without a decode crash, bytes preserved (byte-faithful)."""
    target, overlay, baseline = _paths(tmp_path)
    target.write_bytes(b"[user]\n\tname = \xe9\xe8\xea\n")  # latin-1 accented bytes, invalid UTF-8
    gitconfig_migrate(target, overlay, baseline)
    assert b"\xe9\xe8\xea" in overlay.read_bytes()


def test_crlf_gitconfig_preserves_line_endings(tmp_path: Path) -> None:
    r"""CRLF line endings survive the fold into the overlay (split on \n only, like awk)."""
    target, overlay, baseline = _paths(tmp_path)
    target.write_bytes(b"[user]\r\n\temail = me@work.example\r\n")
    gitconfig_migrate(target, overlay, baseline)
    assert b"\r\n" in overlay.read_bytes()
