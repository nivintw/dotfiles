#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Declarative macOS Dock layout via dockutil.
#
#   ~/dotfiles/dock.sh [--check]
#
# Idempotent — when the Dock's pinned apps already match the desired list below it makes NO
# changes and does NOT restart the Dock (no jarring flash); otherwise it rebuilds the Dock
# from the list and restarts it. Edit the `apps` array to taste; it was seeded from the Dock
# present when this script was written (Safari, Mail). Missing apps are skipped, so it's safe
# to list apps you haven't installed yet.
#
#   --check   Report whether the Dock matches the desired layout and exit WITHOUT modifying
#             it (exit 0 = already matches, 1 = drift).
set -euo pipefail

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }

# A deliberate no-op bail (not macOS, dockutil missing/broken) exits with this code, distinct
# from 0 (Dock rebuilt or already correct) — src/dotfiles_install/system_setup.py's caller
# branches on it so a skip can't be misreported as "Dock layout applied".
SKIPPED_EXIT=2
# A usage error (bad/extra argument) exits with EX_USAGE, deliberately DISTINCT from
# SKIPPED_EXIT so system_setup.py can't misread a real invocation mistake as a "Dock skipped".
USAGE_EXIT=64

# Reject unknown flags / extra args with a usage error rather than silently rebuilding — a
# mistyped flag must not trigger a destructive rebuild (and Dock flash) by falling through.
check_only=false
case "${1:-}" in
"") ;;
--check) check_only=true ;;
*)
  echo "usage: dock.sh [--check]  (unknown argument: $1)" >&2
  exit "$USAGE_EXIT"
  ;;
esac
if [ "$#" -gt 1 ]; then
  echo "usage: dock.sh [--check]  (unexpected extra arguments)" >&2
  exit "$USAGE_EXIT"
fi

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
# any destructive call.
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

# The desired pinned apps: the basename of every app in the list above that's actually
# installed (an uninstalled app is skipped, so it's never part of the desired state).
desired_apps() {
  local app
  for app in "${apps[@]}"; do
    [ -e "$app" ] && printf '%s\n' "${app##*/}"
  done
}

# The apps currently pinned in the Dock, one percent-decoded basename per line, in Dock order.
# `dockutil --list` is tab-separated (name<TAB>url<TAB>...); we take the file:// URL, strip it
# to a basename, and percent-decode it. Comparing BASENAMES (not full paths) is what makes this
# robust to macOS cryptex path prefixes — a system app the OS reports under
# /System/Cryptexes/App/... vs /System/Applications/... has the same `Foo.app` basename either
# way. Only `.app` entries count (folders, spacers, and recent-app tiles are ignored).
current_dock_apps() {
  local url path decoded base
  while IFS=$'\t' read -r _ url _; do
    [ -n "$url" ] || continue
    path="${url#file://}"
    path="${path%/}"
    decoded="$(printf '%b' "${path//%/\\x}")"
    base="${decoded##*/}"
    case "$base" in
    *.app) printf '%s\n' "$base" ;;
    esac
  done < <(dockutil --list 2>/dev/null)
}

# True when the Dock's pinned apps already match the desired list exactly, in order.
dock_matches() {
  [ "$(current_dock_apps)" = "$(desired_apps)" ]
}

if dock_matches; then
  log "Dock already matches the desired layout — no changes needed."
  exit 0
fi

if [ "$check_only" = true ]; then
  log "Dock differs from the desired layout (--check, no changes made):"
  printf '  current: %s\n' "$(current_dock_apps | tr '\n' ' ')"
  printf '  desired: %s\n' "$(desired_apps | tr '\n' ' ')"
  exit 1
fi

log "Rebuilding the Dock (removes ALL current Dock items, then re-pins the list below)"
# Guarded so the rebuild ALWAYS finishes and restarts the Dock even if an individual dockutil
# call fails (#155): under `set -e` an unguarded `--add` failure would abort the script after
# `--remove all` has already emptied the Dock but before `killall Dock`, stranding an empty,
# un-restarted Dock. Collect failures and press on instead.
dockutil --no-restart --remove all >/dev/null ||
  echo "  WARNING: dockutil --remove all reported an error; continuing to re-pin and restart" >&2

failed=()
for app in "${apps[@]}"; do
  if [ -e "$app" ]; then
    if dockutil --no-restart --add "$app" >/dev/null; then
      echo "  added: $app"
    else
      echo "  WARNING: dockutil failed to add: $app" >&2
      failed+=("$app")
    fi
  else
    echo "  skipping (not installed): $app"
  fi
done

# Always restart the Dock — never leave it stranded empty/partial and un-restarted. A killall
# failure (no Dock session, e.g. headless CI) is tolerated, same as before.
killall Dock >/dev/null 2>&1 || true

if [ "${#failed[@]}" -gt 0 ]; then
  log "Dock rebuilt, but ${#failed[@]} app(s) failed to pin: ${failed[*]}"
  exit 1
fi
log "Dock rebuilt."
