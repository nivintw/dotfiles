# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function __open_at_line --description "Internal helper: open file:line in the user's editor"
    set -l file $argv[1]
    set -l line $argv[2]

    # $EDITOR may carry flags (e.g. "code --wait"); split into a command + args
    # list so the switch dispatches on the program name, not the whole string.
    set -l editor (string split ' ' -- $EDITOR)
    if test -z "$editor[1]"
        if command -q code
            set editor code
        else if command -q nvim
            set editor nvim
        else if command -q vim
            set editor vim
        else
            # No editor found — fall back to the OS default handler (open / xdg-open /
            # wslview). It can't honor the line number, but opening the file beats nothing.
            set editor __os_open
        end
    end

    switch (basename $editor[1])
        case code code-insiders
            $editor --goto "$file:$line"
        case vim nvim vi
            $editor +$line -- $file
        case '*'
            # Generic editor, or the __os_open fallback when no editor was found. Surface a
            # failure instead of silently doing nothing — the __os_open fallback returns
            # non-zero when no OS handler exists, which would otherwise be invisible.
            if not $editor $file
                echo "__open_at_line: couldn't open $file (no editor, and no OS opener available)" >&2
                return 1
            end
    end
end
