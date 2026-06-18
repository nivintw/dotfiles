# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function forrepos --description "Run a command at the root of EVERY git repo under \$PWD (fans out; no dry-run — careful with destructive commands)"
    if test -z "$argv[1]"
        echo "usage: forrepos <command...>" >&2
        return 2
    end

    # CAUTION: this runs $argv at the root of every git repo found under the
    # current directory, with no confirmation and no dry-run. A destructive
    # command (e.g. `git reset --hard`) is multiplied across all of them. Run it
    # from a directory whose repo set you know.
    #
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
        # If $argv touched the dir stack, a bare popd could resume from the wrong
        # directory; bail out rather than fan out into an unknown CWD.
        popd >/dev/null; or break
    end
end
