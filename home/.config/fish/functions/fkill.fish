# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function fkill --description "Fuzzy-select and kill process(es). Default SIGTERM; pass a signal, e.g. fkill 9"
    set -l signal 15
    if set -q argv[1]
        set signal $argv[1]
    end

    # Validate the signal up front: a number (9), or a name (TERM / SIGTERM).
    if not string match -qr '^([0-9]{1,3}|(SIG)?[A-Z]+)$' -- $signal
        echo "fkill: invalid signal '$signal' (use a number like 9 or a name like TERM)" >&2
        return 2
    end
    # Bound numeric signals to the valid range so 0 (a no-op probe) and out-of-range
    # values like 999 don't reach `kill` (and then a pointless `sudo kill`).
    if string match -qr '^[0-9]+$' -- $signal
        if test $signal -lt 1; or test $signal -gt 64
            echo "fkill: signal number '$signal' out of range (use 1-64)" >&2
            return 2
        end
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
            # The kill failed. If the process is still alive it's likely a
            # permissions issue — offer to retry under sudo, but never escalate
            # silently. (If it simply exited between selection and signal, skip.)
            if ps -p $pid >/dev/null 2>&1
                read -l -P "  kill $pid failed — retry with sudo? [y/N] " reply
                if string match -qr '^[Yy]' -- $reply
                    sudo kill -$signal $pid
                else
                    echo "  skipped sudo kill for $pid"
                end
            end
        end
    end
end
