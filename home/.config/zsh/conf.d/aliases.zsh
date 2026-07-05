# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# Interactive-only aliases (fish's abbreviations have no zsh equivalent without a plugin,
# so they're folded in here as plain aliases). Guarded with [[ -o interactive ]] so
# scripts and non-interactive shells keep the real binaries — avoids surprising any
# tooling that shells out to `ls`.
if [[ -o interactive ]] && command -v eza >/dev/null 2>&1; then
    # eza as a drop-in ls with a git column and icons.
    # icons=auto only emits glyphs to a TTY; if your VS Code terminal font lacks a Nerd
    # Font glyphs and shows boxes, change these to `--icons=never`.
    alias ls='eza --group-directories-first'
    alias ll='eza -l --git --icons=auto --group-directories-first'
    alias la='eza -la --git --icons=auto --group-directories-first'
    alias lt='eza --tree --level=2 --icons=auto'
fi

# git
alias gco='git checkout'
alias gst='git status'
alias gp='git pull'
alias gl='git log --oneline --graph --decorate'

# kubectl
alias k=kubectl
alias ka='kubectl apply -f'
