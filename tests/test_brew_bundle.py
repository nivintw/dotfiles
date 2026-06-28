# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for phase 1 (brew bundle).

Covers the bundle-selection precedence that was previously untested shell (``install.sh``'s
six-way if/elif chain), the legacy-selection migration, the ``_brew_bundle`` chokepoint
(tap-trust and the ``--core`` cask strip), and the non-fatal degradation of install failures.
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from dotfiles_install import brew_bundle, commands
from dotfiles_install.bundle_select import parse_bundles
from dotfiles_install.context import InstallContext
from dotfiles_install.ui import UI

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pytest


def _ctx(
    *,
    core: bool = False,
    no_bundles: bool = False,
    keep_bundles: bool = False,
    requested_bundles: tuple[str, ...] = (),
) -> tuple[InstallContext, io.StringIO]:
    """Build an install context (with the given option flags) plus its captured stdout buffer."""
    out = io.StringIO()
    ui = UI(stdout=Console(file=out, width=200), stderr=Console(file=io.StringIO()))
    ctx = InstallContext(
        ui=ui,
        core=core,
        no_bundles=no_bundles,
        keep_bundles=keep_bundles,
        requested_bundles=requested_bundles,
    )
    return ctx, out


def _ok(argv: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
    """A stub command run that always succeeds with empty output."""
    return subprocess.CompletedProcess(list(argv), 0, stdout="")


# --- selection precedence ---------------------------------------------------------------


def test_keep_bundles_reuses_existing_selection_untouched(tmp_path: Path) -> None:
    """``--keep-bundles`` keeps the saved file verbatim and rewrites nothing."""
    sel = tmp_path / "bundles"
    sel.write_text("personal\n")
    ctx, out = _ctx(keep_bundles=True)
    brew_bundle._resolve_selection(ctx, ["personal", "homelab"], sel)
    assert "keeping saved selection" in out.getvalue()
    assert sel.read_text() == "personal\n"


def test_keep_bundles_without_a_saved_file_is_baseline(tmp_path: Path) -> None:
    """``--keep-bundles`` with no saved file means baseline only, and writes no file."""
    sel = tmp_path / "bundles"
    ctx, out = _ctx(keep_bundles=True)
    brew_bundle._resolve_selection(ctx, ["personal"], sel)
    assert "no saved selection" in out.getvalue()
    assert not sel.exists()


def test_no_bundles_persists_an_empty_selection(tmp_path: Path) -> None:
    """``--no-bundles`` writes an explicit baseline-only selection."""
    sel = tmp_path / "bundles"
    ctx, out = _ctx(no_bundles=True)
    brew_bundle._resolve_selection(ctx, ["personal"], sel)
    assert parse_bundles(sel) == []
    assert "baseline only (--no-bundles)" in out.getvalue()


def test_requested_bundles_are_persisted_and_reported(tmp_path: Path) -> None:
    """``--bundle`` values are written authoritatively and listed in the output."""
    sel = tmp_path / "bundles"
    ctx, out = _ctx(requested_bundles=("personal", "homelab"))
    brew_bundle._resolve_selection(ctx, ["personal", "homelab", "work"], sel)
    assert parse_bundles(sel) == ["personal", "homelab"]
    assert "personal, homelab" in out.getvalue()


def test_no_available_bundles_writes_empty_selection(tmp_path: Path) -> None:
    """When no bundles exist, the selection is baseline only."""
    sel = tmp_path / "bundles"
    ctx, out = _ctx()
    brew_bundle._resolve_selection(ctx, [], sel)
    assert parse_bundles(sel) == []
    assert "no bundles found" in out.getvalue()


def test_non_interactive_without_a_selection_seeds_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-interactive with no saved file seeds a baseline-only template."""
    monkeypatch.setattr(brew_bundle, "_is_interactive", lambda: False)
    sel = tmp_path / "bundles"
    ctx, out = _ctx()
    brew_bundle._resolve_selection(ctx, ["personal"], sel)
    assert sel.is_file()
    assert parse_bundles(sel) == []
    assert "non-interactive / no fzf" in out.getvalue()


def test_non_interactive_reuses_an_existing_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-interactive with a saved file reuses it unchanged (idempotent CI re-runs)."""
    monkeypatch.setattr(brew_bundle, "_is_interactive", lambda: False)
    sel = tmp_path / "bundles"
    sel.write_text("homelab\n")
    ctx, out = _ctx()
    brew_bundle._resolve_selection(ctx, ["personal", "homelab"], sel)
    assert "using existing" in out.getvalue()
    assert sel.read_text() == "homelab\n"


def test_interactive_picker_saves_the_chosen_bundles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A confirmed fzf selection (exit 0) is persisted."""
    monkeypatch.setattr(brew_bundle, "_is_interactive", lambda: True)
    monkeypatch.setattr(commands, "which", lambda _name: "/usr/bin/fzf")
    monkeypatch.setattr(
        commands,
        "run",
        lambda argv, **_kw: subprocess.CompletedProcess(list(argv), 0, stdout="homelab\n"),
    )
    sel = tmp_path / "bundles"
    ctx, out = _ctx()
    brew_bundle._resolve_selection(ctx, ["personal", "homelab"], sel)
    assert parse_bundles(sel) == ["homelab"]
    assert "saved selection" in out.getvalue()


def test_interactive_cancel_keeps_the_existing_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cancelled fzf picker (non-zero exit) leaves an existing selection untouched."""
    monkeypatch.setattr(brew_bundle, "_is_interactive", lambda: True)
    monkeypatch.setattr(commands, "which", lambda _name: "/usr/bin/fzf")
    monkeypatch.setattr(
        commands,
        "run",
        lambda argv, **_kw: subprocess.CompletedProcess(list(argv), 130, stdout=""),
    )
    sel = tmp_path / "bundles"
    sel.write_text("personal\n")
    ctx, out = _ctx()
    brew_bundle._resolve_selection(ctx, ["personal", "homelab"], sel)
    assert "selection unchanged" in out.getvalue()
    assert sel.read_text() == "personal\n"


# --- legacy migration -------------------------------------------------------------------


def test_migration_adopts_legacy_file_when_bundles_absent(tmp_path: Path) -> None:
    """A pre-rename ``brewfiles`` file is copied to ``bundles`` when the latter is missing."""
    sel = tmp_path / "bundles"
    sel.with_name("brewfiles").write_text("personal\n")
    ctx, out = _ctx()
    brew_bundle._migrate_legacy_selection(ctx, sel)
    assert sel.read_text() == "personal\n"
    assert "migrated selection" in out.getvalue()


def test_migration_is_a_noop_when_bundles_present(tmp_path: Path) -> None:
    """An existing ``bundles`` file is never overwritten by the legacy one."""
    sel = tmp_path / "bundles"
    sel.write_text("homelab\n")
    sel.with_name("brewfiles").write_text("personal\n")
    ctx, _out = _ctx()
    brew_bundle._migrate_legacy_selection(ctx, sel)
    assert sel.read_text() == "homelab\n"


# --- the _brew_bundle chokepoint --------------------------------------------------------


def test_brew_bundle_non_core_installs_the_file_directly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without ``--core`` the Brewfile is bundled as-is."""
    brewfile = tmp_path / "Brewfile"
    brewfile.write_text('brew "git"\n')
    monkeypatch.setattr(brew_bundle, "_trust_taps", lambda _ctx, _text: None)
    captured: dict[str, object] = {}

    def _run(argv: Sequence[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        captured["argv"] = list(argv)
        return subprocess.CompletedProcess(list(argv), 0)

    monkeypatch.setattr(commands, "run", _run)
    ctx, _out = _ctx(core=False)
    assert brew_bundle._brew_bundle(ctx, brewfile) is True
    assert captured["argv"] == ["brew", "bundle", "install", f"--file={brewfile}"]


def test_brew_bundle_tolerates_non_utf8_brewfile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-UTF-8 byte in a Brewfile does not crash the (designed non-fatal) install."""
    brewfile = tmp_path / "Brewfile"
    # A lone Latin-1 0xe9 byte in a kept comment line — invalid UTF-8.
    brewfile.write_bytes(b'brew "git"  # raw byte \xe9\ncask "firefox"\n')
    monkeypatch.setattr(brew_bundle, "_trust_taps", lambda _ctx, _text: None)
    seen: dict[str, bytes] = {}

    def _run(argv: Sequence[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        bundled = Path(list(argv)[-1].split("=", 1)[1])
        seen["bytes"] = bundled.read_bytes()
        return subprocess.CompletedProcess(list(argv), 0)

    monkeypatch.setattr(commands, "run", _run)
    ctx, _out = _ctx(core=True)
    assert brew_bundle._brew_bundle(ctx, brewfile) is True
    # Cask stripped; the stray 0xe9 byte on the kept line round-tripped faithfully (not crashed).
    assert seen["bytes"] == b'brew "git"  # raw byte \xe9\n'


def test_brew_bundle_core_bundles_a_cask_stripped_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Under ``--core`` the bundled file has the GUI directives stripped out."""
    brewfile = tmp_path / "Brewfile"
    brewfile.write_text('brew "git"\ncask "firefox"\n')
    monkeypatch.setattr(brew_bundle, "_trust_taps", lambda _ctx, _text: None)
    seen: dict[str, str] = {}

    def _run(argv: Sequence[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        bundled = Path(list(argv)[-1].split("=", 1)[1])
        seen["content"] = bundled.read_text()
        return subprocess.CompletedProcess(list(argv), 0)

    monkeypatch.setattr(commands, "run", _run)
    ctx, _out = _ctx(core=True)
    assert brew_bundle._brew_bundle(ctx, brewfile) is True
    assert seen["content"] == 'brew "git"\n'


# --- tap trust --------------------------------------------------------------------------


def test_trust_taps_skips_when_brew_lacks_trust(monkeypatch: pytest.MonkeyPatch) -> None:
    """An older brew without a ``trust`` subcommand short-circuits without touching taps."""
    monkeypatch.setattr(brew_bundle, "_brew_supports_trust", lambda: False)

    def _run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        msg = "no tap commands should run when trust is unsupported"
        raise AssertionError(msg)

    monkeypatch.setattr(commands, "run", _run)
    ctx, _out = _ctx()
    brew_bundle._trust_taps(ctx, 'tap "a/b"\n')  # must not raise


def test_trust_taps_reports_each_trusted_tap(monkeypatch: pytest.MonkeyPatch) -> None:
    """A successfully trusted tap is reported as a detail line."""
    monkeypatch.setattr(brew_bundle, "_brew_supports_trust", lambda: True)
    monkeypatch.setattr(commands, "run", _ok)
    ctx, out = _ctx()
    brew_bundle._trust_taps(ctx, 'tap "a/b"\n')
    assert "trusted tap: a/b" in out.getvalue()


def test_trust_taps_warns_when_a_trust_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed ``brew trust`` warns (non-fatal) rather than aborting."""
    monkeypatch.setattr(brew_bundle, "_brew_supports_trust", lambda: True)

    def _run(argv: Sequence[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        argv = list(argv)
        failed = 1 if argv[:2] == ["brew", "trust"] else 0
        return subprocess.CompletedProcess(argv, failed)

    monkeypatch.setattr(commands, "run", _run)
    ctx, out = _ctx()
    brew_bundle._trust_taps(ctx, 'tap "a/b"\n')
    assert "could not trust tap a/b" in out.getvalue()


# --- install_packages (baseline outcome) ------------------------------------------------


def test_install_packages_reports_baseline_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A clean run reports the baseline installed and (no selection) baseline-only bundles."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(brew_bundle, "_is_interactive", lambda: False)
    monkeypatch.setattr(commands, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(commands, "run", _ok)
    ctx, out = _ctx()
    brew_bundle.install_packages(ctx)
    assert "Homebrew packages installed" in out.getvalue()
    assert "opt-in bundles: baseline only" in out.getvalue()


def test_install_packages_warns_when_baseline_bundle_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed baseline ``brew bundle`` warns and does not abort the phase."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(brew_bundle, "_is_interactive", lambda: False)
    monkeypatch.setattr(brew_bundle, "_trust_taps", lambda _ctx, _text: None)

    def _run(argv: Sequence[str], **_kw: object) -> subprocess.CompletedProcess[str]:
        argv = list(argv)
        failed = 1 if argv[:3] == ["brew", "bundle", "install"] else 0
        return subprocess.CompletedProcess(argv, failed, stdout="")

    monkeypatch.setattr(commands, "run", _run)
    ctx, out = _ctx()
    brew_bundle.install_packages(ctx)
    assert "some baseline Homebrew packages failed" in out.getvalue()
