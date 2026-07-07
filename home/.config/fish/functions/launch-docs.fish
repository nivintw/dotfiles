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

    # Resolve docs/ without hardcoding ~/dotfiles: honor $DOTFILES, then a docs/ in
    # the current repo (so it works from any worktree you're cd'd into), then the
    # conventional checkout.
    set -l toplevel (git rev-parse --show-toplevel 2>/dev/null)
    set -l docs
    for cand in "$DOTFILES/docs" "$toplevel/docs" "$HOME/dotfiles/docs"
        if test -d "$cand"
            set docs "$cand"
            break
        end
    end
    if test -z "$docs"
        echo "launch-docs: docs site not found (set \$DOTFILES or run from the dotfiles repo)" >&2
        return 1
    end

    # A dependency-free port probe: exit 0 iff something is already accepting TCP
    # connections on the port. Uses python3 — already required to run the server below — so
    # the check behaves identically across macOS/Linux/WSL instead of depending on `nc`,
    # which ships on macOS but isn't guaranteed on a minimal Linux/WSL box (when it was
    # absent the old code couldn't probe at all and raced the listener). connect_ex returns 0
    # on a successful connect (listener up / port in use), non-zero otherwise.
    set -l probe 'import socket, sys
s = socket.socket()
s.settimeout(0.3)
sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)'

    # Preflight: refuse a port already in use, so we don't open the browser at a server that
    # isn't ours (or crash python on bind).
    if python3 -c "$probe" $port 2>/dev/null
        echo "launch-docs: port $port is already in use" >&2
        return 1
    end

    set -l url "http://localhost:$port"
    echo "Serving $docs at $url  (Ctrl-C to stop)"
    # Open the browser only once the server actually accepts connections, so the first load
    # never races the listener. Poll the port with the same python3 probe the preflight uses
    # — it opens the instant the listener is up, hard-bounded to ~10s. Backgrounded so the
    # server below keeps the foreground and Ctrl-C stops it cleanly. localhost is a secure
    # context, so the docs' Clipboard-API copy buttons work. __os_open dispatches
    # open/xdg-open/wslview by OS.
    begin
        for attempt in (seq 100)
            if python3 -c "$probe" $port 2>/dev/null
                __os_open "$url"; or echo "launch-docs: couldn't auto-open a browser — open $url yourself" >&2
                break
            end
            sleep 0.1
        end
    end &
    python3 -m http.server "$port" --directory "$docs"
end
