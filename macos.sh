#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# macOS system defaults — a curated set of `defaults write` tweaks.
#
# Curated, NOT a dump. Read it and comment out anything you don't want before
# running. Inspired by Mathias Bynens' ~/.macos, trimmed to a sane starting set.
#
#   ~/dotfiles/macos.sh
#
# Idempotent — safe to re-run. Most settings take effect after the killall at
# the end; a few (marked) only apply after logout/restart. None require sudo.
#
# Discover the key for a setting yourself: change it in System Settings, then
# diff `defaults read` before/after — the changed line is your `defaults write`.
set -euo pipefail

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
log_warn() { printf '\033[1;33m[!!]\033[0m %s\n' "$1" >&2; }

# dwrite — a `defaults` wrapper that survives writes blocked on a managed Mac.
# On an MDM-managed box a configuration profile can pin a key, and the matching
# `defaults write` fails; under `set -euo pipefail` that would abort the whole run
# at the first such key. Instead we capture `defaults`' own output and surface it,
# then keep going — so the un-managed settings still apply.
#
# The warning does NOT assert the cause: MDM is the likely case on a managed box,
# but the same failure shows up for a permissions issue, an unknown domain, or a
# wrong value type, so we print exactly what `defaults` reported and let you judge.
# Always returns 0 so one rejected key can't take down the run.
dwrite() {
  local out
  if ! out="$(defaults "$@" 2>&1)"; then
    log_warn "could not apply: defaults $*"
    [ -n "$out" ] && printf '    %s\n' "$out" >&2
  fi
  return 0
}

[ "$(uname)" = "Darwin" ] || {
  echo "macos.sh is macOS-only; skipping." >&2
  exit 0
}

log "Applying macOS defaults"

# Close System Settings so it can't override changes we're about to make.
osascript -e 'tell application "System Settings" to quit' 2>/dev/null || true

# ---------------------------------------------------------------------------
# Keyboard & text input
# ---------------------------------------------------------------------------
# Fast key repeat (KeyRepeat: lower = faster; 2 is very fast). Needs re-login.
dwrite write NSGlobalDomain KeyRepeat -int 3
dwrite write NSGlobalDomain InitialKeyRepeat -int 18
# Repeat the key when held instead of showing the accent-character popup
# (great for coding/vim; turn OFF if you type accented characters often).
dwrite write NSGlobalDomain ApplePressAndHoldEnabled -bool false

# ---------------------------------------------------------------------------
# Trackpad / mouse
# ---------------------------------------------------------------------------
# Tap to click.
dwrite write com.apple.driver.AppleBluetoothMultitouch.trackpad Clicking -bool true
dwrite -currentHost write NSGlobalDomain com.apple.mouse.tapBehavior -int 1
# Scroll direction: false = "natural" scrolling OFF (traditional direction).
# NOTE: macOS has a SINGLE global scroll-direction flag — it governs BOTH the
# mouse and the trackpad. There is no native per-device setting (you'd need a
# tool like LinearMouse for that). This just codifies the current state.
dwrite write NSGlobalDomain com.apple.swipescrolldirection -bool false

# ---------------------------------------------------------------------------
# General UI/UX
# ---------------------------------------------------------------------------
# Expand the save and print panels by default.
dwrite write NSGlobalDomain NSNavPanelExpandedStateForSaveMode -bool true
dwrite write NSGlobalDomain NSNavPanelExpandedStateForSaveMode2 -bool true
dwrite write NSGlobalDomain PMPrintingExpandedStateForPrint -bool true
dwrite write NSGlobalDomain PMPrintingExpandedStateForPrint2 -bool true
# Near-instant window resize animations.
dwrite write NSGlobalDomain NSWindowResizeTime -float 0.001

# ---------------------------------------------------------------------------
# Finder
# ---------------------------------------------------------------------------
# Show all filename extensions.
dwrite write NSGlobalDomain AppleShowAllExtensions -bool true
# Show hidden files (toggle anytime with Cmd-Shift-. — set false if you'd rather).
dwrite write com.apple.finder AppleShowAllFiles -bool true
# Show the path bar and status bar.
dwrite write com.apple.finder ShowPathbar -bool true
dwrite write com.apple.finder ShowStatusBar -bool true
# Keep folders on top when sorting by name.
dwrite write com.apple.finder _FXSortFoldersFirst -bool true
# Search the current folder by default (not the whole Mac).
dwrite write com.apple.finder FXDefaultSearchScope -string "SCcf"
# Use list view in all Finder windows by default.
dwrite write com.apple.finder FXPreferredViewStyle -string "Nlsv"
# Don't write .DS_Store files on network or USB volumes.
dwrite write com.apple.desktopservices DSDontWriteNetworkStores -bool true
dwrite write com.apple.desktopservices DSDontWriteUSBStores -bool true
# Don't warn when changing a file extension.
dwrite write com.apple.finder FXEnableExtensionChangeWarning -bool false

# ---------------------------------------------------------------------------
# Screenshots
# ---------------------------------------------------------------------------
# Only repoint the screencapture location if the directory actually exists afterward. On a
# managed Mac the mkdir can be blocked (the same reason dwrite exists to survive blocked
# writes) — pointing screencapture at a directory that isn't there would silently break
# screenshots, so leave the location unchanged when the dir couldn't be created.
screenshot_dir="${HOME}/Pictures/Screenshots"
if mkdir -p "$screenshot_dir" 2>/dev/null && [ -d "$screenshot_dir" ]; then
  dwrite write com.apple.screencapture location -string "$screenshot_dir"
else
  log_warn "could not create $screenshot_dir — leaving the screencapture location unchanged"
fi
dwrite write com.apple.screencapture type -string "png"
# Disable the drop shadow on window screenshots.
dwrite write com.apple.screencapture disable-shadow -bool true

# ---------------------------------------------------------------------------
# Dock
# ---------------------------------------------------------------------------
# Keep the Dock always visible (no auto-hide).
dwrite write com.apple.dock autohide -bool false
# Default icon size (61); scale (not genie) minimize.
dwrite write com.apple.dock tilesize -int 61
dwrite write com.apple.dock mineffect -string "scale"
# Minimize windows into their application's Dock icon.
dwrite write com.apple.dock minimize-to-application -bool true
# Don't show recently-used apps in the Dock.
dwrite write com.apple.dock show-recents -bool false
# Don't automatically rearrange Spaces based on most recent use.
dwrite write com.apple.dock mru-spaces -bool false
# Show hidden (Cmd-H'd) apps as dimmed icons in the Dock instead of vanishing.
dwrite write com.apple.dock showhidden -bool true

# ---------------------------------------------------------------------------
# Machine-local overlay
# ---------------------------------------------------------------------------
# Per-machine defaults (work vs personal) live in an untracked file outside the
# repo; source it here so its writes are applied by the same killall below. Use
# `dwrite ...` in it for the same MDM-safe "warn and continue" behavior. Seeded by
# install.sh; missing file = no-op.
macos_local="$HOME/.config/dotfiles/macos.local.sh"
# shellcheck source=/dev/null
[ -f "$macos_local" ] && . "$macos_local"

# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------
log "Restarting affected apps (Finder, Dock, SystemUIServer)"
for app in Finder Dock SystemUIServer; do killall "$app" >/dev/null 2>&1 || true; done

log "Done. Some settings (e.g. key repeat) need a logout/restart to fully apply."
