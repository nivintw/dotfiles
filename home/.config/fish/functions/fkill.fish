# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function fkill --description "Fuzzy-select and kill process(es). Default SIGTERM; pass a signal, e.g. fkill 9"
    set -l signal 15
    if set -q argv[1]
        set signal $argv[1]
    end

    # Validate the signal up front. A number is range-checked; a name is validated
    # case-insensitively (term / TERM / SIGTERM) against the signals this host's
    # `kill -l` actually knows — so a typo like `fkill TremK` is caught here rather
    # than deferred to `kill`, and a valid lowercase name no longer false-rejects.
    if string match -qr '^[0-9]+$' -- $signal
        # Bound numeric signals so 0 (a no-op probe) and out-of-range values like
        # 999 don't reach `kill` (and then a pointless `sudo kill`).
        if test $signal -lt 1; or test $signal -gt 64
            echo "fkill: signal number '$signal' out of range (use 1-64)" >&2
            return 2
        end
    else
        # Normalize the candidate to a bare uppercase name (drop an optional SIG).
        set -l name (string upper -- $signal | string replace -r '^SIG' '')
        # Known names from `kill -l`, normalized the same way. Handles both the BSD
        # format (bare `HUP INT … TERM`) and the GNU format (`15) SIGTERM`): strip
        # SIG, then keep only alphabetic tokens so the `15)` ordinals fall away.
        set -l known (kill -l 2>/dev/null | string split -n ' ' \
            | string upper | string replace -r '^SIG' '' | string match -r '^[A-Z][A-Z0-9]*$')
        if not contains -- $name $known
            echo "fkill: invalid signal '$signal' (use a number like 9 or a name like TERM)" >&2
            return 2
        end
        set signal $name
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
