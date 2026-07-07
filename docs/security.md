# Security

## Secrets

No credential is ever committed. Secret-bearing config (the GitHub MCP token) is stored as a
1Password reference and resolved only at install time:

```json
"Authorization": "Bearer {{ op://MCP/github-claude-pat/credential }}"
```

`op inject` resolves it into `~/.claude.json` (mode `0600`) as you, using the desktop app's CLI
integration — the token never lands in the repo. On a machine without 1Password, the same
secret is sourced from a `GITHUB_PERSONAL_ACCESS_TOKEN` in the environment instead — the
tracked file keeps its `op://` placeholder either way.

## One sudo authentication, fenced off the bootstrappers

Touch ID for sudo is enabled *first*, then sudo is acquired **once** for the single privileged
block that runs *after* `brew bundle` — Touch ID PAM, `/etc/shells` + `chsh`, the firewall. On
a re-run you authenticate once — a fingerprint tap. It is deliberately *not* carried across
`brew bundle`: `brew bundle` invalidates the sudo timestamp, so a ticket acquired beforehand
would be gone by the time the bundle finishes — acquiring it *afterward* is what actually
yields a single prompt.

!!! note "What the fence still guarantees"
    The ticket is dropped (`sudo -k`) at the end of the privileged block, *before any
    `curl | bash` installer runs*. Homebrew and uv bootstrap before sudo is ever acquired;
    fisher and Claude Code after it's dropped — so those upstream installers never run with a
    warm sudo ticket, and a compromised or MITM'd one can't silently escalate. An `EXIT` trap
    drops the ticket even if the run aborts.

## SSH-host hygiene

The tracked `~/.ssh/config` holds only a generic `Host *` block, the `Include`, and
`Host github.com`. Real hosts, IPs, and usernames live in the untracked `~/.ssh/config.local`.
A custom `no-concrete-ssh-hosts` hook fails the commit when a concrete host slips into the
tracked config — a non-generic `Host`, a `HostName`/`User`, a
`ProxyJump`/`ProxyCommand`/`Match`/forward directive, or an IPv4/IPv6 literal. Tested both ways
(passes generic, fails on a planted host).

## Defense in depth

| Control | What it does |
| --- | --- |
| gitleaks | Scans every commit — and the whole history in CI — for secret &amp; token shapes before they can land |
| detect-private-key | Blocks committed private keys outright |
| App firewall + stealth (macOS) / ufw (Linux) | Enabled during the bootstrap — macOS stops answering pings/port scans; Linux gets default-deny-incoming via `ufw` (with an explicit SSH allow-rule first). WSL2 skips this — the Windows host owns the firewall. |
| Touch ID for sudo (macOS only) | Via `/etc/pam.d/sudo_local` (survives OS updates) + pam_reattach for tmux |
| `transfer.fsckObjects` | git validates object integrity on every fetch |
| Pinned CI binaries | Every release binary CI downloads (osv-scanner, hawkeye, taplo, gitleaks, bats) is checked against a committed SHA256 (or commit pin) before it runs |
| SSH commit signing | Commits are signed with a 1Password-held SSH key by default; a machine without 1Password gets signing disabled so commits still succeed |
