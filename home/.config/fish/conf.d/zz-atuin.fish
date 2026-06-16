# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# ─────────────────────────────────────────────────────────────────────────────
# atuin — SQLite-backed shell history with full-text search, bound to Ctrl+R.
#
# Filename is "zz-" prefixed on purpose: conf.d files load in alphabetical order,
# and fzf.fish (which also binds Ctrl+R) ships as `conf.d/*fzf*`. Loading atuin
# LAST ensures atuin wins Ctrl+R. fzf.fish keeps its other bindings (Ctrl+Alt+*).
#
# HOW TO REMOVE IT (if you miss fzf.fish's history UI):
#   1. brew uninstall atuin
#   2. delete this file (home/.config/fish/conf.d/zz-atuin.fish) and re-stow
#   3. fzf.fish reclaims Ctrl+R automatically on next shell start
#   (History DB lives at ~/.local/share/atuin — delete it too for a clean wipe.)
#
# --disable-up-arrow keeps the Up key as ordinary fish history; atuin takes only
# Ctrl+R.
# ─────────────────────────────────────────────────────────────────────────────
if status is-interactive; and command -q atuin
    atuin init fish --disable-up-arrow | source
end
