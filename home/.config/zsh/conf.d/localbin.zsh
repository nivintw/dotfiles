# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# ~/.local/bin holds the uv tool shims, the Claude CLI, and the stowed ollm helper. The
# installer only exports it for its own process; make it real for interactive zsh.
# .zshrc's `typeset -U path` keeps this idempotent across re-sourcing.
[[ -d "$HOME/.local/bin" ]] && path=("$HOME/.local/bin" $path)
