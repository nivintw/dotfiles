# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function fkill --description "Fuzzy-select and kill process(es). Default SIGTERM; pass a signal, e.g. fkill 9"
    set -l signal 15
    if set -q argv[1]
        set signal $argv[1]
    end

    set -l pids (
        ps -axo pid,user,%cpu,%mem,command \
            | fzf --multi --header-lines=1 --prompt "kill -$signal > " \
            | awk '{print $1}'
    )
    test -n "$pids"; or return

    for pid in $pids
        echo "Killing $pid (signal $signal)"
        if not kill -$signal $pid 2>/dev/null
            sudo kill -$signal $pid
        end
    end
end
