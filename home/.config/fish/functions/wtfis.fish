# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function wtfis --description "Explain what a name resolves to (alias / function / builtin / binary + real path)"
    if test -z "$argv[1]"
        echo "usage: wtfis <name>..." >&2
        return 2
    end

    for name in $argv
        echo "── $name ──"
        if not type -a $name 2>/dev/null
            echo "  (not found)"
        end
        # If it resolves to a file, show where a symlink ultimately points.
        set -l path (command -v $name 2>/dev/null)
        if test -n "$path"; and test -L "$path"
            set -l real (readlink "$path")
            echo "  -> symlink to: $real"
        end
        echo
    end
end
