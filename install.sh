#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Bootstrap a machine from this dotfiles repo.
#
# This is a thin shim. All install logic lives in the Python package under
# src/dotfiles_install/ (the `dotfiles-install` console script); this file only
# bootstraps uv — the single dependency needed to launch it — and hands off.
# Everything else (Homebrew, fish, stow, macOS defaults, the Dock, verification)
# is a phase inside the installer. Idempotent — safe to re-run. Run from anywhere:
#
#   ~/dotfiles/install.sh [--core] [--bundle NAME ...] [--no-bundles] [--keep-bundles]
#
# Pass --help to see the full flag surface (handled by the Python installer).
#
set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Supported platforms only — fail fast before fetching anything. macOS is fully
# supported; Linux/WSL2 run the OS-agnostic phases (stow, fish, atuin, the Claude/uv
# steps) — the package, privileged, and system-tweak phases are macOS-gated, with
# Linux ports tracked under issue #34. The installer re-checks per phase via
# os_detect; this guard just rejects platforms it can't target (e.g. Windows, BSD)
# before bootstrapping uv. WSL2 reports `Linux` to uname, so it passes here.
case "$(uname)" in
Darwin | Linux) ;;
*)
  printf 'install.sh supports macOS and Linux/WSL2 only (detected %s). Aborting.\n' "$(uname)" >&2
  exit 1
  ;;
esac

# Bootstrap uv if missing — the only thing needed to launch the installer. uv then
# provides the managed Python (>=3.14) and builds the dotfiles-install entry point.
# The installer's phase 0 re-checks uv (a no-op here) and installs Homebrew; this
# shim just gets us far enough to hand off. Capture-then-run so a failed download
# fails loudly instead of silently no-opping a piped shell.
if ! command -v uv >/dev/null 2>&1; then
  printf 'Installing uv...\n'
  # Test curl's status in the `if` condition (exempt from `set -e`): a bare
  # `uv_script="$(curl ...)"` would let errexit abort the script on a network/HTTP failure
  # BEFORE the guard could print a useful message. A non-zero exit OR an empty body is a failure.
  if ! uv_script="$(curl -LsSf https://astral.sh/uv/install.sh)" || [ -z "$uv_script" ]; then
    printf 'uv install failed (download error); check your network and re-run.\n' >&2
    exit 1
  fi
  printf '%s\n' "$uv_script" | sh
  # uv installs to ~/.local/bin (newer) or ~/.cargo/bin (older); cover both.
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || {
  printf 'uv install failed; install uv (https://docs.astral.sh/uv/) and re-run.\n' >&2
  exit 1
}

# Hand off to the real installer. --no-dev keeps the end-user install lean (only the
# runtime deps + the package, not the pytest/playwright/ruff/ty dev toolchain). exec
# so signals and the exit code pass straight through.
exec uv run --no-dev --project "$DOTFILES" dotfiles-install "$@"
