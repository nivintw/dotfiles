# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Phases 5-11: the post-stow installers.

The cluster of steps that run after stow (phase 3) and after phase 2 drops the sudo ticket, so
the ``curl|bash``-class installers here (fisher, Claude Code) never run with a warm root
timestamp:

* 5  fisher — bootstrap the fish plugin manager, then ``fisher update`` the stowed ``fish_plugins``
* 6  TPM — clone the tmux plugin manager (if missing) and install the stowed plugins
* 7  atuin — backfill pre-existing shell history (only if atuin is installed)
* 8  iTerm2 — point it at the tracked prefs folder
* 9  uv tools — install each line of ``uv_tools.txt`` + the Playwright headless shell
* 10 git clone hook — report the notify-on-clone mode (nothing to install)
* 11 Claude Code CLI — native installer, only when absent (it self-updates after)

Each installer is non-fatal: a network failure warns (replayed in the summary) and the run
continues. Phase 9 and phase 11 put ``~/.local/bin`` on ``PATH`` so the later ``command -v``
checks (and phase 12's ``claude``) find the freshly installed shims.

Ported from ``install.sh`` phases 5-11.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from dotfiles_install import commands
from dotfiles_install.layout import DOTFILES

if TYPE_CHECKING:
    from dotfiles_install.context import InstallContext

_RETRY_ATTEMPTS = 3

# Bootstrap fisher if absent, then reconcile plugins from the stowed fish_plugins. Run inside a
# single `fish -c` so `functions -q fisher` (the idempotency guard) is evaluated by fish itself.
_FISHER_SCRIPT = """\
if not functions -q fisher
  curl -sL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source
  fisher install jorgebucaran/fisher
end
fisher update
"""


def install_fish_plugins(ctx: InstallContext) -> None:
    """Phase 5: bootstrap fisher (if needed) and update the stowed fish plugins."""

    def _install() -> bool:
        return commands.run_ok(["fish", "-c", _FISHER_SCRIPT])

    if commands.retry("fisher (fish plugins)", _RETRY_ATTEMPTS, _install, ui=ctx.ui):
        ctx.ui.ok("fish plugins installed")
    else:
        ctx.ui.warn(
            "fisher bootstrap failed (network?) — fish plugins not installed; "
            "re-run install.sh to retry",
        )


def install_tmux_plugins(ctx: InstallContext) -> None:
    """Phase 6: clone TPM if its entrypoint is missing, then install the stowed plugins."""
    tpm_dir = Path.home() / ".config" / "tmux" / "plugins" / "tpm"
    install_plugins = tpm_dir / "bin" / "install_plugins"

    def _clone() -> bool:
        # rm -rf before each attempt so a retry after a partial clone can't fail on a non-empty
        # target directory.
        shutil.rmtree(tpm_dir, ignore_errors=True)
        return commands.run_ok(
            ["git", "clone", "--depth", "1", "https://github.com/tmux-plugins/tpm", str(tpm_dir)],
        )

    # Key the (re)clone off the actual entrypoint, not just the directory: a partial checkout
    # (dir present, bin/install_plugins missing) must still trigger a reclone.
    if not os.access(install_plugins, os.X_OK):
        ctx.ui.active("installing TPM (tmux plugin manager)")
        if not commands.retry("TPM clone", _RETRY_ATTEMPTS, _clone, ui=ctx.ui):
            ctx.ui.warn(
                "TPM clone failed (network?) — tmux plugins not installed; "
                "re-run install.sh to retry",
            )
    if os.access(install_plugins, os.X_OK):
        commands.run([str(install_plugins)], capture=True)  # output suppressed; never fatal
        ctx.ui.ok("tmux plugins installed")


def import_atuin_history(ctx: InstallContext) -> None:
    """Phase 7: backfill pre-existing shell history into atuin (no-op if atuin isn't installed)."""
    if commands.which("atuin") is None:
        ctx.ui.detail("atuin not installed — skipping shell history import")
        return
    commands.run(["atuin", "import", "auto"], capture=True)  # dedupes; never fatal
    ctx.ui.ok("shell history imported into atuin")


def configure_iterm2(ctx: InstallContext) -> None:
    """Phase 8: point iTerm2 at the repo's tracked preferences folder."""
    iterm_prefs = DOTFILES / "iterm2"
    set_folder = commands.run_ok(
        [
            "defaults",
            "write",
            "com.googlecode.iterm2",
            "PrefsCustomFolder",
            "-string",
            str(iterm_prefs),
        ],
    )
    load_custom = commands.run_ok(
        [
            "defaults",
            "write",
            "com.googlecode.iterm2",
            "LoadPrefsFromCustomFolder",
            "-bool",
            "true",
        ],
    )
    if set_folder and load_custom:
        ctx.ui.ok(f"iTerm2 pointed at tracked preferences ({iterm_prefs})")
    else:
        ctx.ui.warn("couldn't point iTerm2 at the tracked prefs (defaults write failed)")


def install_uv_tools(ctx: InstallContext) -> None:
    """Phase 9: install each ``uv_tools.txt`` tool, then the Playwright headless shell."""
    failures = 0
    for line in (DOTFILES / "uv_tools.txt").read_text(encoding="utf-8").split("\n"):
        # Skip blank lines and comments (matching the bash `'' | \#*` case).
        if line == "" or line.startswith("#"):
            continue
        tokens = line.split()  # a line is a tool name plus optional `--with` args

        def _install(tokens: list[str] = tokens) -> bool:
            return commands.run_ok(["uv", "tool", "install", *tokens])

        if not commands.retry(
            f"uv tool install {' '.join(tokens)}", _RETRY_ATTEMPTS, _install, ui=ctx.ui
        ):
            ctx.ui.warn(
                f"uv tool install failed for: {' '.join(tokens)} (re-run install.sh to retry)"
            )
            failures += 1
    if failures == 0:
        ctx.ui.ok("uv tools installed")
    else:
        ctx.ui.warn(
            f"{failures} uv tool(s) failed to install (see above) — re-run install.sh to retry",
        )

    # uv drops tool shims into ~/.local/bin; put it on PATH so later command -v checks (and the
    # Claude CLI in phase 11) find them even when uv was already present.
    _ensure_local_bin_on_path()

    ctx.ui.active("installing Playwright headless shell (browser for the docs-site tests)")
    if not commands.run_ok(
        [
            "uv",
            "run",
            "--project",
            str(DOTFILES),
            "playwright",
            "install",
            "--only-shell",
            "chromium",
        ],
    ):
        ctx.ui.warn("Playwright headless shell install failed; re-run install.sh to retry.")


def report_clone_hook(ctx: InstallContext) -> None:
    """Phase 10: report the git clone-hook mode (notify-on-clone vs opt-in auto-install)."""
    result = commands.run(
        ["git", "config", "--bool", "--get", "dotfiles.autoInstallHooks"], capture=True
    )
    enabled = result.returncode == 0 and result.stdout.strip() == "true"
    if enabled:
        ctx.ui.ok(
            "fresh clones will auto-install pre-commit hooks (dotfiles.autoInstallHooks=true)"
        )
    else:
        ctx.ui.detail(
            "fresh clones will notify when a repo defines pre-commit hooks; "
            "set dotfiles.autoInstallHooks=true to auto-install",
        )


def install_claude_cli(ctx: InstallContext) -> None:
    """Phase 11: install the Claude Code CLI via its native installer, only when absent."""
    if commands.which("claude") is not None:
        ctx.ui.detail("Claude Code already installed — skipping (it self-updates)")
        return

    def _install() -> bool:
        # Capture-then-run: a failed/empty download is a failed attempt, not a silent no-op.
        script = commands.fetch(["curl", "-fsSL", "https://claude.ai/install.sh"])
        if script is None:
            return False
        return commands.run_ok(["bash"], input_text=script)

    if commands.retry("Claude Code install", _RETRY_ATTEMPTS, _install, ui=ctx.ui):
        _ensure_local_bin_on_path()
        ctx.ui.ok("Claude Code CLI installed")
    else:
        ctx.ui.warn("Claude Code install failed (network?) — skipping; re-run install.sh to retry")


def _ensure_local_bin_on_path() -> None:
    """Prepend ``~/.local/bin`` to ``PATH`` (once) so freshly installed shims resolve."""
    local_bin = str(Path.home() / ".local" / "bin")
    current = os.environ.get("PATH", "")
    if local_bin not in current.split(os.pathsep):
        os.environ["PATH"] = f"{local_bin}{os.pathsep}{current}" if current else local_bin
