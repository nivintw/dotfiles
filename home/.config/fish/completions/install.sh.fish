# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# install.sh is invoked by path (~/dotfiles/install.sh), but fish keys completions
# on the command's basename, so `complete -c install.sh` applies to any path form.
# `-f` suppresses filename completion so the flags aren't mixed with a directory
# listing.

function __install_sh_bundles --description "Available opt-in Brewfile bundle names"
    # Mirror install.sh's discovery: Brewfile.d/<name>.brewfile basenames. Resolve
    # the repo via $DOTFILES, then the current repo, then the conventional checkout
    # — the same precedence launch-docs uses.
    set -l toplevel (git rev-parse --show-toplevel 2>/dev/null)
    for cand in "$DOTFILES/Brewfile.d" "$toplevel/Brewfile.d" "$HOME/dotfiles/Brewfile.d"
        if test -d "$cand"
            for bf in $cand/*.brewfile
                test -e "$bf"; and basename "$bf" .brewfile
            end
            return
        end
    end
end

complete -c install.sh -f
complete -c install.sh -l bundle -x -a "(__install_sh_bundles)" -d "Opt into a Brewfile bundle (repeatable)"
complete -c install.sh -l no-bundles -d "Opt into no bundles (baseline only)"
complete -c install.sh -l keep-bundles -d "Keep the saved selection; skip the picker"
complete -c install.sh -s h -l help -d "Show help and exit"
