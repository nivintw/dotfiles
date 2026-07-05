# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# zsh always reads ~/.zshenv (before it even knows ZDOTDIR exists), so this is the one
# file that must live at the real $HOME rather than under the XDG-style tree below.
# Setting ZDOTDIR here redirects every other zsh startup file (.zshrc, .zprofile, …) to
# home/.config/zsh/, mirroring fish's ~/.config/fish/ layout.
export ZDOTDIR="$HOME/.config/zsh"
