# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function fkill --description "Fuzzy-select and kill process(es). Default SIGTERM; pass a signal, e.g. fkill 9"
    set -l signal 15
    if set -q argv[1]
        set signal $argv[1]
    end

    # Validate the signal up front: a number (9), or a name (TERM / SIGTERM).
    # Rejecting garbage here is what lets the sudo fallback below assume any
    # kill failure is a real permission issue, not a typo.
    if not string match -qr '^([0-9]{1,3}|(SIG)?[A-Z]+)$' -- $signal
        echo "fkill: invalid signal '$signal' (use a number like 9 or a name like TERM)" >&2
        return 2
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
            # The kill failed. Only escalate to sudo if the process is still
            # alive (a permissions problem) — never prompt for a password just
            # because it already exited between selection and signal.
            if ps -p $pid >/dev/null 2>&1
                sudo kill -$signal $pid
            end
        end
    end
end
