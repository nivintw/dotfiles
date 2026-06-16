# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function forrepos --description "Run a (simple) command at the root of every git repo under the current tree"
    if test -z "$argv[1]"
        echo "usage: forrepos <command...>" >&2
        return 2
    end

    # Find each repo by its .git entry, run at the repo root. Match both a .git
    # directory (normal clone) and a .git file (worktrees / submodules). -prune
    # stops the search from descending into a repo's own internals.
    for gitdir in (find . -name .git -prune | sort)
        set -l repo (dirname $gitdir)
        echo "── "(string replace -r '^\./' '' -- $repo)" ──"
        pushd $repo >/dev/null
        $argv
        popd >/dev/null
    end
end
