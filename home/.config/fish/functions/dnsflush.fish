# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function dnsflush --description "Flush the DNS resolver cache (macOS / systemd-resolved)"
    if is_macos
        # Both steps are independent and both matter (the killall is what actually
        # refreshes the resolver), so run them unconditionally — chaining with `and`
        # would skip the killall whenever the flush returned non-zero.
        set -l ok 0
        sudo dscacheutil -flushcache; or set ok 1
        sudo killall -HUP mDNSResponder; or set ok 1
        if test $ok -eq 0
            echo "DNS cache flushed."
            return 0
        end
        echo "dnsflush: one or more steps failed" >&2
        return 1
    else if is_wsl
        # WSL must be checked BEFORE resolvectl: modern WSL2 ships systemd-resolved, so
        # resolvectl is present — but flushing it is pointless, because name resolution on WSL
        # is handled by the Windows host. Flushing the Linux cache wouldn't fix a stale lookup.
        echo "dnsflush: on WSL, DNS is the Windows host's job — flush it from Windows (run 'ipconfig /flushdns')." >&2
        return 1
    else if command -q resolvectl
        # systemd-resolved is the common Linux resolver-cache owner.
        if sudo resolvectl flush-caches
            echo "DNS cache flushed (systemd-resolved)."
            return 0
        end
        echo "dnsflush: resolvectl flush-caches failed" >&2
        return 1
    else if command -q systemd-resolve
        # Older systemd (pre-resolvectl) ships the legacy `systemd-resolve --flush-caches`
        # binary instead — same resolver cache, older CLI.
        if sudo systemd-resolve --flush-caches
            echo "DNS cache flushed (systemd-resolve)."
            return 0
        end
        echo "dnsflush: systemd-resolve --flush-caches failed" >&2
        return 1
    else
        # Plain Linux without systemd-resolved.
        echo "dnsflush: no supported DNS cache to flush on this system" >&2
        return 1
    end
end
