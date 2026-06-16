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

[ "$(uname)" = "Darwin" ] || { echo "macos.sh is macOS-only; skipping." >&2; exit 0; }

log "Applying macOS defaults"

# Close System Settings so it can't override changes we're about to make.
osascript -e 'tell application "System Settings" to quit' 2>/dev/null || true

# ---------------------------------------------------------------------------
# Keyboard & text input
# ---------------------------------------------------------------------------
# Fast key repeat (KeyRepeat: lower = faster; 2 is very fast). Needs re-login.
defaults write NSGlobalDomain KeyRepeat -int 2
defaults write NSGlobalDomain InitialKeyRepeat -int 15
# Repeat the key when held instead of showing the accent-character popup
# (great for coding/vim; turn OFF if you type accented characters often).
defaults write NSGlobalDomain ApplePressAndHoldEnabled -bool false

# ---------------------------------------------------------------------------
# Trackpad / mouse
# ---------------------------------------------------------------------------
# Tap to click.
defaults write com.apple.driver.AppleBluetoothMultitouch.trackpad Clicking -bool true
defaults -currentHost write NSGlobalDomain com.apple.mouse.tapBehavior -int 1
# Scroll direction: false = "natural" scrolling OFF (traditional direction).
# NOTE: macOS has a SINGLE global scroll-direction flag — it governs BOTH the
# mouse and the trackpad. There is no native per-device setting (you'd need a
# tool like LinearMouse for that). This just codifies the current state.
defaults write NSGlobalDomain com.apple.swipescrolldirection -bool false

# ---------------------------------------------------------------------------
# General UI/UX
# ---------------------------------------------------------------------------
# Expand the save and print panels by default.
defaults write NSGlobalDomain NSNavPanelExpandedStateForSaveMode -bool true
defaults write NSGlobalDomain NSNavPanelExpandedStateForSaveMode2 -bool true
defaults write NSGlobalDomain PMPrintingExpandedStateForPrint -bool true
defaults write NSGlobalDomain PMPrintingExpandedStateForPrint2 -bool true
# Near-instant window resize animations.
defaults write NSGlobalDomain NSWindowResizeTime -float 0.001

# ---------------------------------------------------------------------------
# Finder
# ---------------------------------------------------------------------------
# Show all filename extensions.
defaults write NSGlobalDomain AppleShowAllExtensions -bool true
# Show hidden files (toggle anytime with Cmd-Shift-. — set false if you'd rather).
defaults write com.apple.finder AppleShowAllFiles -bool true
# Show the path bar and status bar.
defaults write com.apple.finder ShowPathbar -bool true
defaults write com.apple.finder ShowStatusBar -bool true
# Keep folders on top when sorting by name.
defaults write com.apple.finder _FXSortFoldersFirst -bool true
# Search the current folder by default (not the whole Mac).
defaults write com.apple.finder FXDefaultSearchScope -string "SCcf"
# Use list view in all Finder windows by default.
defaults write com.apple.finder FXPreferredViewStyle -string "Nlsv"
# Don't write .DS_Store files on network or USB volumes.
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool true
defaults write com.apple.desktopservices DSDontWriteUSBStores -bool true
# Don't warn when changing a file extension.
defaults write com.apple.finder FXEnableExtensionChangeWarning -bool false

# ---------------------------------------------------------------------------
# Screenshots
# ---------------------------------------------------------------------------
mkdir -p "${HOME}/Pictures/Screenshots"
defaults write com.apple.screencapture location -string "${HOME}/Pictures/Screenshots"
defaults write com.apple.screencapture type -string "png"
# Disable the drop shadow on window screenshots.
defaults write com.apple.screencapture disable-shadow -bool true

# ---------------------------------------------------------------------------
# Dock
# ---------------------------------------------------------------------------
# Keep the Dock always visible (no auto-hide).
defaults write com.apple.dock autohide -bool false
# Default icon size (48); scale (not genie) minimize.
defaults write com.apple.dock tilesize -int 48
defaults write com.apple.dock mineffect -string "scale"
# Minimize windows into their application's Dock icon.
defaults write com.apple.dock minimize-to-application -bool true
# Don't show recently-used apps in the Dock.
defaults write com.apple.dock show-recents -bool false
# Don't automatically rearrange Spaces based on most recent use.
defaults write com.apple.dock mru-spaces -bool false
# Show hidden (Cmd-H'd) apps as dimmed icons in the Dock instead of vanishing.
defaults write com.apple.dock showhidden -bool true

# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------
log "Restarting affected apps (Finder, Dock, SystemUIServer)"
for app in Finder Dock SystemUIServer; do killall "$app" >/dev/null 2>&1 || true; done

log "Done. Some settings (e.g. key repeat) need a logout/restart to fully apply."
