<!--
SPDX-FileCopyrightText: © 2026 Tyler Nivin
SPDX-License-Identifier: MIT
-->

# Manual setup steps

Most of a new machine is automated by [`install.sh`](install.sh), which:

- groups every step that needs **sudo** (Touch ID PAM, `/etc/shells` + `chsh`,
  firewall) into one block right after `brew bundle`, so you authenticate once —
  and the `curl | bash` bootstraps never run with a warm sudo ticket
- installs **Homebrew** and **uv** if they're missing
- runs `brew bundle` ([Brewfile](Brewfile)) — all CLI tools, **fish**, GUI app
  casks, and the **MesloLGS NF** font (`font-meslo-for-powerlevel10k` cask)
- enables **Touch ID for sudo** via `/etc/pam.d/sudo_local` (with `pam_reattach`
  so it works inside tmux too)
- makes **fish** the default login shell (`/etc/shells` + `chsh`; prompts for sudo)
- symlinks dotfiles into `$HOME` with `stow`
- creates an empty untracked **`~/.ssh/config.local`** (the tracked `~/.ssh/config`
  `Include`s it for machine-local host entries)
- bootstraps **fisher** and runs `fisher update` — all fish plugins from
  `home/.config/fish/fish_plugins` (tide, fzf.fish)
- installs **TPM** and the **tmux plugins** declared in
  `home/.config/tmux/tmux.conf` (extrakto, tmux-yank, vim-tmux-navigator)
- points **iTerm2** at the tracked prefs folder (`iterm2/`); takes effect on
  iTerm's next launch
- installs the **uv tools** listed in [uv_tools.txt](uv_tools.txt)
- configures the **prek git template dir** (`~/.config/git/template`) so cloning
  a repo with a pre-commit config auto-installs its hooks (`init.templateDir` in
  `.gitconfig`). Tradeoff: a malicious config in an untrusted clone would run on
  first commit — accepted since only trusted repos are cloned here
- installs the **Claude Code CLI** via the native installer
  (`~/.local/bin/claude`), which self-updates thereafter — chosen over a brew
  cask precisely so it stays current automatically
- registers the **Claude Code MCP servers** declared in
  [claude_mcp.json](claude_mcp.json) (user scope). Secret-backed servers
  (e.g. GitHub) need 1Password CLI signed in (see the GitHub MCP step below)
- applies **macOS defaults** ([macos.sh](macos.sh)), enables the **application
  firewall + stealth mode**, and sets the **Dock layout** ([dock.sh](dock.sh))

zoxide is **not** a fisher plugin anymore — it's installed standalone via the
Brewfile and initialized in `config.fish` (`zoxide init fish | source`).

Fish is brew-installed now; the only catch is that a `brew upgrade` can disturb
an already-open fish session until it's restarted. Minor, accepted tradeoff.

## Run the bootstrap

No prerequisites — `install.sh` installs Homebrew and uv itself if they're missing.

```bash
~/dotfiles/install.sh
```

## After (steps no script can do for you)

- [ ] **Claude Code login** — the CLI is installed automatically by `install.sh`
      (native installer). First run needs a one-time browser login: run `claude`
      and sign in. MCP servers are already registered by the script; logging in
      is what lets you actually use Claude Code.
- [ ] **GitHub MCP token** — the GitHub MCP authenticates with a Personal Access
      Token (its OAuth path needs dynamic client registration, which the
      `api.githubcopilot.com` endpoint doesn't support). Store the PAT in
      1Password at `op://MCP/github-claude-pat/credential` (API Credential item,
      `credential` field), enable **1Password → Settings → Developer → Integrate
      with 1Password CLI** (+ Touch ID), then re-run `install.sh`. `op inject`
      bakes the token into `~/.claude.json`; rotate by updating 1Password and
      re-running.
- [ ] **VS Code** — sign in to sync extensions/settings (the app itself is a cask).
- [ ] **1Password browser extensions** (the desktop app is a cask).
- [ ] **AppCleaner SmartDelete** — open AppCleaner → Settings → enable
      **SmartDelete**. This installs a privileged background helper (admin auth
      required) so dragging an app to the Trash auto-prompts to remove its
      leftover files. It can't be scripted via `defaults` — it's a one-time GUI
      toggle.

## Notes on a couple of new tools

- **atuin** owns **Ctrl+R** (SQLite history search). Up-arrow stays normal fish
  history. To revert, see the header of `home/.config/fish/conf.d/zz-atuin.fish`.
- **eza** aliases `ls`/`ll`/`la`/`lt` (interactive shells only). If your VS Code
  terminal font lacks Nerd Font glyphs and shows boxes, switch `--icons=auto` to
  `--icons=never` in `home/.config/fish/conf.d/aliases.fish`.
- **Prettier vs rumdl (VS Code):** both can format Markdown, so rumdl owns `.md`
  and Prettier handles everything else. This is already configured in the stowed
  `settings.json` (`[markdown].editor.defaultFormatter` → `rvben.rumdl`,
  `prettier.disableLanguages: ["markdown"]`).
- **VS Code settings and Settings Sync:** `settings.json` is stowed from
  `home/Library/Application Support/Code/User/settings.json`. If you also have
  Settings Sync enabled, syncing from another machine will overwrite the stowed
  file (VS Code writes through the symlink, so changes land in the repo — but a
  *pull* from the cloud wins). Pick one source of truth: dotfiles repo OR Settings
  Sync, not both for the same file.
