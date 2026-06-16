# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function launch-docs --description "Serve the dotfiles docs/ site locally (python http.server)"
    set -l port 8000
    if set -q argv[1]
        set -l p $argv[1]
        if not string match -qr '^[0-9]+$' -- $p; or test $p -lt 1; or test $p -gt 65535
            echo "usage: launch-docs [port]   (port must be 1-65535; default 8000)" >&2
            return 2
        end
        set port $p
    end

    set -l docs "$HOME/dotfiles/docs"
    if not test -d "$docs"
        echo "launch-docs: docs site not found at $docs" >&2
        return 1
    end

    # Preflight: refuse a port already in use, so we don't open the browser at a
    # server that isn't ours (or crash python on bind). (nc is part of macOS.)
    if nc -z localhost $port 2>/dev/null
        echo "launch-docs: port $port is already in use" >&2
        return 1
    end

    set -l url "http://localhost:$port"
    echo "Serving $docs at $url  (Ctrl-C to stop)"
    # Open the browser only once the server actually accepts connections, so the
    # first load never races the listener. Backgrounded so the server below stays
    # in the foreground and Ctrl-C stops it cleanly. localhost is a secure context,
    # so the docs' Clipboard-API copy buttons work.
    if type -q open
        begin
            curl -s --retry 30 --retry-delay 0 --retry-connrefused --max-time 10 -o /dev/null "$url"
            and open "$url"
        end &
    end
    python3 -m http.server "$port" --directory "$docs"
end
