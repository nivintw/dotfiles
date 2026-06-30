# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function is_wsl --description "Exit 0 on a WSL (Windows Subsystem for Linux) kernel"
    # Mirrors src/dotfiles_install/os_detect.py::is_wsl — a Linux kernel whose
    # /proc/sys/kernel/osrelease advertises a Microsoft/WSL marker.
    test (uname) = Linux
    or return 1
    set -l osrelease /proc/sys/kernel/osrelease
    test -r $osrelease
    or return 1
    string match -qir 'microsoft|wsl' -- (cat $osrelease)
end
