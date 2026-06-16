# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# Rancher Desktop keeps its CLI shims (docker, kubectl, nerdctl, helm, …) in
# ~/.rd/bin. Rancher itself injects a machine-specific, absolute-path block into
# config.fish ("### MANAGED BY RANCHER DESKTOP …"); we keep that out of the repo
# and add a portable equivalent here instead. $HOME makes it identical on every
# machine, and fish_add_path is idempotent so re-sourcing won't duplicate it.
if test -d "$HOME/.rd/bin"
    fish_add_path --global --prepend "$HOME/.rd/bin"
end
