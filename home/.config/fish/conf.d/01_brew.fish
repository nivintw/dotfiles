# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# TWN notes: configure fish shell for homebrew.
# This isn't automatic because we use homebrew to install fish.
# Thus, we create a chicken and egg situation and have to do this after the fact.

# This is safe to run any number of times
# i.e. sub-shells
# because it is well-written. Good job homebrew team!
#
# Prefer the Apple-Silicon prefix; fall back to the Intel prefix so a shell on an
# Intel Mac doesn't error on every startup. Silent no-op if brew isn't installed.
for brew_bin in /opt/homebrew/bin/brew /usr/local/bin/brew
    if test -x $brew_bin
        $brew_bin shellenv | source
        break
    end
end

# Don't let `brew bundle cleanup` uninstall VS Code extensions: most are managed
# by VS Code Settings Sync, not the Brewfile. Only extensions explicitly listed
# in the Brewfile are installed by `brew bundle install`.
set -gx HOMEBREW_BUNDLE_CLEANUP_NO_VSCODE 1
