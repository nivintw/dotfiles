# Security

A dotfiles repo is a high-value target: it touches credentials, SSH, sudo, and runs `curl | bash` bootstraps. The posture here treats all of that as hostile-by-default.

## Secrets are references, not values

No credential is ever committed. Secret-bearing config (the GitHub MCP token) is stored as a [**1Password reference**](https://1password.com/) and resolved only at install time:

```json
"Authorization": "Bearer {{ op://MCP/github-claude-pat/credential }}"
```

`op inject` resolves it into `~/.claude.json` (mode `0600`) as you, using the desktop app's CLI integration — the token never lands in the repo. Rotate by updating 1Password and re-running. A [pytest](https://docs.pytest.org/) invariant asserts the auth header stays an `op://` reference, a rule [gitleaks](https://github.com/gitleaks/gitleaks) alone can't know.

On a machine without 1Password, the same secret is sourced from a `GITHUB_PERSONAL_ACCESS_TOKEN` in the environment instead — it still only ever lands in `~/.claude.json`, and the tracked file keeps its `op://` placeholder, so the committed config stays token-free either way.

## One sudo authentication, fenced off the bootstrappers

Touch ID for sudo is enabled *first*, then sudo is acquired **once** for the single privileged block that runs *after* `brew bundle` — Touch ID PAM, `/etc/shells` + `chsh`, the firewall. On a re-run you authenticate **once** — a fingerprint tap. A fresh machine costs a little more (a typed password to write the Touch-ID PAM file, since Touch ID can't yet authorize enabling itself, then this one acquisition), but never the old per-cask string of password prompts. It is deliberately *not* carried across `brew bundle`: `brew bundle` invalidates the sudo timestamp (confirmed for both the tty-keyed default and a global one, and not via any `sudo -k`), so a ticket acquired beforehand would be gone by the time the bundle finishes — acquiring it *afterward* is what actually yields a single prompt.

!!! note "What the fence still guarantees"

    The ticket is dropped (`sudo -k`) at the end of the privileged block, **before any `curl | bash` installer runs**. [Homebrew](https://brew.sh) and [uv](https://docs.astral.sh/uv/) bootstrap before sudo is ever acquired; [fisher](https://github.com/jorgebucaran/fisher) and [Claude Code](https://github.com/anthropics/claude-code) after it's dropped — so those upstream installers **never run with a warm sudo ticket**, and a compromised or MITM'd one can't silently escalate. An `EXIT` trap drops the ticket even if the run aborts. The honest tradeoff: on a *fresh* machine a cask that ships a privileged `.pkg` still prompts during `brew bundle` — a fingerprint tap once Touch ID is effective, but a typed password inside [tmux](https://github.com/tmux/tmux)/screen, where the [pam_reattach](https://github.com/fabianishere/pam_reattach) that Touch ID needs in a multiplexer isn't installed until the bundle itself — and it can't be folded into the single authentication because brew invalidates the timestamp; Homebrew verifies cask/bottle checksums before running them.

## SSH-host hygiene

The tracked `~/.ssh/config` holds only a generic `Host *` block, the `Include`, and `Host github.com`. Real hosts, IPs, and usernames live in the untracked `~/.ssh/config.local`.

!!! note "Checked on every commit"

    A custom **`no-concrete-ssh-hosts`** hook fails the commit when a concrete host slips into the tracked config — a non-generic `Host`, a `HostName`/`User`, a `ProxyJump`/`ProxyCommand`/`Match`/forward directive, or an IPv4/IPv6 literal. A backstop for the common shapes, not a guarantee against every hand-crafted line; tested both ways (passes generic, fails on a planted host).

## Defense in depth

| Control | What it does |
|---------|--------------|
| **gitleaks** | Scans every commit for secret & token shapes before they can land |
| **detect-private-key** | Blocks committed private keys outright |
| **App firewall + stealth** *(macOS)* / **ufw** *(Linux)* | Enabled during the bootstrap — macOS stops answering pings/port scans; Linux gets default-deny-incoming via `ufw` (with an explicit SSH allow-rule first, so an active session can't be locked out). WSL2 skips this entirely — the Windows host owns the firewall. |
| **Touch ID for sudo** *(macOS only)* | Via `/etc/pam.d/sudo_local` (survives OS updates) + [pam_reattach](https://github.com/fabianishere/pam_reattach) for [tmux](https://github.com/tmux/tmux) |
| **`transfer.fsckObjects`** | git validates object integrity on every fetch — supply-chain hygiene |
| **Pinned CI binaries** | Every release binary CI downloads (gitleaks, osv-scanner, hawkeye, taplo) is checked against a committed SHA256 via `sha256sum -c` before it runs; [`scripts/refresh-binary-checksums.sh`](https://github.com/nivintw/dotfiles/blob/main/scripts/refresh-binary-checksums.sh) keeps the pins in step with version bumps and refuses to re-pin a tampered asset whose version didn't change — supply-chain integrity for the toolchain |
| **SSH commit signing** | Commits are signed with a 1Password-held SSH key (`op-ssh-sign`) by default; on a machine without 1Password, `install.sh` disables signing in `~/.gitconfig_local` so commits still succeed |
