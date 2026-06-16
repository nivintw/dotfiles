# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function fco --description "Fuzzy-checkout a git branch (local or remote)"
    if not git rev-parse --git-dir >/dev/null 2>&1
        echo "Not a git repository." >&2
        return 1
    end

    # List local + remote branches, strip the `remotes/<remote>/` prefix and the
    # `*`/whitespace decorations, dedupe. Checking out a name that exists only on
    # a remote makes git create a local tracking branch automatically.
    set -l branch (
        git branch --all --color=never \
            | string replace -r '^[+* ]+' '' \
            | string replace -r '^remotes/[^/]+/' '' \
            | string match -v -- 'HEAD*' \
            | sort -u \
            | fzf --no-multi --preview 'git log --oneline --graph --color=always -20 {}'
    )
    or return
    test -n "$branch"; or return
    git checkout $branch
end
