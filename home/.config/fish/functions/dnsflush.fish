# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function dnsflush --description "Flush the macOS DNS cache"
    # Both steps are independent and both matter (the killall is what actually
    # refreshes the resolver), so run them unconditionally — chaining with `and`
    # would skip the killall whenever the flush returned non-zero.
    set -l ok 0
    sudo dscacheutil -flushcache; or set ok 1
    sudo killall -HUP mDNSResponder; or set ok 1
    if test $ok -eq 0
        echo "DNS cache flushed."
    else
        echo "dnsflush: one or more steps failed" >&2
        return 1
    end
end
