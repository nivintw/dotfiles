# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Typer entry point for the dotfiles installer (skeleton).

Reproduces ``install.sh``'s flag surface (``--bundle`` / ``--no-bundles`` / ``--keep-bundles`` /
``--core`` / ``--help``) and its exit codes — 0 on success or help, 2 on a usage error, 1 on a
runtime precondition (non-macOS) — then walks the phase registry. Phases 0-13 and 17 (verify
& summary) execute **real work**; phases 14-16 are stubs that report as not-yet-ported.
``install.sh`` stays the default entry point until the cutover (#72), so running this module
directly today runs only the ported phases for real.
"""

from __future__ import annotations

from typing import Annotated

import typer

from dotfiles_install import commands
from dotfiles_install.context import InstallContext
from dotfiles_install.layout import discover_bundles
from dotfiles_install.os_detect import current_os
from dotfiles_install.phases import phases_for
from dotfiles_install.ui import UI


def _help_epilog() -> str:
    """Build the ``--help`` epilog listing the discovered opt-in bundles."""
    names = discover_bundles()
    listing = "\n".join(f"  {name}" for name in names) if names else "  (none found)"
    return f"Opt-in Brewfile bundles (Brewfile.d/<name>.brewfile):\n{listing}"


app = typer.Typer(add_completion=False, rich_markup_mode=None)


@app.command(epilog=_help_epilog())
def main(
    bundle: Annotated[
        list[str] | None,
        typer.Option("--bundle", help="Opt into a Brewfile bundle and persist it; repeatable."),
    ] = None,
    no_bundles: Annotated[
        bool,
        typer.Option("--no-bundles", help="Baseline only; bypass the bundle picker."),
    ] = False,
    keep_bundles: Annotated[
        bool,
        typer.Option("--keep-bundles", help="Keep the saved selection; skip the picker."),
    ] = False,
    core: Annotated[
        bool,
        typer.Option("--core", help="Core profile: CLI formulae only, skip casks."),
    ] = False,
) -> None:
    """Converge this Mac to the state declared in the repo (dotfiles bootstrap)."""
    # Dedup repeated --bundle values, preserving order (bash's add_requested_bundle).
    requested = tuple(dict.fromkeys(bundle or ()))
    _validate_bundles(requested, no_bundles=no_bundles, keep_bundles=keep_bundles)
    ui = UI()
    ctx = InstallContext(
        ui=ui,
        core=core,
        no_bundles=no_bundles,
        keep_bundles=keep_bundles,
        requested_bundles=requested,
    )
    _run(ctx)


def _validate_bundles(
    requested: tuple[str, ...],
    *,
    no_bundles: bool,
    keep_bundles: bool,
) -> None:
    """Reject mutually exclusive bundle flags and unknown bundle names (exit code 2)."""
    if keep_bundles and (requested or no_bundles):
        msg = "--keep-bundles can't be combined with --bundle/--no-bundles"
        raise typer.BadParameter(msg)
    available = set(discover_bundles())
    for name in requested:
        if name not in available:
            msg = f"unknown bundle: {name!r}"
            raise typer.BadParameter(msg)


def _run(ctx: InstallContext) -> None:
    """Walk the OS-gated phase registry, reporting each not-yet-ported phase as skipped."""
    ui = ctx.ui
    ui.banner("dotfiles bootstrap")
    try:
        target = current_os()
    except RuntimeError as exc:
        ui.err(f"{exc}; the installer targets macOS")
        raise typer.Exit(code=1) from exc
    applicable = phases_for(target)
    if not applicable:
        ui.err(f"no install phases apply to {target.value}; macOS only for now")
        raise typer.Exit(code=1)
    try:
        for phase in applicable:
            ui.step(f"[{phase.number}] {phase.name}")
            if phase.run is not None:
                phase.run(ctx)
            else:
                ui.warn(f"phase '{phase.name}' is not yet ported (skipped)")
    finally:
        # Backstop the sudo ticket drop, mirroring install.sh's global `trap 'sudo -k 2>/dev/null
        # || true' EXIT`. The privileged phase drops the ticket at the end of its own block, but
        # an earlier privileged step (phase 1's pre-bundle Touch-ID enable) also warms one, and an
        # abort (Ctrl-C / unexpected error) could exit before the privileged phase runs. Dropping
        # here ensures no warm passwordless sudo ticket survives the run, whatever happened above.
        # capture=True keeps it silent like the bash trap's 2>/dev/null — this runs unconditionally,
        # even when no ticket was acquired (or the user isn't in sudoers), so sudo's stderr must
        # not leak to the terminal.
        commands.run(["sudo", "-k"], capture=True)
