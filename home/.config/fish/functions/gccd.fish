# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function gccd --description "git clone a repo and cd into it"
    if test (count $argv) -lt 1
        echo "usage: gccd <repo-url> [dir]" >&2
        return 2
    end

    git clone $argv; or return

    set -l target $argv[2]
    if test -z "$target"
        # Derive the directory name git would have created from the URL.
        set target (basename $argv[1] .git)
    end
    cd $target
end
