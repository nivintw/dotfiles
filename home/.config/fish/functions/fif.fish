# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function fif --description "Interactive ripgrep through file contents; enter opens the match in \$EDITOR"
    if not command -q rg
        echo "fif needs ripgrep (rg)." >&2
        return 1
    end

    set -l rg_cmd 'rg --column --line-number --no-heading --color=always --smart-case'
    set -l initial "$argv"

    # Initial result set: run rg for the seed query, or nothing (`true`) when
    # called with no args so the list starts empty and fills in as you type.
    set -l default_cmd true
    if test -n "$initial"
        set default_cmd "$rg_cmd -- "(string escape -- "$initial")
    end

    # --disabled turns off fzf's own fuzzy filtering so every keystroke re-runs
    # ripgrep instead (live full-text search). Preview highlights the match line.
    set -l result
    begin
        set -lx FZF_DEFAULT_COMMAND $default_cmd
        set result (
            fzf --ansi --disabled --query "$initial" \
                --bind "change:reload:$rg_cmd -- {q} || true" \
                --delimiter : \
                --preview 'bat --color=always {1} --highlight-line {2} 2>/dev/null || sed -n {2}p {1}' \
                --preview-window 'up,60%,border-bottom,+{2}/3'
        )
    end
    or return
    test -n "$result"; or return

    set -l file (string split -f1 : -- $result)
    set -l line (string split -f2 : -- $result)
    __open_at_line $file $line
end
