# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function gcor --description "Checkout a recently-visited branch (from the reflog)"
    if not git rev-parse --git-dir >/dev/null 2>&1
        echo "Not a git repository." >&2
        return 1
    end

    # Pull branch names out of the reflog's "moving from X to Y" entries, in
    # most-recent-first order, deduped. Surfaces branches you visited even if a
    # later prune removed their remote.
    set -l branch (
        git reflog 2>/dev/null \
            | grep -oE 'moving from [^ ]+ to [^ ]+' \
            | awk '{print $NF}' \
            | awk '!seen[$0]++' \
            | head -n 30 \
            | fzf --no-multi --preview 'git log --oneline --graph --color=always -20 {}'
    )
    or return
    test -n "$branch"; or return
    git checkout $branch; or return
end
