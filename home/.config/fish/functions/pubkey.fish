# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function pubkey --description "Print an SSH public key and copy it to the clipboard"
    set -l key $argv[1]
    test -n "$key"; or set key ~/.ssh/id_ed25519_1password_personal.pub

    if not test -f $key
        echo "No such key: $key" >&2
        echo "Available public keys:" >&2
        ls ~/.ssh/*.pub 2>/dev/null >&2
        return 1
    end

    cat $key
    cat $key | pbcopy
    echo "(copied $key to clipboard)" >&2
end
