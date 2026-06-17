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
    # NUL-delimited (-print0 / sort -z / split0) so paths with spaces or
    # newlines survive intact instead of being split into bogus iterations.
    for gitdir in (find . -name .git -prune -print0 | sort -z | string split0)
        set -l repo (dirname -- $gitdir)
        echo "── "(string replace -r '^\./' '' -- $repo)" ──"
        pushd $repo >/dev/null; or continue
        $argv
        popd >/dev/null
    end
end
