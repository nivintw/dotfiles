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
            set editor open
        end
    end

    switch (basename $editor[1])
        case code code-insiders
            $editor --goto "$file:$line"
        case vim nvim vi
            $editor +$line -- $file
        case '*'
            $editor $file
    end
end
