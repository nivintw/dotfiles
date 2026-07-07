# Getting Started

On my own machines this is the whole story: clone, run, done — no toolchain to set up first, since `install.sh` installs [Homebrew](https://brew.sh) and [uv](https://docs.astral.sh/uv/) if they're missing. If you're adopting it, there's one step before that: [make it yours](#make-it-yours).

Runs the same way on **macOS, Linux, and WSL2** — the steps below marked *macOS only* just skip themselves everywhere else.

```bash
git clone https://github.com/nivintw/dotfiles ~/dotfiles
~/dotfiles/install.sh
```

!!! note "It's idempotent — re-run it any time"

    `install.sh` converges the machine to the declared state instead of clobbering it: `brew bundle` adopts already-installed casks in place, `stow` refuses to overwrite existing real files, and the MCP/symlink/shell steps no-op once they're done. The two declarative system steps are the deliberate exception — `macos.sh` re-asserts its preferences and `dock.sh` rebuilds the Dock from its list every run (pass `--no-dock` to skip it, or it skips itself if `dockutil` can't read the current Dock state). That's by design: they reset those surfaces to the repo's definition rather than preserving local tweaks.

## What the bootstrap does

In order — privileged steps are grouped into a single `sudo` session so you authenticate once.

| # | Step | What happens |
|---|------|--------------|
| 0 | Toolchain | Install Homebrew & uv if missing |
| 1 | `brew bundle` | All baseline CLI tools, [fish](https://fishshell.com/) and [zsh](https://www.zsh.org/), GUI casks, the [MesloLGS NF](https://github.com/ryanoasis/nerd-fonts) font — then an [fzf](https://github.com/junegunn/fzf) multi-select for opt-in bundles (`personal`, `homelab`, `1password`) |
| 2 | Shell selection | Resolve the login shell — fish by default, or zsh if you pass `--shell zsh` — and persist the choice to `~/.config/dotfiles/shell` so a plain re-run repeats it |
| 3 | Privileged block | The resolved shell as login shell everywhere, plus one sudo prompt for the OS-specific bit: Touch ID for sudo & the app firewall + stealth mode (macOS), `ufw` (native Linux), or nothing (WSL2 — the Windows host owns the firewall) |
| 4 | [Stow](https://www.gnu.org/software/stow/) | Symlink `home/` into `$HOME` — both shells' config trees, regardless of which is selected |
| 5 | Overlays | Seed untracked machine-local overlay files (SSH, git, fish, zsh, `Brewfile.local`, `CLAUDE.local.md`, `claude_mcp.local.json`, `macos.local.sh`) with commented examples; disable commit signing if 1Password is absent |
| 6 | [fisher](https://github.com/jorgebucaran/fisher) | fish plugins from `fish_plugins` ([tide](https://github.com/IlanCosman/tide), [fzf.fish](https://github.com/PatrickF1/fzf.fish)) — zsh's plugins ([zinit](https://github.com/zdharma-continuum/zinit)-managed) self-install on first zsh startup instead |
| 7 | [TPM](https://github.com/tmux-plugins/tpm) | [tmux](https://github.com/tmux/tmux) plugin manager + plugins from `tmux.conf` |
| 8 | [atuin](https://atuin.sh/) | Backfill existing shell history into atuin's DB |
| 9 | [iTerm2](https://iterm2.com/) *(macOS only)* | Point iTerm at the tracked `iterm2/` prefs folder |
| 10 | uv tools | Install the Python CLIs in `uv_tools.txt` |
| 11 | git clone hook | A stowed `post-checkout` template hook **notifies** on every fresh clone that defines pre-commit hooks — running nothing from the clone, so the default is safe. Opt into auto-install with `git config --file ~/.gitconfig_local dotfiles.autoInstallHooks true` and the hook runs [prek](https://github.com/j178/prek) install itself |
| 12 | [Claude Code](https://github.com/anthropics/claude-code) | Native installer (self-updating) → `~/.local/bin/claude` |
| 13 | MCP servers | Replay `claude_mcp.json` (deep-merged with an optional `~/.config/dotfiles/claude_mcp.local.json` overlay) into `~/.claude.json` — secrets via `op inject`, or a `GITHUB_PERSONAL_ACCESS_TOKEN` from the environment without 1Password |
| 14 | Claude settings | Generate `~/.claude/settings.json` by deep-merging the tracked `claude_settings.json` baseline with the untracked `~/.config/dotfiles/claude_settings.local.json` overlay (arrays union; the overlay wins per scalar) |
| 15 | [Ollama](https://ollama.com/) | Start the server & pull the role models from `scripts/ollama_models.sh`: [`qwen3:4b-instruct-2507-q4_K_M`](https://ollama.com/library/qwen3) (~2.5 GB, fast tier + [GitLens](https://www.gitkraken.com/gitlens)) and [`qwen3-vl:4b-instruct`](https://ollama.com/library/qwen3-vl) (~3.3 GB, vision) everywhere; on Apple Silicon with >32 GB unified memory (macOS 13+) also the big pair: the MLX `qwen3.5:35b-a3b-coding-nvfp4` (~21 GB, bulk coding) and `gemma4:26b` (~17 GB, generalist) — all driven through the `ollm` CLI; skip by dropping the `ollama-app` cask |
| 16 | macOS defaults *(macOS only)* | `macos.sh` system tweaks |
| 17 | Dock *(macOS only)* | Declarative Dock layout via `dock.sh` |
| 18 | VS Code settings *(macOS only)* | Generate `settings.json` by deep-merging the tracked `vscode_settings.json` baseline with an untracked `~/.config/dotfiles/vscode_settings.local.json` overlay, auto-seeding the Homebrew `rg` path the todo-tree extension needs |
| 19 | Verify | Re-check the install end state and print the summary (the same checks `dotfiles-doctor` runs) |

!!! warning "iTerm2"

    The iTerm step takes effect on iTerm's next launch — fully quit it first if it's already open.

!!! note "Several of these steps are *my* taste"

    The package list (1), MCP servers (13), the Ollama models (15), the macOS defaults (16), and the Dock (17) encode my preferences and my accounts — that 1Password path is my vault, not yours. They're the first things to change when you fork. [Make it yours](#make-it-yours) walks the exact files.

## Make it yours

This is my personal repo, not a configurable framework — so adopting it means **forking and editing**, not flipping options. The good news: the machinery (Stow, the overlays, the idempotent bootstrap, the hook suite) is generic and worth keeping as-is. What you change is the *contents*. Fork on GitHub, clone your fork, edit the files below, *then* run `install.sh`.

| Change first | File | Why |
|--------------|------|-----|
| **Your apps & CLIs** | `Brewfile`, `Brewfile.d/*.brewfile` | The single most personal file. Swap in the software you actually use; my `personal`/`homelab` bundles are examples of the pattern, not a menu for you. |
| **The Dock** | `dock.sh` | It *rebuilds your Dock* from this list on every run. Edit it to your apps, or the first run replaces your Dock with mine. |
| **macOS defaults** | `macos.sh` | System tweaks to my taste (key-repeat, Finder, screenshots, …). Read it before running — it re-asserts every run. |
| **Git identity** | `~/.gitconfig_local` | The tracked `home/.gitconfig` ships no `[user]` block — set your name, email, and signing key in the untracked overlay (`install.sh` seeds it with a commented stanza). A pre-existing `~/.gitconfig` is backed up and folded into the overlay on first install. On a machine without 1Password, `install.sh` disables commit signing for you. |
| **Claude MCP servers** | `claude_mcp.json` | My server list, and the secret refs point at *my* 1Password vault (`op://MCP/…`). Repoint them at your vault items, supply a `GITHUB_PERSONAL_ACCESS_TOKEN` via the environment, or remove the servers you don't want. |
| **Terminal & SSH** | `iterm2/`, `home/.ssh/config` | iTerm prefs are my colors/keybinds; the SSH config is a generic baseline (real hosts belong in the untracked overlay). Both optional, but yours to set. |

!!! note "It's yours now — no upstream to track"

    Once forked, there's nothing to "pull from me." Take what's useful, delete what isn't, and let it diverge. The [overlay pattern](#per-machine-setup) below is how *one* repo serves all *your* machines without per-machine branches — adopt that and you won't need to fork again per box.

## The human-only steps

A few things no script can do for you.

### Claude Code login

The CLI is installed automatically; first run needs a one-time browser sign-in (`claude`). MCP servers are already registered.

### GitHub MCP token

With [1Password](https://1password.com/): store a PAT at `op://MCP/github-claude-pat/credential`, enable the 1Password CLI integration, then re-run the script — `op inject` bakes it into `~/.claude.json`, never the repo. Without 1Password: export `GITHUB_PERSONAL_ACCESS_TOKEN` (e.g. in `~/.config/dotfiles/local.fish`) and re-run — the GitHub MCP server is wired to it.

### [VS Code](https://code.visualstudio.com/) & 1Password

Sign in to VS Code to sync (the app is a cask). For 1Password, enable the opt-in `1password` bundle on personal machines; the Safari extension installs via `mas`, while the Chrome/Firefox extensions are a manual add (the desktop app prompts to connect them).

### [AppCleaner](https://freemacsoft.net/appcleaner/) SmartDelete

A one-time GUI toggle (installs a privileged helper) — can't be scripted via `defaults`.

## Per-machine setup

How I run one repo across a laptop, a work box, and a homelab node without a fork or a `work`/`personal` branch each: per-machine specifics live in untracked overlay files the bootstrap seeds, and each machine fills in only what it needs. Adopt the same pattern in your fork — see the Architecture page's [machine-local overlays](architecture.md#machine-local-overlays) section for the full mechanism.

### Login shell: fish or zsh

fish is the default login shell; pass `install.sh --shell zsh` to select zsh instead (or `--shell fish` to switch back). The choice persists to `~/.config/dotfiles/shell`, so a plain re-run repeats it. Both shells' config trees are always stowed regardless of which is selected — only the login shell (`chsh`) differs.

### Opt-in software bundles

The bootstrap's bundle step shows an [fzf](https://github.com/junegunn/fzf) multi-select; pick `personal` and/or `homelab`. A re-run pre-seeds the picker with your current choice, ready to amend, and persists the result to `~/.config/dotfiles/bundles`. For a scripted, non-interactive run, pass `install.sh --bundle personal` (repeatable) or `--no-bundles` to skip the picker entirely, or `--keep-bundles` to skip it while keeping the saved pick. To enable one later without re-running the installer:

```bash
echo personal >> ~/.config/dotfiles/bundles
brew bundle install --file=~/dotfiles/Brewfile.d/personal.brewfile
```

### Machine-private software

Work-only or sensitive casks the public repo shouldn't carry go in untracked `~/.config/dotfiles/Brewfile.local` — auto-loaded by `install.sh`, the Homebrew analogue of `~/.gitconfig_local`.

### SSH hosts, git identity, shell tweaks

Machine-specific SSH hosts go in `~/.ssh/config.local`, a work git identity in `~/.gitconfig_local` (e.g. an `includeIf "gitdir:~/work/"`), and shell tweaks in `~/.config/dotfiles/local.fish` (fish) or `local.zsh` (zsh) — whichever you use, or both. Each is seeded with a commented example.

## Updating

### New CLI tool / app

Add a `brew`/`cask` line to the `Brewfile`, then `brew bundle install --file=~/dotfiles/Brewfile`.

### Dotfile change

Edit the file under `home/` (or its symlink in `$HOME` — same file) and commit.

### Find untracked installs

`brew bundle cleanup --file=~/dotfiles/Brewfile` reports prune candidates.

### New opt-in bundle

Drop a `Brewfile.d/<name>.brewfile` — [hawkeye](https://github.com/korandoru/hawkeye) stamps its SPDX header automatically — then select it on machines that want it.

## Uninstalling

### Preview first

`~/dotfiles/uninstall.sh --dry-run` prints exactly what it would remove and what it would leave, changing nothing. Drop `--dry-run` to do it (one confirmation), or add `--yes` to skip that prompt — the per-item offers still default to the safe choice, so `--yes` never removes anything you weren't asked about.

### Reverses only what it owns

It auto-removes the provably-ours, reversible setup — [stow](https://www.gnu.org/software/stow/) symlinks, the Claude MCP registrations, the iTerm2 prefs pointer — then *offers* (default no) to remove things it can't prove it owns: the TPM clone, the uv tools, the Ollama models. It *asks* before lossy system changes too — your login shell, and `/etc/pam.d/sudo_local` (removed only when its contents match the standard Touch-ID config the installer writes, and always after an explicit prompt).

### Your data is never deleted

Machine-local data — `~/.config/dotfiles/` overlays, `*.pre-stow.bak` backups, the generated `~/.claude/settings.json` — and genuinely irreversible setup (`macos.sh` defaults, the Dock, Homebrew itself) is left in place and listed in a closing summary, each with a copy-paste command to finish by hand if you want to.
