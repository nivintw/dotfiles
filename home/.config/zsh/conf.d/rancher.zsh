# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# Rancher Desktop keeps its CLI shims (docker, kubectl, nerdctl, helm, …) in ~/.rd/bin.
# Rancher itself injects a machine-specific, absolute-path block into shell rc files
# ("### MANAGED BY RANCHER DESKTOP …"); we keep that out of the repo and add a portable
# equivalent here instead. $HOME makes it identical on every machine, and .zshrc's
# `typeset -U path` keeps this idempotent across re-sourcing.
[[ -d "$HOME/.rd/bin" ]] && path=("$HOME/.rd/bin" $path)
