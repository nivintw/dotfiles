# Architecture

A symlink farm with a single source of truth, and a bootstrap that's careful never to fight
the machine it's setting up. Runs on macOS, Linux, and WSL2 — the installer's phase registry
OS-gates each phase; the ones whose entire purpose is macOS state (iTerm2, `macos.sh`, the
Dock, VS Code settings) skip themselves on Linux/WSL2, and every other phase runs everywhere.

## `home/` mirrors `$HOME`

The repo's `home/` directory is a literal mirror of `$HOME`. GNU Stow walks it and creates a
symlink in `$HOME` for every file, so the file in the repo *is* the file on disk. Editing
either side edits the same bytes — no copy step, no "apply" command, no drift.

!!! note "Why Stow"
    One `stow home` creates the whole symlink farm and is itself idempotent. It refuses to
    overwrite an existing real file — so a conflict is a loud error, never silent data loss.
    The bootstrap removes only known *generated* real files first (never existing symlinks,
    and never a file that resolves back into the repo through a folded parent) so Stow can
    take them over.

## Repository layout

| Path | Role |
| --- | --- |
| `home/` | Everything symlinked into `$HOME` |
| `Brewfile` | Baseline formulae + casks, installed by `brew bundle` |
| `Brewfile.d/` | Opt-in `<name>.brewfile` bundles layered on the baseline per machine |
| `uv_tools.txt` | Python CLIs, one `uv tool install` arg-list per line |
| `claude_mcp.json` | Claude Code MCP servers, replayed into `~/.claude.json` |
| `vscode_settings.json` | VS Code `settings.json` baseline, deep-merged with a machine-local overlay |
| `install.sh` | Thin entry-point shim — guards on macOS/Linux, bootstraps `uv`, then hands off to the installer |
| `src/dotfiles_install/` | The idempotent installer: a Python package (`dotfiles-install` console script) that walks an ordered phase registry |
| `macos.sh` · `dock.sh` | macOS defaults &amp; declarative Dock |
| `iterm2/` | iTerm2 prefs (pointed at directly, not stowed) |
| `scripts/` | Helper scripts referenced by hooks |
| `tests/` | bats (fish + zsh function behavior) + pytest (config validity) |
| `docs/` | This documentation site |

## What isn't stowed — and why

- **iTerm2 preferences** — pointed at the `iterm2/` folder directly via `defaults`. It
  rewrites its plist on quit, which would clobber a symlink.
- **`~/.claude.json`** — machine-local state (project history, OAuth). The declarative source
  of truth is `claude_mcp.json`, replayed in idempotently.
- **`~/.claude/settings.json`** — generated, not symlinked: Claude Code's `/config` and
  `/plugin` write live state through it, so the tracked `claude_settings.json` baseline is
  deep-merged with a machine-local overlay and written as a real file.
- **VS Code `settings.json`** — generated with the same mechanism, for a machine-drift reason
  rather than a live-rewrite one: the todo-tree extension's bundled-ripgrep path moves between
  VS Code releases and isn't expressible in a single tracked baseline. So the tracked
  `vscode_settings.json` baseline is deep-merged with a machine-local overlay — auto-seeded
  with this machine's `rg` path.
- **Machine-local overlays** — untracked files outside the repo the tracked config `Include`s
  or sources; seeded with commented examples, never symlinked.

## Machine-local overlays

This is how one repo runs across every machine — a laptop, a work box, a homelab node — from
a single branch. Anything machine-specific lives in untracked files *outside* the repo that
the tracked config reads, so `git pull` never conflicts and nothing machine-specific leaks
into the public repo.

| Tool | Tracked baseline | Untracked overlay | Wiring |
| --- | --- | --- | --- |
| SSH | `home/.ssh/config` | `~/.ssh/config.local` | `Include`d by the tracked config |
| git | `home/.gitconfig` | `~/.gitconfig_local` | `[include]`d **last** (overlay wins every key); a pre-existing `~/.gitconfig` is backed up + folded in |
| fish | `home/.config/fish/**` | `~/.config/dotfiles/local.fish` | sourced by `conf.d/zzz-local.fish` |
| zsh | `home/.config/zsh/**`, `home/.zshenv` | `~/.config/dotfiles/local.zsh` | sourced by `conf.d/zzz-local.zsh` |
| Homebrew | `Brewfile` + `Brewfile.d/*.brewfile` | `~/.config/dotfiles/Brewfile.local` | loaded by `install.sh` |
| Claude memory | `home/.claude/CLAUDE.md` | `~/.config/dotfiles/CLAUDE.local.md` | `@`-imported by the tracked `CLAUDE.md` |
| Claude settings | `claude_settings.json` | `~/.config/dotfiles/claude_settings.local.json` | deep-merged by the installer (arrays union) |
| Claude MCP | `claude_mcp.json` | `~/.config/dotfiles/claude_mcp.local.json` | deep-merged by the installer |
| VS Code settings | `vscode_settings.json` | `~/.config/dotfiles/vscode_settings.local.json` | deep-merged; auto-seeded with this machine's `rg` path |
| macOS defaults | `macos.sh` | `~/.config/dotfiles/macos.local.sh` | sourced by `macos.sh` |

The bootstrap seeds each overlay with a commented example on first run — idempotently, so it
never clobbers content already added. This is also how 1Password stays optional: the baseline
keeps it as the personal default, but a machine without it gets graceful fallbacks (commit
signing disabled, the GitHub MCP token read from the environment) and skips the opt-in
`1password` bundle. Per-directory git identity uses `[includeIf "gitdir:~/work/"]` in
`~/.gitconfig_local`.

!!! info "Opt-in Brewfile bundles"
    Software not wanted on every machine lives in tracked `Brewfile.d/<name>.brewfile`
    bundles, picked via an fzf multi-select persisted to `~/.config/dotfiles/bundles`.
    `brew bundle` ignores the filename; the `.brewfile` extension exists so hawkeye
    auto-maintains each bundle's SPDX header.

## XDG-native git config

The global git ignore lives at `home/.config/git/ignore`; a copy is also mirrored into the
repo's own `.gitignore` because VS Code's `explorer.excludeGitIgnore` only reads an
in-workspace `.gitignore`, never the global `core.excludesFile` — git behavior itself is
unchanged.

## The idempotency contract

- **Adopt, don't clobber** — `brew bundle` adopts a cask whose app is already in
  `/Applications` in place.
- **Guarded mutations** — every step checks before it acts: `/etc/shells` gets the resolved
  shell's line only if absent, MCP servers are removed-then-added, Ollama model pulls are
  skipped when already present.
- **Re-run is the test** — running `install.sh` a second time should exit 0 with no step
  redoing work (the declarative `macos.sh`/`dock.sh` steps are the deliberate exception —
  they converge rather than no-op).
