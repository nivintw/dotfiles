# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# ~/.local/bin holds the uv tool shims, the Claude CLI, and the stowed ollm helper.
# The installer only exports it for its own process; make it real for interactive
# fish. fish_add_path is idempotent, so re-sourcing won't duplicate it.
if test -d "$HOME/.local/bin"
    fish_add_path --global "$HOME/.local/bin"
end
