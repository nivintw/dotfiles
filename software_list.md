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
      `api.githubcopilot.com` doesn't support). Store the PAT in 1Password at
      `op://MCP/github-claude-pat/credential` (API Credential item, `credential`
      field), enable **1Password → Settings → Developer → Integrate with 1Password
      CLI** (+ Touch ID), then re-run `install.sh`. `op inject` bakes the token into
      `~/.claude.json`; rotate by updating 1Password and re-running.
- [ ] **VS Code** — sign in to sync extensions/settings (the app itself is a cask).
- [ ] **1Password browser extensions** — install them (the desktop app is a cask).
- [ ] **AppCleaner SmartDelete** — open AppCleaner → Settings → enable
      **SmartDelete**. It installs a privileged background helper (admin auth
      required) so trashing an app auto-prompts to remove its leftover files. It
      can't be scripted via `defaults` — it's a one-time GUI toggle.
