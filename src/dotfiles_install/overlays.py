# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Phase 4: seed the untracked machine-local overlay files.

The tracked config ``[include]``s / sources these per-machine files (work vs personal vs
homelab). Each is created — with a commented, self-documenting template — only when absent, so
the includes never dangle and existing content is never clobbered. The seeded files are
untracked and live outside the repo, so they carry no SPDX header (only this module does).

Finally, commit signing degrades gracefully: on a machine without 1Password's ``op-ssh-sign``,
``commit.gpgsign=false`` is written into ``~/.gitconfig_local`` (unless already set) so commits
still work — the overlay's ``[include]`` sits after the baseline's ``commit.gpgsign=true``.

Ported from ``install.sh`` phase 4 (the "Machine-local overlay files" block).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from dotfiles_install import commands

if TYPE_CHECKING:
    from dotfiles_install.context import InstallContext

# The 1Password commit signer; its absence triggers the gpgsign fallback. A module constant so
# tests can repoint it at a tmp path.
_OP_SSH_SIGN = Path("/Applications/1Password.app/Contents/MacOS/op-ssh-sign")

_SSH_CONFIG_LOCAL = """\
# Machine-local SSH config (untracked). Included by ~/.ssh/config.
# Example:
#   Host myserver
#       HostName 10.0.0.5
#       User me
"""

_GITCONFIG_LOCAL = """\
# Machine-local git config (untracked). Included LAST by ~/.gitconfig, so anything
# here overrides the tracked baseline.
#
# Set your git identity here — it is intentionally NOT in the public repo. Without
# it `git commit` fails with "Please tell me who you are":
#   [user]
#       name = Your Name
#       email = you@example.com
#       signingkey = ssh-ed25519 AAAA...   # your SSH signing key (if you sign)
#
# Good home for a per-directory work identity, too:
#   [includeIf "gitdir:~/work/"]
#       path = ~/.gitconfig.work   # work email, signing key, etc. — untracked
#
# Commit signing: the tracked ~/.gitconfig signs commits with 1Password's
# op-ssh-sign. On a machine WITHOUT 1Password, install.sh disables signing here
# automatically (adds commit.gpgsign=false below) so commits still work — the
# [include] of this file sits after commit.gpgsign=true in the tracked config, so
# this wins. To sign with a different tool instead, set your own program + key:
#   [gpg "ssh"]
#       program = /opt/homebrew/bin/ssh-keygen   # or a work signer
#   [user]
#       signingkey = ~/.ssh/id_ed25519.pub
#   [commit]
#       gpgsign = true
"""

_LOCAL_FISH = """\
# Machine-local fish config (untracked). Sourced last by conf.d/zzz-local.fish.
# Example:
#   set -gx SOME_API_TOKEN ...
#   alias work-vpn 'sudo openconnect ...'
"""

_BREWFILE_LOCAL = """\
# Machine-private Homebrew additions (untracked — never committed). Same Ruby DSL
# as the repo Brewfile; loaded automatically by install.sh. For work-only or
# sensitive software the public repo shouldn't carry.
# Example:
#   cask "company-vpn"
#   brew "internal-cli-tool"
"""

_CLAUDE_LOCAL_MD = """\
<!-- Machine-local Claude Code instructions (untracked). Imported by the tracked
     ~/.claude/CLAUDE.md via `@~/.config/dotfiles/CLAUDE.local.md`. Put work-vs-personal
     guidance here that shouldn't live in the public repo. Markdown, same format as
     CLAUDE.md. Example:

       ## Work
       - Internal package registry: https://nexus.corp.example/...
       - Never push to the public mirror from a work checkout.
-->
"""

_EMPTY_JSON = "{}\n"

_CLAUDE_HOOKS_README = """\
# Machine-local Claude Code hook scripts (untracked)

Put per-machine hook scripts here and reference them by absolute path from the
`hooks` block of `~/.config/dotfiles/claude_settings.local.json`. install.sh
merges that overlay's `hooks` into the generated `~/.claude/settings.json`
alongside any shared hooks from the tracked `claude_settings.json` baseline.

Keep work-vs-personal hooks here so they never reach the public repo. Shared
hooks that should apply on every machine belong in the baseline (and their
scripts under `home/.claude/hooks/`).
"""

_MACOS_LOCAL_SH = """\
# Machine-local macOS defaults (untracked). Sourced by macos.sh before it restarts
# Finder/Dock. Use the same `defaults write` calls as macos.sh; prefer the `dwrite`
# wrapper so a write blocked by an MDM profile warns and keeps going instead of
# aborting. Example:
#   dwrite com.apple.dock tilesize -int 64
"""


def seed_overlays(ctx: InstallContext) -> None:
    """Seed every machine-local overlay (if absent), then apply the commit-signing fallback."""
    home = Path.home()
    config = home / ".config" / "dotfiles"

    ssh_local = home / ".ssh" / "config.local"
    _seed_if_absent(ctx, ssh_local, _SSH_CONFIG_LOCAL)
    # ssh ignores a group/world-readable include file, so enforce 0600 every run (not just on
    # create), mirroring the unconditional `chmod 600` in the bash original.
    ssh_local.chmod(0o600)

    gitconfig_local = home / ".gitconfig_local"
    _seed_if_absent(ctx, gitconfig_local, _GITCONFIG_LOCAL)
    _seed_if_absent(ctx, config / "local.fish", _LOCAL_FISH)
    _seed_if_absent(ctx, config / "Brewfile.local", _BREWFILE_LOCAL)
    _seed_if_absent(ctx, config / "CLAUDE.local.md", _CLAUDE_LOCAL_MD)
    _seed_if_absent(ctx, config / "claude_mcp.local.json", _EMPTY_JSON)
    _seed_if_absent(ctx, config / "claude_settings.local.json", _EMPTY_JSON)
    _seed_if_absent(ctx, config / "claude-hooks.local" / "README.md", _CLAUDE_HOOKS_README)
    _seed_if_absent(ctx, config / "macos.local.sh", _MACOS_LOCAL_SH)

    _disable_signing_without_1password(ctx, gitconfig_local)
    ctx.ui.ok("overlay files ready")


def _seed_if_absent(ctx: InstallContext, path: Path, content: str) -> None:
    """Create ``path`` (with parents) from ``content`` only when it isn't already a file."""
    if path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    ctx.ui.active(f"created {path}")


def _disable_signing_without_1password(ctx: InstallContext, gitconfig_local: Path) -> None:
    """Disable commit signing in the overlay when ``op-ssh-sign`` is absent and unset."""
    if os.access(_OP_SSH_SIGN, os.X_OK):
        return
    existing = commands.run(
        ["git", "config", "--file", str(gitconfig_local), "--get", "commit.gpgsign"],
        capture=True,
    )
    if existing.returncode == 0 and existing.stdout.strip():
        ctx.ui.detail(
            "1Password not found, but commit.gpgsign is already set in ~/.gitconfig_local "
            "— leaving it as-is",
        )
        return
    commands.run(["git", "config", "--file", str(gitconfig_local), "commit.gpgsign", "false"])
    ctx.ui.warn(
        "1Password not found — disabled commit signing in ~/.gitconfig_local "
        "(set commit.gpgsign yourself to re-enable).",
    )
