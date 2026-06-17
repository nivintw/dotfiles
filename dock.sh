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

[ "$(uname)" = "Darwin" ] || { echo "dock.sh is macOS-only; skipping." >&2; exit 0; }
command -v dockutil >/dev/null 2>&1 || {
  echo "dockutil not found — install it via the Brewfile, then re-run." >&2
  exit 0
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
