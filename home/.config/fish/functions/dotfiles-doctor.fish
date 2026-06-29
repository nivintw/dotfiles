# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function dotfiles-doctor --description "Check that the dotfiles install is healthy (verify_install)"
    # Resolve the repo without hardcoding ~/dotfiles: honor $DOTFILES, then the current repo
    # (so it works from any worktree you're cd'd into), then the conventional checkout.
    set -l toplevel (git rev-parse --show-toplevel 2>/dev/null)
    set -l checker
    for cand in "$DOTFILES" "$toplevel" "$HOME/dotfiles"
        # Skip an empty candidate ($DOTFILES unset / not in a git repo) so it can't collapse to
        # an absolute "/scripts/verify_install.sh" and probe a checker outside the repo.
        if test -n "$cand"; and test -f "$cand/scripts/verify_install.sh"
            set checker "$cand/scripts/verify_install.sh"
            break
        end
    end
    if test -z "$checker"
        echo "dotfiles-doctor: verify_install.sh not found (set \$DOTFILES or run from the dotfiles repo)" >&2
        return 1
    end

    # verify_install reads only — no sudo, no mutation — and exits non-zero when anything needs
    # attention, so dotfiles-doctor is safe to run any time and usable directly in a conditional.
    bash "$checker"
end
