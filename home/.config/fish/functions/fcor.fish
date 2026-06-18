# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function fcor --description "Fuzzy-checkout a recent local branch (by commit date)"
    if not git rev-parse --git-dir >/dev/null 2>&1
        echo "Not a git repository." >&2
        return 1
    end

    set -l branch (
        git for-each-ref --sort=-committerdate --format='%(refname:short)' refs/heads \
            | fzf --no-multi --preview 'git log --oneline --graph --color=always -20 {}'
    )
    or return
    test -n "$branch"; or return
    git checkout $branch; or return
end
