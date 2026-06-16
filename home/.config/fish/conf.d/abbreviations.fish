# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# Shell abbreviations. Kept in conf.d (not config.fish) so config.fish stays
# minimal and these load in every interactive shell.

# git
abbr -a gco 'git checkout'
abbr -a gst 'git status'
abbr -a gp 'git pull'
abbr -a gl 'git log --oneline --graph --decorate'

# kubectl
abbr -a k kubectl
abbr -a ka 'kubectl apply -f'
