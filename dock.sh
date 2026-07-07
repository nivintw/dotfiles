#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Declarative macOS Dock layout via dockutil.
#
#   ~/dotfiles/dock.sh            # apply the layout (idempotent)
#   ~/dotfiles/dock.sh --check    # report drift only; make no changes
#
# Idempotent — when the Dock's pinned apps already match the list below it does
# nothing (no rebuild, no flash). Otherwise it clears the Dock and rebuilds it,
# then restarts the Dock. Edit the `apps` array to taste; it was seeded from the
# Dock present when this script was written (Safari, Mail). Missing apps are
# skipped, so it's safe to list apps you haven't installed yet.
set -euo pipefail

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
log_warn() { printf '\033[1;33m[!!]\033[0m %s\n' "$1" >&2; }

# A deliberate no-op bail (not macOS, dockutil missing/broken) exits with this code, distinct
# from 0 (Dock actually rebuilt or already correct) — src/dotfiles_install/system_setup.py's
# caller branches on it so a skip can't be misreported as "Dock layout applied".
SKIPPED_EXIT=2

# --check: report drift without touching the Dock. Any other argument is an error.
check_only=0
case "${1:-}" in
--check) check_only=1 ;;
"") ;;
*)
  echo "usage: dock.sh [--check]" >&2
  exit "$SKIPPED_EXIT"
  ;;
esac

# The OS guard reads through a variable so the bats suite can drive the rebuild logic on a
# Linux runner (DOCK_UNAME=Darwin) with a fake dockutil/killall on PATH — the same override
# seam the Python installer's os_detect uses.
[ "${DOCK_UNAME:-$(uname)}" = "Darwin" ] || {
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
current_list=""
current_list="$(dockutil --list 2>/dev/null)" || {
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

# Test/override seam: DOCK_APPS (newline-separated absolute .app paths) replaces the list
# above when set, so the bats suite can point the rebuild at fake apps under a tmpdir (real
# /Applications/*.app can't be created on a Linux CI runner).
if [ -n "${DOCK_APPS:-}" ]; then
  apps=()
  while IFS= read -r _app_override; do
    [ -n "$_app_override" ] && apps+=("$_app_override")
  done <<<"$DOCK_APPS"
fi

# Percent-decode stdin (e.g. %20 -> space) so a dockutil file URL compares against a plain
# filesystem path. printf '%b' expands \xNN escapes; mapping every % to \x turns %20 into \x20.
_decode() {
  local s
  s="$(cat)"
  printf '%b' "${s//%/\\x}"
}

# Reduce an app path or dockutil file URL to a stable comparison key: its percent-decoded
# basename with the .app suffix dropped. Keying on the basename (not the full path) is what
# makes the comparison robust to macOS cryptex prefixes — the same Safari shows up as
# /Applications/Safari.app in the desired list but /System/Cryptexes/App/.../Safari.app in the
# live Dock; both reduce to "Safari".
_appkey() {
  local p
  p="$(printf '%s' "$1" | _decode)"
  p="${p%/}"    # strip a trailing slash (dockutil URLs carry one)
  p="${p##*/}"  # basename
  p="${p%.app}" # drop the .app suffix
  printf '%s' "$p"
}

# Desired pinned apps, in order — only those actually installed (the same -e filter the
# rebuild uses, so "already matches" agrees with what a rebuild would produce).
desired=()
for app in "${apps[@]}"; do
  [ -e "$app" ] && desired+=("$(_appkey "$app")")
done

# Current pinned apps, in order: pull the last .app token off each `dockutil --list` line
# (works regardless of the version's column layout) and reduce it to the same key. Non-app
# Dock items (folders, stacks, spacers) carry no .app token and are skipped — the comparison
# is scoped to pinned apps by design.
current=()
while IFS= read -r line; do
  [ -n "$line" ] || continue
  appref="$(printf '%s\n' "$line" | grep -oE '[^[:space:]]*\.app/?' | tail -n1)" || true
  [ -n "$appref" ] && current+=("$(_appkey "$appref")")
done <<<"$current_list"

# Newline-join for an exact ordered comparison ("${arr[@]}" on an empty array is safe under
# set -u in modern bash).
join_lines() {
  local IFS=$'\n'
  printf '%s' "${*}"
}
desired_str="$(join_lines "${desired[@]}")"
current_str="$(join_lines "${current[@]}")"

if [ "$desired_str" = "$current_str" ]; then
  if [ "$check_only" = 1 ]; then
    echo "Dock already matches the desired layout (no drift)."
  else
    log "Dock already matches the desired layout — nothing to do."
  fi
  exit 0
fi

# From here the Dock differs from the desired layout.
if [ "$check_only" = 1 ]; then
  echo "Dock drift detected:"
  echo "  desired: ${desired[*]:-(none)}"
  echo "  current: ${current[*]:-(none)}"
  exit 1
fi

log "Rebuilding the Dock (removes ALL current Dock items, then re-pins the list below)"
# Guard every mutating step so a transient dockutil failure can't abort the run under set -e
# and strand a half-built or empty Dock: collect failures and press on, then ALWAYS restart
# the Dock at the end. (Before this, a failed --add after --remove all left an empty,
# un-restarted Dock — see issue #155.)
dockutil --no-restart --remove all >/dev/null ||
  log_warn "dockutil --remove all failed (continuing to rebuild anyway)"

add_failures=0
for app in "${apps[@]}"; do
  if [ -e "$app" ]; then
    if dockutil --no-restart --add "$app" >/dev/null; then
      echo "  added: $app"
    else
      log_warn "failed to add $app (continuing)"
      add_failures=$((add_failures + 1))
    fi
  else
    echo "  skipping (not installed): $app"
  fi
done

# ALWAYS restart the Dock, even if some --add calls failed — a rebuilt-but-not-restarted Dock
# is the exact stranded state we're guarding against.
killall Dock >/dev/null 2>&1 || true

if [ "$add_failures" -gt 0 ]; then
  log_warn "Dock rebuilt with $add_failures app(s) that failed to add — re-run to retry."
else
  log "Dock rebuilt."
fi
