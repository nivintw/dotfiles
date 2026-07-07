# Architecture

A symlink farm with a single source of truth, and a bootstrap that's careful never to
fight the machine it's setting up. Runs on macOS, Linux, and WSL2 — the installer's phase
registry OS-gates each phase; the ones whose entire purpose is macOS state (iTerm2,
`macos.sh`, the Dock, VS Code settings) skip themselves on Linux/WSL2, and every other
phase runs everywhere.

## home/ mirrors $HOME

The repo's `home/` directory is a literal mirror of `$HOME`.
[GNU Stow](https://www.gnu.org/software/stow/) walks it and creates a symlink in `$HOME`
for every file, so the file in the repo *is* the file on disk:

```text
~/dotfiles/home/.config/fish/config.fish
        ▲  symlink
~/.config/fish/config.fish   →   (same file)
```

Editing either side edits the same bytes. There's no copy step, no "apply" command, no
drift between "the repo" and "my machine."

!!! note "Why Stow"

    One `stow home` creates the whole symlink farm and is itself idempotent. It **refuses
    to overwrite an existing real file** — so a conflict is a loud error, never silent data
    loss. Before stowing, the installer clears only known tool-*generated* real files (never
    existing symlinks): a copy byte-identical to the repo's is removed, a divergent one is
    backed up to a numbered `*.pre-stow.bak` (never destroyed), so Stow can take the path over.

## Repository layout

| Path | Role |
| --- | --- |
| `home/` | Everything symlinked into `$HOME` |
| `Brewfile` | Baseline formulae + casks, installed by `brew bundle` |
| `Brewfile.d/` | Opt-in `<name>.brewfile` bundles (e.g. `personal`, `homelab`) layered on the baseline per machine |
| `uv_tools.txt` | Python CLIs, one `uv tool install` arg-list per line |
| `claude_mcp.json` | [Claude Code](https://github.com/anthropics/claude-code) MCP servers, replayed into `~/.claude.json` |
| `vscode_settings.json` | VS Code `settings.json` baseline, deep-merged with a machine-local overlay at install time |
| `install.sh` | Thin entry-point shim — guards on macOS/Linux (WSL2 reports as Linux), bootstraps `uv`, then hands off to the installer |
| `src/dotfiles_install/` | The idempotent installer: a Python package (the `dotfiles-install` console script) that walks an ordered phase registry |
| `macos.sh` · `dock.sh` | macOS defaults & declarative Dock |
| `iterm2/` | [iTerm2](https://iterm2.com/) prefs (pointed at directly — see below) |
| `scripts/` | Helper scripts referenced by hooks |
| `tests/` | [bats](https://github.com/bats-core/bats-core) ([fish](https://fishshell.com/) + [zsh](https://www.zsh.org/) function behavior) + [pytest](https://docs.pytest.org/) (config validity) |
| `docs/` | This documentation site |

## What isn't stowed — and why

Some paths can't be a symlink into the repo — a tool rewrites them, they hold machine-local
state, or they're generated from a baseline + overlay. Each is handled by its own installer
phase instead of Stow.

| Not stowed | Why |
| --- | --- |
| **iTerm2 preferences** | iTerm is pointed at the `iterm2/` folder directly via `defaults`. It rewrites its plist on quit, which would clobber a symlink — so it owns a real folder in the repo instead. |
| **`~/.claude.json`** | Machine-local state (project history, OAuth). The declarative source of truth is `claude_mcp.json`, replayed in idempotently rather than symlinked. |
| **`~/.claude/settings.json`** | Generated, not symlinked: Claude Code's `/config` and `/plugin` write live state through it, so the tracked `claude_settings.json` baseline is deep-merged with a machine-local overlay and written as a real file. See [Machine-local overlays](#machine-local-overlays) below. |
| **VS Code `settings.json`** | Generated with the same mechanism as Claude Code's, for a machine-drift reason rather than a live-rewrite one: the todo-tree extension's bundled-ripgrep path moves between VS Code releases and isn't expressible in a single tracked, cross-machine baseline. So the tracked `vscode_settings.json` baseline is deep-merged with a machine-local overlay — auto-seeded with this machine's Homebrew `rg` path — and written as a real file. |
| **Machine-local overlays** | A family of untracked files outside the repo (`~/.ssh/config.local`, `~/.gitconfig_local`, and more) that the tracked config `Include`s or sources — seeded with commented examples, never symlinked. See below. |

## Machine-local overlays

This is how I run one repo across all of *my* machines — a laptop, a work box, a homelab
node — from a single branch. Anything machine-specific lives in untracked files *outside*
the repo that the tracked config reads, so `git pull` never conflicts and nothing
machine-specific leaks into the public repo. I don't keep a per-machine fork or a
`work`/`personal` branch — and once you've forked, the same pattern means you won't need to
either.

| Tool | Tracked baseline | Untracked overlay | Wiring |
| --- | --- | --- | --- |
| SSH | `home/.ssh/config` | `~/.ssh/config.local` | `Include`d by the tracked config |
| git | `home/.gitconfig` | `~/.gitconfig_local` | `[include]`d **last** by the tracked config (overlay wins for every key, incl. identity); a pre-existing `~/.gitconfig` is backed up + folded in |
| fish | `home/.config/fish/**` | `~/.config/dotfiles/local.fish` | sourced by `conf.d/zzz-local.fish` |
| zsh | `home/.config/zsh/**`, `home/.zshenv` | `~/.config/dotfiles/local.zsh` | sourced by `conf.d/zzz-local.zsh`; always stowed alongside fish — only the login shell is selected (see [Per-machine setup](getting-started.md#per-machine-setup)) |
| Homebrew | `Brewfile` + `Brewfile.d/*.brewfile` | `~/.config/dotfiles/Brewfile.local` | loaded by the installer's brew-bundle phase |
| Claude memory | `home/.claude/CLAUDE.md` | `~/.config/dotfiles/CLAUDE.local.md` | `@`-imported by the tracked `CLAUDE.md` |
| Claude settings | `claude_settings.json` | `~/.config/dotfiles/claude_settings.local.json` | deep-merged by the installer (arrays union) into a real `~/.claude/settings.json` |
| Claude MCP | `claude_mcp.json` | `~/.config/dotfiles/claude_mcp.local.json` | deep-merged by the installer |
| VS Code settings | `vscode_settings.json` | `~/.config/dotfiles/vscode_settings.local.json` | deep-merged by the installer (arrays union) into a real `settings.json`; auto-seeded with this machine's `rg` path |
| macOS defaults | `macos.sh` | `~/.config/dotfiles/macos.local.sh` | sourced by `macos.sh` |

The bootstrap seeds each overlay with a commented example on first run — idempotently, so it
never clobbers content you've added — so the includes never dangle and the format is
self-documenting. This is also how 1Password stays optional: the baseline keeps it as the
personal default, but a machine without it gets graceful fallbacks (commit signing disabled,
the GitHub MCP token read from the environment) and skips the opt-in `1password` bundle.

!!! tip "Opt-in Brewfile bundles"

    Software not wanted on every machine lives in tracked `Brewfile.d/<name>.brewfile`
    bundles. The installer shows an [fzf](https://github.com/junegunn/fzf) multi-select of
    the available ones — pre-seeded with your current pick on a re-run, so it's ready to
    amend — and persists the result to `~/.config/dotfiles/bundles`. Pass `--bundle NAME`
    (repeatable) or `--no-bundles` to skip the picker for scripted runs, or `--keep-bundles`
    to skip it while reusing the saved pick unchanged; non-interactive runs (CI) just read
    the saved file. This repo ships `personal`, `homelab`, and `1password`; a machine that
    picks nothing gets just the baseline.

!!! tip "An extension, not a filename"

    `brew bundle` ignores the filename entirely; the `.brewfile` extension exists so
    [hawkeye](https://github.com/korandoru/hawkeye) auto-maintains each bundle's SPDX header
    from one `.config/licenserc.toml` mapping (no hand-written headers), and the editor
    highlights them as the Ruby DSL they are.

!!! note "Per-directory git identity"

    The cleanest way to use a work email/signing key only in work repos — set in
    `~/.gitconfig_local`:

    ```ini
    [includeIf "gitdir:~/work/"]
        path = ~/.gitconfig.work
    ```

## XDG-native git config

The global git ignore lives at `home/.config/git/ignore` — git reads `~/.config/git/ignore`
automatically when `core.excludesFile` is unset, so there's no custom path to configure. A
copy of those rules is also mirrored into the repo's own `.gitignore` for one specific reason:

!!! note "Why the duplicate"

    VS Code's `explorer.excludeGitIgnore` only reads an in-workspace `.gitignore`, never the
    global `core.excludesFile`. Mirroring the global rules into the repo's `.gitignore` makes
    the editor's file tree hide exactly what git ignores. Git behavior is unchanged — the
    global was already in effect.

## The idempotency contract

- **Adopt, don't clobber.** `brew bundle` adopts a cask whose app is already in
  `/Applications` in place — no redownload, no "install fails, adopt later" dance.
- **Guarded mutations.** Every step checks before it acts: `/etc/shells` gets the resolved
  shell's line (fish by default, or zsh when selected) only if absent, MCP servers are
  removed-then-added, the [Ollama](https://ollama.com/) model pulls are skipped when already
  present.
- **Re-run is the test.** The real idempotency check is running `install.sh` a second time:
  exit 0, and no step reports re-doing work — no duplicate shells entry, no stow conflict, no
  duplicate MCP server. (The declarative `macos.sh` and `dock.sh` steps re-assert state by
  design — they converge rather than no-op.)
