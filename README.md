<!--
SPDX-FileCopyrightText: © 2026 Tyler Nivin
SPDX-License-Identifier: MIT
-->

<!-- rumdl-disable-file MD033 MD041 -->
<!-- README hero uses a centered HTML block (MD033) and so doesn't open with an
     H1 on line 1 (MD041); both are intentional and scoped to this file. -->

<div align="center">

# 🍎 dotfiles

**_Setting up my new computer: clone. run. done._**

The one repo I clone onto every machine I own — Mac, Linux, or WSL2 — and it's
**built to be forked.**

[![CI](https://github.com/nivintw/dotfiles/actions/workflows/main.yml/badge.svg)](https://github.com/nivintw/dotfiles/actions/workflows/main.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![REUSE compliant](https://api.reuse.software/badge/github.com/nivintw/dotfiles)](https://api.reuse.software/info/github.com/nivintw/dotfiles)
![macOS](https://img.shields.io/badge/macOS-000000?logo=apple&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?logo=linux&logoColor=black)
![WSL2](https://img.shields.io/badge/WSL2-4D4D4D?logo=windowsterminal&logoColor=white)

**[📖 Read the docs →](https://nivintw.github.io/dotfiles/)**

</div>

---

## ⚡ Quick start

No toolchain to install first — `install.sh` bootstraps Homebrew and uv itself.

```bash
git clone https://github.com/nivintw/dotfiles ~/dotfiles
~/dotfiles/install.sh
```

That one command converges a fresh machine to my exact setup: CLI tools, fish,
and — on macOS — GUI apps, the MesloLGS NF font, macOS defaults, and the Dock.
On Linux and WSL2 it runs the same OS-agnostic core (Homebrew/Linuxbrew, fish,
Stow, tmux, Claude Code, …); the macOS-only steps just skip themselves. It's
safe to re-run — it _converges_ the machine to the declared state rather than
clobbering what's there.

> **Forking?** `install.sh` installs _my_ taste — package list, Dock, keys, macOS
> defaults. Review and edit those before you run it.
> → **[Make it yours](https://nivintw.github.io/dotfiles/getting-started.html#make-it-yours)**

---

## ✨ What makes it tick

| Feature | What it gives you |
| --- | --- |
| 🔗 **GNU Stow** | `home/` mirrors `$HOME` via symlinks — editing `~/.config/fish/config.fish` edits the repo file directly. |
| ♻️ **Idempotent bootstrap** | Re-run `install.sh` anytime; it adopts existing packages and symlinks instead of clobbering them. |
| 🧩 **Machine-local overlays** | One branch across every machine — work box, homelab, personal — with nothing machine-specific leaking into the public repo. |
| ✅ **Quality gate** | A prek hook suite (lint, format, license, spelling) plus bats and pytest — run identically by you locally and by CI on every PR — CI installer-smoke jobs that run `install.sh --core` end-to-end on ephemeral macOS _and_ Linux runners, and an opt-in local Tart VM harness (macOS or Linux) that does it twice to prove idempotency. |
| 🎬 **Live demos** | asciinema casts of the fish functions actually running, embedded on the docs site. |
| 🤖 **Local AI fleet** | Role-based Ollama models (fast / bulk / brainstorm / vision) provisioned by the installer; the `ollm` CLI routes mechanical work to them, GitLens gets offline AI, and a session-start hook shows Claude Code the live roster. |

---

## 🗂️ Repo layout

- **`home/`** — mirrors `$HOME`, symlinked into place with [GNU Stow](https://www.gnu.org/software/stow/).
- **`Brewfile`** — formulae + casks, installed with `brew bundle`.
- **`Brewfile.d/*.brewfile`** — tracked, opt-in bundles (e.g. `personal`, `homelab`, `1password`), picked from an `fzf` multi-select (re-runs pre-seed your current pick; `--bundle`/`--no-bundles` skip it for scripts, `--keep-bundles` reuses the saved pick unchanged).
- **`uv_tools.txt`** — Python tools, one `uv tool install` arg-list per line.
- **`claude_mcp.json`** — Claude Code MCP servers; the GitHub token is a 1Password reference resolved at install time — or, on a machine without 1Password, a `GITHUB_PERSONAL_ACCESS_TOKEN` read from the environment — so no token is ever committed.
- **`iterm2/`** — iTerm2 preferences (pointed at directly, not stowed).
- **`software_list.md`** — the few human-only steps Brewfile and stow can't automate.

> Full reference — install flow, architecture, every command — lives on the
> **[documentation site →](https://nivintw.github.io/dotfiles/)**.

---

## 🧩 Machine-local overlays

The tracked files are a generic baseline. Anything machine-specific lives in
**untracked files outside the repo** that the tracked config reads — so one branch
runs everywhere, `git pull` never conflicts, and nothing private ever lands in the
public repo. `install.sh` creates each file empty on first run; fill in what a
given machine needs.

| Tool | Tracked baseline | Local overlay (untracked) | Wiring |
| --- | --- | --- | --- |
| **SSH** | `home/.ssh/config` | `~/.ssh/config.local` | `Include`d by the tracked config |
| **git** | `home/.gitconfig` | `~/.gitconfig_local` | `[include]`d **last** by the tracked config (overlay wins for every key, incl. identity) |
| **fish** | `home/.config/fish/**` | `~/.config/dotfiles/local.fish` | sourced by `conf.d/zzz-local.fish` |
| **Homebrew** | `Brewfile` + `Brewfile.d/*` | `~/.config/dotfiles/Brewfile.local` | auto-loaded by `install.sh` |
| **Claude memory** | `home/.claude/CLAUDE.md` | `~/.config/dotfiles/CLAUDE.local.md` | `@`-imported by the tracked `CLAUDE.md` |
| **Claude settings** | `claude_settings.json` | `~/.config/dotfiles/claude_settings.local.json` | deep-merged by `install.sh` (arrays union); written to a real `~/.claude/settings.json` |
| **Claude MCP** | `claude_mcp.json` | `~/.config/dotfiles/claude_mcp.local.json` | deep-merged by `install.sh` |
| **macOS defaults** | `macos.sh` | `~/.config/dotfiles/macos.local.sh` | sourced by `macos.sh` |

**No 1Password?** The baseline keeps 1Password as the personal default (SSH commit
signing, the `op://` MCP token, the desktop app). On a machine without it, the install
degrades gracefully: 1Password is an opt-in `1password` bundle (so it's simply not
installed), `install.sh` disables commit signing in `~/.gitconfig_local`, and the
GitHub MCP server falls back to a `GITHUB_PERSONAL_ACCESS_TOKEN` from the environment.

**Git identity lives in the overlay.** The tracked `home/.gitconfig` ships **no**
`[user]` block — set your `name`/`email`/`signingkey` in `~/.gitconfig_local`
(`install.sh` seeds it with a commented stanza). On a fresh machine that already
has a real `~/.gitconfig`, `install.sh` **backs it up** to `~/.gitconfig.pre-stow.bak`
and folds its contents into `~/.gitconfig_local` before stowing — so nothing is
stomped and your existing settings keep applying (and override the baseline).

**Per-directory git identity** — the clean way to use a work email and signing key
only inside work repos:

```gitconfig
# in ~/.gitconfig_local (untracked)
[includeIf "gitdir:~/work/"]
    path = ~/.gitconfig.work   # work email, signing key, etc.
```

---

## 🔄 Day to day

- **New CLI tool or app** — add a `brew`/`cask` line to the `Brewfile`, then
  `brew bundle install --file=~/dotfiles/Brewfile`.
- **Dotfile change** — just edit the file under `home/` (or its symlink in `$HOME`
  — same file) and commit.
- **Prune candidates** — `brew bundle cleanup --file=~/dotfiles/Brewfile` shows
  what's installed but no longer tracked.

---

## 🧹 Uninstalling

`~/dotfiles/uninstall.sh` is the safe reverse of the install. Preview it with
`--dry-run` (it changes nothing), then run it for real. It removes only what the
installer demonstrably owns (stow symlinks, MCP registrations, the iTerm2 pointer),
_offers_ to remove things it can't prove it owns (the TPM clone, uv tools, Ollama
models), _asks_ before lossy system changes (login shell, the Touch-ID PAM file), and never
deletes your machine-local data — it lists what it leaves behind with copy-paste
commands to finish by hand.

---

## 📄 License

[MIT](LICENSE) — and [REUSE](https://reuse.software)-compliant, so every file
carries its own copyright and license. Fork it, adapt it, make it yours.
