# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function __os_open --description "Open a URL or file in the OS default handler (macOS/Linux/WSL)"
    # Cross-platform replacement for a bare `open`. macOS has open; WSL hands off to
    # Windows via wslview (wslu) or explorer.exe; Linux uses xdg-open. Each handles both
    # URLs and file paths. Returns non-zero when no handler is available, so callers can
    # fall back (or simply not open) instead of erroring.
    if is_macos
        open $argv
    else if is_wsl; and command -q wslview
        wslview $argv
    else if is_wsl; and command -q explorer.exe
        explorer.exe $argv
    else if command -q xdg-open
        xdg-open $argv
    else
        return 1
    end
end
