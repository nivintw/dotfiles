# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function is_wsl --description "Exit 0 on a WSL (Windows Subsystem for Linux) kernel"
    # Mirrors src/dotfiles_install/os_detect.py::is_wsl — a Linux kernel whose
    # /proc/sys/kernel/osrelease advertises a Microsoft/WSL marker. The path is overridable via
    # $__dotfiles_osrelease so the bats suite can point it at a fixture and exercise the marker
    # match on any host — the same reason the Python twin's _WSL_OSRELEASE is repointable.
    test (uname) = Linux
    or return 1
    set -l osrelease /proc/sys/kernel/osrelease
    set -q __dotfiles_osrelease
    and set osrelease $__dotfiles_osrelease
    test -r $osrelease
    or return 1
    string match -qir 'microsoft|wsl' -- (cat $osrelease)
end
