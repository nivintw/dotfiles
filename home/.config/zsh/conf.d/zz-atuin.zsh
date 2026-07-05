# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# ─────────────────────────────────────────────────────────────────────────────
# atuin — SQLite-backed shell history with full-text search, bound to Ctrl+R.
#
# Filename is "zz-" prefixed on purpose (matching the fish original): conf.d files load
# in alphabetical order, and loading atuin LAST ensures it wins the Ctrl+R binding over
# anything an earlier conf.d file (or a zinit plugin) might claim.
#
# HOW TO REMOVE IT:
#   1. brew uninstall atuin
#   2. delete this file (home/.config/zsh/conf.d/zz-atuin.zsh) and re-stow
#   (History DB lives at ~/.local/share/atuin — delete it too for a clean wipe.)
#
# --disable-up-arrow keeps the Up key as ordinary zsh history; atuin takes only Ctrl+R.
# ─────────────────────────────────────────────────────────────────────────────
if [[ -o interactive ]] && command -v atuin >/dev/null 2>&1; then
    eval "$(atuin init zsh --disable-up-arrow)"
fi
