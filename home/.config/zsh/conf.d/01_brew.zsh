# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# TWN notes: configure zsh shell for homebrew.
# This isn't automatic because we use homebrew to install zsh (a newer one than Apple
# ships). Thus, we create a chicken and egg situation and have to do this after the fact.

# This is safe to run any number of times (e.g. sub-shells) because it is well-written.
# Good job homebrew team!
#
# Try each known Homebrew prefix in turn: Apple-Silicon mac, Intel mac, then the two
# Linuxbrew locations (system-wide install, then a per-user ~/.linuxbrew). The first one
# present wins; silent no-op if brew isn't installed at all.
for brew_bin in /opt/homebrew/bin/brew /usr/local/bin/brew /home/linuxbrew/.linuxbrew/bin/brew "$HOME/.linuxbrew/bin/brew"; do
    if [[ -x "$brew_bin" ]]; then
        eval "$("$brew_bin" shellenv)"
        break
    fi
done
unset brew_bin

# Don't let `brew bundle cleanup` uninstall VS Code extensions: most are managed by VS
# Code Settings Sync, not the Brewfile. Only extensions explicitly listed in the Brewfile
# are installed by `brew bundle install`.
export HOMEBREW_BUNDLE_CLEANUP_NO_VSCODE=1
