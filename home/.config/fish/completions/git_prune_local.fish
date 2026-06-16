# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

complete -c git_prune_local -f # no file arguments
complete -c git_prune_local -s h -l help -d "Show help and exit"
complete -c git_prune_local -s n -l dry-run -d "Show what would be deleted without deleting"
