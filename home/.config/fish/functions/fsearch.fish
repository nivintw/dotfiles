# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function fsearch --description "Ripgrep file contents for a pattern, fuzzy-pick a match, open in \$EDITOR"
    if not command -q rg
        echo "fsearch needs ripgrep (rg)." >&2
        return 1
    end
    if test -z "$argv"
        echo "usage: fsearch <pattern>" >&2
        return 2
    end

    # One-shot search (vs fif's live reload): run ripgrep once for the pattern,
    # then fuzzy-filter the results in fzf.
    set -l result (
        rg --column --line-number --no-heading --color=always --smart-case -- $argv \
            | fzf --ansi --delimiter : \
                --preview 'bat --color=always {1} --highlight-line {2} 2>/dev/null || sed -n {2}p {1}' \
                --preview-window 'up,60%,border-bottom,+{2}/3'
    )
    or return
    test -n "$result"; or return

    # rg --column emits FILE:LINE:COL:TEXT. Extract FILE + LINE with a regex
    # (non-greedy path) so a filename containing ':' isn't truncated by a split.
    set -l parsed (string match -rg '^(.+?):(\d+):' -- $result)
    or return
    __open_at_line $parsed[1] $parsed[2]
end
