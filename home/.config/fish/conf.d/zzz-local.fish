# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# Machine-local fish config (work vs personal vs homelab). Loaded late (zzz-)
# so it can adjust what the other conf.d snippets set. The file lives OUTSIDE the
# stowed tree — ~/.config/dotfiles/ is never managed by stow, so a fresh-machine
# fold can't pull it into the repo — keeping work-specific env/PATH/abbreviations
# untracked while the public repo stays generic. Same idea as ~/.ssh/config.local
# and ~/.gitconfig_local. Missing file = no-op.
set -l local_config $HOME/.config/dotfiles/local.fish
test -f $local_config; and source $local_config
