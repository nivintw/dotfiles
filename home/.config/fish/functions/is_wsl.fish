# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function is_wsl --description "Exit 0 on a WSL (Windows Subsystem for Linux) kernel"
    # Mirrors src/dotfiles_install/os_detect.py::is_wsl. Three conclusive signals, in order: the
    # $WSL_DISTRO_NAME env fast-path (exported inside every WSL distro), then a Microsoft/WSL
    # marker in /proc/sys/kernel/osrelease OR /proc/version (Microsoft's canonical recommended
    # marker — catches variants the single osrelease check misses). Both files stay overridable
    # ($__dotfiles_osrelease / $__dotfiles_proc_version) so the bats suite can point them at
    # fixtures on any host — the same reason the Python twin's _WSL_OSRELEASE/_WSL_VERSION are.
    test (uname) = Linux
    or return 1
    set -q WSL_DISTRO_NAME; and test -n "$WSL_DISTRO_NAME"
    and return 0
    set -l osrelease /proc/sys/kernel/osrelease
    set -q __dotfiles_osrelease
    and set osrelease $__dotfiles_osrelease
    # NB: `version` is a fish reserved read-only variable (the shell's own version), so the
    # local for /proc/version must be named something else.
    set -l procver /proc/version
    set -q __dotfiles_proc_version
    and set procver $__dotfiles_proc_version
    for src in $osrelease $procver
        test -r $src
        or continue
        string match -qir 'microsoft|wsl' -- (cat $src)
        and return 0
    end
    return 1
end
