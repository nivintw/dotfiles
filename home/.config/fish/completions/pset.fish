# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# Single argument is an environment variable NAME. Offer existing variable names
# (you often re-set one); -x since it never takes a file.
complete -c pset -x -a "(set --names)" -d "Variable name"
