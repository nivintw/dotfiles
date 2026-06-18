# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# fkill takes an optional leading signal (number like 9 or name like TERM); the
# process picker is fzf, so there are no further completable arguments. Offer the
# signal names this host knows, derived from `kill -l` exactly as fkill validates
# them (keep alphabetic tokens, dropping any GNU-format ordinals).
complete -c fkill -x -a "(kill -l 2>/dev/null | string split -n ' ' | string match -r '^[A-Za-z][A-Za-z0-9]*')"
