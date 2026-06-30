# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function is_linux --description "Exit 0 on a non-WSL Linux kernel"
    # WSL is reported separately (is_wsl) so callers can pick Windows-interop tools
    # there; this is true only on a "plain" Linux kernel, mirroring os_detect.py's
    # LINUX-vs-WSL split.
    test (uname) = Linux
    and not is_wsl
end
