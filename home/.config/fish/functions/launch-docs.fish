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

    # Preflight: refuse a port already in use, so we don't open the browser at a server
    # that isn't ours (or crash python on bind). nc ships on macOS but isn't guaranteed on a
    # minimal Linux/WSL box — when it's absent we can't check, so skip the guard and let
    # python surface its own bind error rather than failing open on a bogus "port in use".
    if command -q nc; and nc -z localhost $port 2>/dev/null
        echo "launch-docs: port $port is already in use" >&2
        return 1
    end

    set -l url "http://localhost:$port"
    echo "Serving $docs at $url  (Ctrl-C to stop)"
    # Open the browser only once the server actually accepts connections, so the first load
    # never races the listener. With nc, poll the port directly — the same readiness check the
    # preflight uses — which opens the instant the listener is up, hard-bounded to ~10s. (curl's
    # --retry can't do this: --max-time bounds a single attempt, not the sequence.) Without nc,
    # we can't poll, so wait a beat for the bind and open best-effort. Backgrounded so the server
    # below keeps the foreground and Ctrl-C stops it cleanly. localhost is a secure context, so
    # the docs' Clipboard-API copy buttons work. __os_open dispatches open/xdg-open/wslview by OS.
    begin
        if command -q nc
            for attempt in (seq 100)
                if nc -z localhost $port 2>/dev/null
                    __os_open "$url"; or echo "launch-docs: couldn't auto-open a browser — open $url yourself" >&2
                    break
                end
                sleep 0.1
            end
        else
            sleep 1
            __os_open "$url"; or echo "launch-docs: couldn't auto-open a browser — open $url yourself" >&2
        end
    end &
    python3 -m http.server "$port" --directory "$docs"
end
