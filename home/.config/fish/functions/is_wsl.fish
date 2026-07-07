# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function is_wsl --description "Exit 0 on a WSL (Windows Subsystem for Linux) kernel"
    # Mirrors src/dotfiles_install/os_detect.py::is_wsl — a Linux kernel running under WSL.
    # Three markers, any one is sufficient (checked cheapest-first):
    #   1. $WSL_DISTRO_NAME — an env fast-path WSL always exports; needs no file read.
    #   2. /proc/version — Microsoft's canonical recommended WSL marker.
    #   3. /proc/sys/kernel/osrelease — the original single-file check.
    # Both proc paths are overridable via $__dotfiles_osrelease / $__dotfiles_procversion so
    # the bats suite can point them at fixtures and exercise the marker match on any host —
    # the same reason the Python twin's _WSL_OSRELEASE / _WSL_PROCVERSION are repointable.
    test (uname) = Linux
    or return 1
    # Env fast-path: WSL exports $WSL_DISTRO_NAME (e.g. "Ubuntu") into every shell.
    set -q WSL_DISTRO_NAME; and test -n "$WSL_DISTRO_NAME"
    and return 0
    set -l osrelease /proc/sys/kernel/osrelease
    set -q __dotfiles_osrelease
    and set osrelease $__dotfiles_osrelease
    set -l procversion /proc/version
    set -q __dotfiles_procversion
    and set procversion $__dotfiles_procversion
    for marker_file in $procversion $osrelease
        test -r $marker_file
        or continue
        string match -qir 'microsoft|wsl' -- (cat $marker_file)
        and return 0
    end
    return 1
end
