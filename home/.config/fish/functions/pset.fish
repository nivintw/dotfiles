# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function pset --description "Set an exported env var from a hidden prompt (keeps secrets out of shell history)"
    set -l name $argv[1]
    if test -z "$name"
        echo "usage: pset VARNAME" >&2
        return 2
    end
    if not string match -qr '^[A-Za-z_][A-Za-z0-9_]*$' -- $name
        echo "pset: invalid variable name '$name'" >&2
        return 2
    end

    # read -s: silent (no echo), and because the value is typed at a prompt it
    # never appears on the command line, so it isn't recorded in history.
    read -s -P "$name = " value
    if test -z "$value"
        echo "pset: empty value — $name not set" >&2
        return 1
    end
    set -gx $name $value
    echo "(set $name for this session; value not echoed or recorded)" >&2
end
