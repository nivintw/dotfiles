<!--
SPDX-FileCopyrightText: © 2026 Tyler Nivin
SPDX-License-Identifier: MIT
-->

# Manual setup steps

[`install.sh`](install.sh) automates the whole machine — Homebrew, fish, casks,
fonts, symlinks, plugins, MCP servers, macOS defaults, and the Dock. The full
step-by-step flow lives in the docs, so it stays in one place:
**[getting started →](https://nivintw.github.io/dotfiles/getting-started.html)**.

This file is only the short list of things **no script can do for you** — the GUI
logins and one-time toggles. Work through them after the bootstrap finishes.

## After the bootstrap

- [ ] **Claude Code login** — the CLI is installed by `install.sh`, but first run
      needs a one-time browser login: run `claude` and sign in. The MCP servers are
      already registered; logging in is what lets you use them.
- [ ] **GitHub MCP token** — the GitHub MCP authenticates with a Personal Access
      Token (its OAuth path needs dynamic client registration, which
      `api.githubcopilot.com` doesn't support).
  - _With 1Password (personal default):_ store the PAT at
    `op://MCP/github-claude-pat/credential` (API Credential item, `credential` field),
    enable **1Password → Settings → Developer → Integrate with 1Password CLI**
    (+ Touch ID), then re-run `install.sh`. `op inject` bakes the token into
    `~/.claude.json`; rotate by updating 1Password and re-running.
  - _Without 1Password (e.g. a managed work box):_ export the PAT as
    `GITHUB_PERSONAL_ACCESS_TOKEN` (or `GH_TOKEN` / `GITHUB_TOKEN`) — e.g.
    `set -gx GITHUB_PERSONAL_ACCESS_TOKEN …` in `~/.config/dotfiles/local.fish` — and
    re-run `install.sh`; it wires the GitHub MCP server to that token.
- [ ] **1Password bundle** — on a personal machine, enable the `1password` opt-in
      bundle (it appears in the `fzf` picker on first run, or add `1password` to
      `~/.config/dotfiles/bundles`) to install the desktop app, `op` CLI, and Safari
      extension. Skip it on a machine that can't have 1Password — the install degrades
      gracefully (see the README's "No 1Password?" note).
- [ ] **VS Code** — sign in to sync extensions/settings (the app itself is a cask).
- [ ] **1Password browser extensions** — install the Chrome/Firefox extensions by hand
      (only the Safari one is automated, via `mas`); the desktop app prompts to connect
      them on first launch. Skip if you didn't enable the `1password` bundle.
- [ ] **AppCleaner SmartDelete** — open AppCleaner → Settings → enable
      **SmartDelete**. It installs a privileged background helper (admin auth
      required) so trashing an app auto-prompts to remove its leftover files. It
      can't be scripted via `defaults` — it's a one-time GUI toggle.
