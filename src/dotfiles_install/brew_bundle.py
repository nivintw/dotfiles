# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Phase 1: install Homebrew formulae and casks via ``brew bundle``.

Three things flow through one chokepoint, :func:`_brew_bundle` (trust the file's taps →
optionally strip casks for ``--core`` → ``brew bundle install --file=``): the baseline
``Brewfile``, each opt-in ``Brewfile.d/<name>.brewfile`` bundle the machine selected, and a
machine-private ``Brewfile.local``. Bundle selection is resolved with the same six-way
precedence as the bash installer (``--keep-bundles`` → ``--bundle`` / ``--no-bundles`` → no
bundles available → interactive fzf picker → reuse an existing selection → baseline-only
template). Every install failure here is non-fatal: it warns (and the warning is replayed in
the closing summary) and the run continues.

Ported from ``install.sh`` phase 1 (the "Homebrew formulae + casks" block). The pre-bundle
Touch-ID-for-sudo enable is a privileged PAM write owned by the phase-2 block (#68); see
:func:`_enable_touch_id_pre_bundle`.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from dotfiles_install import commands
from dotfiles_install.brewfile import brewfile_core, brewfile_taps
from dotfiles_install.bundle_select import fzf_preselect_bind, parse_bundles, write_bundles
from dotfiles_install.layout import BUNDLES_DIR, DOTFILES, discover_bundles

if TYPE_CHECKING:
    from dotfiles_install.context import InstallContext

_BREWFILE = DOTFILES / "Brewfile"


# Home-based paths are resolved lazily (not module constants) so they honor ``$HOME`` at call
# time — which keeps them correct in a long-lived process and redirectable in tests.
def _config_dir() -> Path:
    """Return the machine-private dotfiles config dir (``~/.config/dotfiles``)."""
    return Path.home() / ".config" / "dotfiles"


def _selection_file() -> Path:
    """Return the opt-in bundle selection file (``~/.config/dotfiles/bundles``)."""
    return _config_dir() / "bundles"


def _brewfile_local() -> Path:
    """Return the machine-private ``Brewfile.local`` path (``~/.config/dotfiles``)."""
    return _config_dir() / "Brewfile.local"


def install_packages(ctx: InstallContext) -> None:
    """Run the baseline bundle, the selected opt-in bundles, and any ``Brewfile.local``."""
    _enable_touch_id_pre_bundle()
    if _brew_bundle(ctx, _BREWFILE):
        ctx.ui.ok("Homebrew packages installed")
    else:
        ctx.ui.warn(
            "some baseline Homebrew packages failed to install — re-run install.sh to retry",
        )
    _install_opt_in_bundles(ctx)
    _install_brewfile_local(ctx)


def _enable_touch_id_pre_bundle() -> None:
    """Call site for the pre-bundle Touch-ID-for-sudo enable — implementation owned by #68.

    ``install.sh`` enables Touch ID for sudo *before* ``brew bundle`` so that a cask's ``.pkg``
    password prompt becomes a fingerprint tap. That enable is a privileged PAM write, so it
    lands with the phase-2 privileged block (#68); this hook marks the ordering without pulling
    sudo into this slice. The bash installer performs the real enable until the cutover (#72),
    so this is intentionally a no-op for now.
    """


def _brew_bundle(ctx: InstallContext, brewfile: Path) -> bool:
    """Trust the file's taps, then ``brew bundle install`` it (a cask-stripped copy under --core).

    Returns whether the bundle install succeeded. The single chokepoint shared by the baseline
    Brewfile, each opt-in bundle, and ``Brewfile.local``.
    """
    # surrogateescape, not strict: the bash original is byte-oriented (sed/grep) and never
    # decodes, so a stray non-UTF-8 byte in a hand-edited Brewfile must not crash the (designed
    # non-fatal) install — and round-trips faithfully back to the temp file under --core.
    text = brewfile.read_text(encoding="utf-8", errors="surrogateescape")
    _trust_taps(ctx, text)
    if not ctx.core:
        return _bundle_install(brewfile)
    return _bundle_install_core(brewfile_core(text))


def _bundle_install(brewfile: Path) -> bool:
    """Run ``brew bundle install --file=<brewfile>`` and report success."""
    return commands.run_ok(["brew", "bundle", "install", f"--file={brewfile}"])


def _bundle_install_core(core_text: str) -> bool:
    """Write the cask-stripped Brewfile to a temp file, bundle it, and clean up."""
    with tempfile.NamedTemporaryFile(
        "w",
        prefix="brewfile-core",
        delete=False,
        encoding="utf-8",
        errors="surrogateescape",  # faithfully round-trip any non-UTF-8 bytes read above
    ) as handle:
        handle.write(core_text)
        temp = Path(handle.name)
    try:
        return _bundle_install(temp)
    finally:
        temp.unlink(missing_ok=True)


def _trust_taps(ctx: InstallContext, brewfile_text: str) -> None:
    """Trust each third-party tap the Brewfile declares (a failed trust warns, non-fatal)."""
    if not _brew_supports_trust():
        return
    for tap in brewfile_taps(brewfile_text):
        commands.run(["brew", "tap", tap], capture=True)  # add the tap; non-fatal, quiet
        if commands.run_ok(["brew", "trust", tap]):
            ctx.ui.detail(f"trusted tap: {tap}")
        else:
            ctx.ui.warn(
                f"could not trust tap {tap} — its packages may fail to install "
                f"(retry: brew trust {tap})",
            )


def _brew_supports_trust() -> bool:
    """Report whether this Homebrew has a ``trust`` subcommand (older brews lack it)."""
    result = commands.run(["brew", "commands"], capture=True)
    if result.returncode:
        return False
    return "trust" in result.stdout.split()


def _install_opt_in_bundles(ctx: InstallContext) -> None:
    """Resolve the bundle selection (migrate, persist, or pick), then install what's selected."""
    available = discover_bundles()
    sel = _selection_file()
    sel.parent.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_selection(ctx, sel)
    _resolve_selection(ctx, available, sel)
    _run_selected_bundles(ctx, sel)


def _migrate_legacy_selection(ctx: InstallContext, sel: Path) -> None:
    """Adopt a legacy ``brewfiles`` selection as ``bundles`` once, if ``bundles`` is absent."""
    legacy = sel.with_name("brewfiles")  # the pre-rename sibling of the bundles file
    if not sel.is_file() and legacy.is_file():  # match bash's `-f` (skip non-regular files)
        shutil.copyfile(legacy, sel)
        ctx.ui.detail("migrated selection from legacy ~/.config/dotfiles/brewfiles")


def _resolve_selection(ctx: InstallContext, available: list[str], sel: Path) -> None:
    """Persist or reuse the bundle selection following install.sh's six-way precedence."""
    if ctx.keep_bundles:
        _resolve_keep(ctx, sel)
        return
    if ctx.no_bundles or ctx.requested_bundles:
        _resolve_from_flags(ctx, available, sel)
        return
    if not available:
        write_bundles(sel, available, [])
        ctx.ui.detail("no bundles found in Brewfile.d — baseline only")
        return
    _resolve_interactive_or_reuse(ctx, available, sel)


def _resolve_keep(ctx: InstallContext, sel: Path) -> None:
    """``--keep-bundles``: reuse the saved selection as-is, no picker, no rewrite."""
    if sel.is_file():
        ctx.ui.detail("keeping saved selection (--keep-bundles)")
    else:
        ctx.ui.detail("--keep-bundles: no saved selection — baseline only")


def _resolve_from_flags(ctx: InstallContext, available: list[str], sel: Path) -> None:
    """``--bundle`` / ``--no-bundles``: authoritative, persisted, no prompt."""
    write_bundles(sel, available, list(ctx.requested_bundles))
    if ctx.requested_bundles:
        ctx.ui.detail(f"opt-in bundles: {', '.join(ctx.requested_bundles)}")
    else:
        ctx.ui.detail("baseline only (--no-bundles)")


def _resolve_interactive_or_reuse(ctx: InstallContext, available: list[str], sel: Path) -> None:
    """Pick via fzf when interactive; else reuse an existing selection or seed a baseline file."""
    if _is_interactive() and commands.which("fzf") is not None:
        _run_picker(ctx, available, sel)
        return
    if sel.is_file():
        ctx.ui.detail("non-interactive — using existing ~/.config/dotfiles/bundles")
        return
    ctx.ui.detail(
        "non-interactive / no fzf — baseline only; "
        "pass --bundle NAME or edit ~/.config/dotfiles/bundles",
    )
    write_bundles(sel, available, [])


def _run_picker(ctx: InstallContext, available: list[str], sel: Path) -> None:
    """Run the fzf multi-select picker; ENTER saves the choice, ESC keeps the current selection."""
    ctx.ui.active("select bundles to install (TAB toggles, ENTER confirms, ESC keeps current)")
    preseed = fzf_preselect_bind(available, parse_bundles(sel))
    argv = [
        "fzf",
        "--multi",
        "--height=40%",
        "--reverse",
        "--border",
        "--prompt=bundles> ",
        "--header=opt-in Brewfile bundles — TAB to toggle, ENTER to confirm",
        f"--preview=cat '{BUNDLES_DIR}'/{{}}.brewfile",
        "--preview-window=right,60%",
    ]
    if preseed:
        argv += ["--bind", preseed]
    result = commands.run(argv, input_text="\n".join(available) + "\n", capture=True)
    if result.returncode and sel.is_file():
        ctx.ui.detail("selection unchanged")
        return
    picked = [line for line in result.stdout.splitlines() if line]
    write_bundles(sel, available, picked)
    summary = ", ".join(picked) if picked else "baseline only"
    ctx.ui.detail(f"saved selection to ~/.config/dotfiles/bundles ({summary})")


def _run_selected_bundles(ctx: InstallContext, sel: Path) -> None:
    """Install each selected opt-in bundle; warn (non-fatal) on a missing or failing bundle."""
    installed: list[str] = []
    for bundle in parse_bundles(sel):
        bundle_file = BUNDLES_DIR / f"{bundle}.brewfile"
        if not bundle_file.is_file():
            ctx.ui.warn(f"skipping opt-in bundle '{bundle}' (no {bundle_file})")
            continue
        ctx.ui.active(f"installing opt-in bundle: {bundle}")
        if not _brew_bundle(ctx, bundle_file):
            ctx.ui.warn(
                f"opt-in bundle '{bundle}' had install failures — re-run install.sh to retry",
            )
        installed.append(bundle)
    if installed:
        ctx.ui.ok(f"opt-in bundles: {', '.join(installed)}")
    else:
        ctx.ui.ok("opt-in bundles: baseline only")


def _install_brewfile_local(ctx: InstallContext) -> None:
    """Install the machine-private ``Brewfile.local`` additions if the file is present."""
    brew_local = _brewfile_local()
    if not brew_local.is_file():
        return
    ctx.ui.step("Machine-private Brewfile additions (Brewfile.local)")
    if _brew_bundle(ctx, brew_local):
        ctx.ui.ok("machine-private additions installed")
    else:
        ctx.ui.warn("some Brewfile.local packages failed to install — re-run install.sh to retry")


def _is_interactive() -> bool:
    """Report whether stdin is a TTY (bash ``[ -t 0 ]``) — gates the fzf picker."""
    return sys.stdin.isatty()
