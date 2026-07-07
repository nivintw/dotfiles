# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function __clipboard_copy --description "Copy stdin to the system clipboard (macOS/Linux/WSL)"
    # Cross-platform replacement for a bare `pbcopy`. macOS has pbcopy; WSL reaches the
    # Windows clipboard (win32yank preferred, else clip.exe); Linux uses the Wayland
    # (wl-copy) or X11 (xclip/xsel) tool that's installed.
    if is_macos
        pbcopy
    else if is_wsl; and command -q win32yank.exe
        # Prefer win32yank on WSL: it writes the clipboard via the Unicode API (codepage-clean,
        # so non-ASCII round-trips) and stores stdin verbatim — no --crlf, so it can't append
        # the trailing CR that clip.exe does.
        win32yank.exe -i
    else if is_wsl; and command -q win32yank
        win32yank -i
    else if is_wsl; and command -q clip.exe
        # Fallback: clip.exe mangles non-ASCII (codepage) and appends a CR, but it's always
        # present on WSL when win32yank isn't installed.
        clip.exe
    else if command -q wl-copy; and set -q WAYLAND_DISPLAY
        # Only attempt wl-copy under an actual Wayland session; on a display-less box it
        # would fail, so fall through to xsel/xclip below.
        wl-copy
    else if command -q xclip
        xclip -selection clipboard
    else if command -q xsel
        xsel --clipboard --input
    else
        # No clipboard tool. Drain a *piped* stdin so the upstream `printf … |` producer
        # doesn't see a broken pipe — but never `cat` an interactive tty, which would block
        # the shell waiting for Ctrl-D. Either way, report failure.
        isatty stdin; or command cat >/dev/null
        return 1
    end
end
