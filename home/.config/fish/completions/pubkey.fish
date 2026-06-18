# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# Optional argument is a path to a public-key file. Surface ~/.ssh/*.pub as
# candidates while leaving normal path completion in place for keys elsewhere.
complete -c pubkey -a "(ls ~/.ssh/*.pub 2>/dev/null)" -d "SSH public key"
