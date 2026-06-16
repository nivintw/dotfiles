# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# Interactive-only aliases. Guarded with `status is-interactive` so scripts and
# non-interactive shells keep the real binaries — avoids surprising any tooling
# that shells out to `ls`.

if status is-interactive; and command -q eza
    # eza as a drop-in ls with a git column and icons.
    # icons=auto only emits glyphs to a TTY; if your VS Code terminal font lacks
    # Nerd Font glyphs and shows boxes, change these to `--icons=never`.
    alias ls 'eza --group-directories-first'
    alias ll 'eza -l --git --icons=auto --group-directories-first'
    alias la 'eza -la --git --icons=auto --group-directories-first'
    alias lt 'eza --tree --level=2 --icons=auto'
end
