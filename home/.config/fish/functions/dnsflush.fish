# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function dnsflush --description "Flush the macOS DNS cache"
    sudo dscacheutil -flushcache
    and sudo killall -HUP mDNSResponder
    and echo "DNS cache flushed."
end
