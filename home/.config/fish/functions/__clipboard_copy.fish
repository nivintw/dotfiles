# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function __clipboard_copy --description "Copy stdin to the system clipboard (macOS/Linux/WSL)"
    # Cross-platform replacement for a bare `pbcopy`. macOS has pbcopy; WSL reaches the
    # Windows clipboard via clip.exe; Linux uses the Wayland (wl-copy) or X11 (xclip/xsel)
    # tool that's installed.
    if is_macos
        pbcopy
    else if is_wsl; and command -q clip.exe
        clip.exe
    else if command -q wl-copy
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
