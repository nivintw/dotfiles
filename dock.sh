#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Declarative macOS Dock layout via dockutil.
#
#   ~/dotfiles/dock.sh
#
# Idempotent — clears the Dock and rebuilds it from the list below, then
# restarts the Dock. Edit the `apps` array to taste; it was seeded from the
# Dock present when this script was written (Safari, Mail). Missing apps are
# skipped, so it's safe to list apps you haven't installed yet.
set -euo pipefail

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }

# A deliberate no-op bail (not macOS, dockutil missing/broken) exits with this code, distinct
# from 0 (Dock actually rebuilt) — src/dotfiles_install/system_setup.py's caller branches on
# it so a skip can't be misreported as "Dock layout applied".
SKIPPED_EXIT=2

[ "$(uname)" = "Darwin" ] || {
  echo "dock.sh is macOS-only; skipping." >&2
  exit "$SKIPPED_EXIT"
}
command -v dockutil >/dev/null 2>&1 || {
  echo "dockutil not found — install it via the Brewfile, then re-run." >&2
  exit "$SKIPPED_EXIT"
}

# Read-only preflight: if dockutil can't even list the current Dock, its state is
# indeterminate (corrupted plist, incompatible version, no Dock session). Bail out BEFORE
# any destructive call — this only guards the "can't read state at all" case; it doesn't
# make the rebuild atomic, so a failure between `--remove all` and the last `--add` below
# can still leave the Dock partially rebuilt (a pre-existing gap, not introduced here).
dockutil --list >/dev/null 2>&1 || {
  echo "dockutil can't read the current Dock state (indeterminate) — leaving the Dock untouched." >&2
  exit "$SKIPPED_EXIT"
}

# Dock apps, left to right. Uncomment / add the ones you want.
apps=(
  "/Applications/Safari.app"
  "/System/Applications/Mail.app"
  # --- apps you have installed; uncomment to pin ---
  # "/Applications/iTerm.app"
  # "/Applications/Visual Studio Code.app"
  # "/Applications/Obsidian.app"
  # "/Applications/Firefox.app"
  # "/Applications/Google Chrome.app"
  # "/Applications/1Password.app"
  # "/Applications/Discord.app"
)

log "Rebuilding the Dock (removes ALL current Dock items, then re-pins the list below)"
dockutil --no-restart --remove all >/dev/null

for app in "${apps[@]}"; do
  if [ -e "$app" ]; then
    dockutil --no-restart --add "$app" >/dev/null
    echo "  added: $app"
  else
    echo "  skipping (not installed): $app"
  fi
done

killall Dock >/dev/null 2>&1 || true
log "Dock rebuilt."
