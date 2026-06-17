# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function pubkey --description "Print an SSH public key and copy it to the clipboard"
    # Explicit path wins:  pubkey ~/.ssh/id_rsa.pub
    if test -n "$argv[1]"
        if not test -f $argv[1]
            echo "No such key: $argv[1]" >&2
            return 1
        end
        # `string collect -a` keeps the file contents as a single argument even
        # when empty or multi-line, so an empty/odd file can't shift $argv and
        # make the path get copied in place of the key (_pubkey_emit guards "").
        _pubkey_emit (cat $argv[1] | string collect -a) $argv[1]
        return
    end

    # With no path argument, discover the key automatically so the same command
    # works on every machine (personal w/ 1Password, work, or neither).
    #
    # Prefer a running agent: 1Password, the macOS keychain, and a plain
    # ssh-agent all answer `ssh-add -L` identically. A public-key line starts
    # with ssh- / ecdsa- / sk-, which also filters out the "agent has no
    # identities" message. The group is non-capturing and the .* consumes the
    # whole line, so `string match -r` returns each key line once, intact (a
    # capturing group would also emit the capture, duplicating every key).
    set -l keytypes '^(?:ssh-|ecdsa-|sk-).*'

    # Tier 1: whatever agent $SSH_AUTH_SOCK already points at (work ssh-agent, etc.).
    set -l keys (ssh-add -L 2>/dev/null | string match -r $keytypes)

    # Tier 2: the 1Password agent, if the default agent held nothing. The macOS
    # socket path is constant across Macs (2BUA8C4S2C is 1Password's Apple Team
    # ID); the second is the Linux/symlink location.
    if test (count $keys) -eq 0
        for sock in "$HOME/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock" "$HOME/.1password/agent.sock"
            test -S $sock; or continue
            set keys (SSH_AUTH_SOCK=$sock ssh-add -L 2>/dev/null | string match -r $keytypes)
            test (count $keys) -gt 0; and break
        end
    end

    if test (count $keys) -gt 0
        set -l key $keys[1]
        if test (count $keys) -gt 1
            # The raw "ssh-ed25519 AAAA…" blobs are visually identical, so present
            # a human label per key — its comment (e.g. the 1Password item name),
            # or the type + last 8 chars of the blob when it carries no comment —
            # with the SHA256 fingerprint appended as a tiebreaker. An index prefix
            # keeps every row unique.
            set -l labels
            for i in (seq (count $keys))
                set -l parts (string split ' ' -- $keys[$i])
                set -l label (string join ' ' -- $parts[3..-1])
                test -n "$label"; or set label "$parts[1] …"(string sub -s -8 -- $parts[2])
                set -l fp (printf '%s\n' $keys[$i] | ssh-keygen -lf - 2>/dev/null | string split ' ')[2]
                test -n "$fp"; and set label "$label  $fp"
                set -a labels (printf '%d. %s' $i $label)
            end
            # Map the choice back by its position in $labels rather than parsing
            # the printed text: immune to comments containing ". " and to fzf
            # quirks like FZF_DEFAULT_OPTS=--print-query (which prepends a line —
            # so take the last line as the selection). --no-multi forbids picking
            # several rows at once.
            set -l picked (printf '%s\n' $labels | fzf --no-multi --prompt="pubkey> ")
            set -l idx (contains -i -- "$picked[-1]" $labels)
            test -n "$idx"; or return 1
            set key $keys[$idx]
        end
        _pubkey_emit $key
        return
    end

    # Tier 3: no agent identities — fall back to *.pub files on disk. -L -type f
    # keeps real files (and symlinks to them) while dropping directories and
    # dangling symlinks; -print0 | string split0 survives odd filenames.
    set -l pubs (find -L ~/.ssh -maxdepth 1 -type f -name '*.pub' -print0 2>/dev/null | string split0)
    if test (count $pubs) -eq 0
        echo "No SSH keys found (no agent identities, no ~/.ssh/*.pub)." >&2
        echo "Usage: pubkey [path-to-public-key]" >&2
        return 1
    end
    set -l file $pubs[1]
    if test (count $pubs) -gt 1
        set -l picked (printf '%s\n' $pubs | fzf --no-multi --prompt="pubkey> ")
        set file $picked[-1]
    end
    test -n "$file"; or return 1
    _pubkey_emit (cat $file | string collect -a) $file
end

function _pubkey_emit --description "Print a public key, copy it to the clipboard, and report"
    set -l key (string trim -- $argv[1])
    set -l label $argv[2]
    if test -z "$key"
        echo "pubkey: no key to copy" >&2
        return 1
    end
    printf '%s\n' $key
    printf '%s' $key | pbcopy
    if test -n "$label"
        echo "(copied $label to clipboard)" >&2
    else
        echo "(copied to clipboard)" >&2
    end
end
