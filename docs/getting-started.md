# Getting Started

On my own machines this is the whole story: clone, run, done — no toolchain to set up
first, since `install.sh` installs Homebrew and uv if they're missing. Runs the same way on
**macOS, Linux, and WSL2** — steps marked *macOS only* below just skip themselves elsewhere.

--8<-- "install.md"

!!! tip "Re-run is the test"
    Running `install.sh` a second time should exit 0 with no step redoing work. The two
    declarative system steps are the deliberate exception — `macos.sh` re-asserts its
    preferences and `dock.sh` rebuilds the Dock from its list every run (pass `--no-dock`
    to skip it, or it skips itself if `dockutil` can't read the current Dock state). That's
    by design: they reset those surfaces to the repo's definition rather than preserving
    local tweaks.

## What the bootstrap does

In order — privileged steps are grouped into a single `sudo` session so you authenticate
once.

| # | Step | What happens |
| --- | --- | --- |
| 0 | Toolchain | Install Homebrew &amp; uv if missing |
| 1 | `brew bundle` | All baseline CLI tools, fish and zsh, GUI casks, the MesloLGS NF font — then an fzf multi-select for opt-in bundles (`personal`, `homelab`, `1password`) |
| 2 | Shell selection | Resolve the login shell — fish by default, or zsh if `--shell zsh` — and persist the choice to `~/.config/dotfiles/shell` |
| 3 | Privileged block | The resolved shell as login shell, plus one sudo prompt for the OS-specific bit: Touch ID for sudo &amp; the app firewall (macOS), `ufw` (native Linux), or nothing (WSL2 — the Windows host owns the firewall) |
| 4 | Stow | Symlink `home/` into `$HOME` — both shells' config trees, regardless of which is selected |
| 5 | Overlays | Seed untracked machine-local overlay files (SSH, git, fish, zsh, `Brewfile.local`, `CLAUDE.local.md`, …) with commented examples; disable commit signing if 1Password is absent |
| 6 | fisher | fish plugins from `fish_plugins` (tide, fzf.fish) — zsh's plugins self-install on first zsh startup |
| 7 | TPM | tmux plugin manager + plugins from `tmux.conf` |
| 8 | atuin | Backfill existing shell history into atuin's DB |
| 9 | iTerm2 *(macOS only)* | Point iTerm at the tracked `iterm2/` prefs folder |
| 10 | uv tools | Install the Python CLIs in `uv_tools.txt` |
| 11 | git clone hook | A stowed `post-checkout` template hook **notifies** on every fresh clone that defines pre-commit hooks — running nothing from the clone, so the default is safe |
| 12 | Claude Code | Native installer (self-updating) → `~/.local/bin/claude` |
| 13 | MCP servers | Replay `claude_mcp.json` (deep-merged with an optional overlay) into `~/.claude.json` — secrets via `op inject` |
| 14 | Claude settings | Generate `~/.claude/settings.json` by deep-merging the tracked baseline with the untracked overlay (arrays union; overlay wins per scalar) |
| 15 | Ollama | Start the server &amp; pull the role models, driven through the `ollm` CLI; skipped under `--core` |
| 16 | macOS defaults *(macOS only)* | `macos.sh` system tweaks |
| 17 | Dock *(macOS only)* | Declarative Dock layout via `dock.sh` |
| 18 | VS Code settings *(macOS only)* | Generate `settings.json` by deep-merging the tracked baseline with an untracked overlay |
| 19 | Verify | Re-check the install end state and print the summary (the same checks `dotfiles-doctor` runs) |

The iTerm2 step takes effect on iTerm's next launch — fully quit it first if it's already
open. Several steps are personal taste — the package list (1), MCP servers (13), the Ollama
models (15), the macOS defaults (16), and the Dock (17) encode Tyler's preferences and
accounts. They're the first things to change on a fork.

## Make it yours

This is a personal repo, not a configurable framework — adopting it means **forking and
editing**, not flipping options. The machinery (Stow, the overlays, the idempotent
bootstrap, the hook suite) is generic and worth keeping as-is; what changes is the
*contents*.

| Change first | File | Why |
| --- | --- | --- |
| Your apps &amp; CLIs | `Brewfile`, `Brewfile.d/*.brewfile` | The single most personal file. |
| The Dock | `dock.sh` | It rebuilds your Dock from this list on every run. |
| macOS defaults | `macos.sh` | System tweaks to personal taste; re-asserts every run. |
| Git identity | `~/.gitconfig_local` | The tracked `home/.gitconfig` ships no `[user]` block. A pre-existing `~/.gitconfig` is backed up and folded into the overlay on first install. |
| Claude MCP servers | `claude_mcp.json` | Repoint the secret refs at your own 1Password vault, or supply a `GITHUB_PERSONAL_ACCESS_TOKEN`. |
| Terminal &amp; SSH | `iterm2/`, `home/.ssh/config` | iTerm prefs are personal; the SSH config is a generic baseline. |

## The human-only steps

- **Claude Code login** — the CLI installs automatically; first run needs a one-time
  browser sign-in.
- **GitHub MCP token** — with 1Password: store a PAT at
  `op://MCP/github-claude-pat/credential`, enable the 1Password CLI integration, re-run.
  Without: export `GITHUB_PERSONAL_ACCESS_TOKEN` and re-run.
- **VS Code &amp; 1Password** — sign in to VS Code to sync; enable the opt-in `1password`
  bundle for the desktop app / browser extensions.
- **AppCleaner SmartDelete** — a one-time GUI toggle that installs a privileged helper;
  can't be scripted via `defaults`.

## Per-machine setup

Per-machine specifics live in untracked overlay files the bootstrap seeds; each machine
fills in only what it needs (see [Architecture](architecture.md#machine-local-overlays) for
the full mechanism).

- **Login shell: fish or zsh** — fish is the default; `--shell zsh` selects zsh instead.
  Persists to `~/.config/dotfiles/shell`; both shells' config trees are always stowed.
- **Opt-in software bundles** — an fzf multi-select for `personal`/`homelab`; persists to
  `~/.config/dotfiles/bundles`. `--bundle NAME` / `--no-bundles` / `--keep-bundles` control
  it non-interactively.
- **Machine-private software** — work-only or sensitive casks go in untracked
  `~/.config/dotfiles/Brewfile.local`.
- **SSH hosts, git identity, shell tweaks** — `~/.ssh/config.local`, `~/.gitconfig_local`,
  `~/.config/dotfiles/local.fish` (fish) or `local.zsh` (zsh).

## Uninstalling

`~/dotfiles/uninstall.sh --dry-run` previews exactly what it would remove, changing nothing.
It auto-removes the provably-ours, reversible setup (stow symlinks, Claude MCP
registrations, the iTerm2 prefs pointer), *offers* (default no) to remove things it can't
prove it owns (the TPM clone, uv tools, Ollama models), and *asks* before lossy system
changes (login shell, the Touch-ID PAM file). Machine-local data and genuinely irreversible
setup (macOS defaults, the Dock, Homebrew itself) is left in place and listed with
copy-paste commands to finish by hand.
