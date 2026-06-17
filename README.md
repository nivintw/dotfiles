<!--
SPDX-FileCopyrightText: © 2026 Tyler Nivin
SPDX-License-Identifier: MIT
-->

# dotfiles

My personal macOS setup — the same repo I clone onto every Mac I own: clone, run,
done. It's also **built to be forked**: the machinery (Stow, the overlays, the
idempotent bootstrap, the hook suite) is the reusable part; the package list, the
Dock, and the keys are mine to swap for yours. If you're adopting it, fork it and
see [**Make it yours**](https://nivintw.github.io/dotfiles/getting-started.html#make-it-yours)
first.

📖 **[Documentation site →](https://nivintw.github.io/dotfiles/)**

## Layout

- `home/` — mirrors `$HOME`. Symlinked into place with [GNU Stow](https://www.gnu.org/software/stow/).
  Editing `~/.config/fish/config.fish` edits `home/.config/fish/config.fish` directly.
- `home/.typos.toml` — default [typos](https://github.com/crate-ci/typos) config.
  Applies to any repo under `$HOME` without its own typos config (typos walks up
  the tree). Ignores URLs/emails/bare domains by shape and adds a
  `# typos:disable-line` escape hatch. Check-only by design — never auto-write.
- `Brewfile` — formulae + casks, installed with `brew bundle`.
- `software_list.md` — the manual steps Brewfile/stow can't automate.
- `uv_tools.txt` — Python tools, one `uv tool install` arg-list per line (read by `install.sh`).
- `claude_mcp.json` — Claude Code user-scope MCP servers, declared as `name → config`.
  Replayed into `~/.claude.json` by `install.sh` (that file is machine-local state,
  so it isn't stowed). Secret values are 1Password references (`{{ op://... }}`)
  resolved at install time with `op inject`, so no token is committed. Skipped if
  the Claude Code CLI isn't installed; secret-backed servers are skipped until
  1Password CLI is signed in (re-run `install.sh` to add them).
- `iterm2/` — iTerm2 preferences. iTerm is pointed at this folder directly
  (not stowed — iTerm rewrites the plist on quit, which would clobber a symlink).

## Bootstrap a new machine

No toolchain to set up first — `install.sh` installs Homebrew and uv if they're
missing. (Forking? It installs *my* taste — package list, Dock, macOS defaults,
keys — so review and edit those before you run it; see
[Make it yours](https://nivintw.github.io/dotfiles/getting-started.html#make-it-yours).)

```bash
git clone https://github.com/nivintw/dotfiles ~/dotfiles
~/dotfiles/install.sh
```

`install.sh` runs, in order: install Homebrew + uv if missing → `brew bundle`
(CLI tools, fish, GUI casks, the MesloLGS NF font) → set fish as the default
login shell → `stow` symlinks → fisher plugins → point iTerm2 at `iterm2/` →
uv tools → register Claude Code MCP servers (`claude_mcp.json`) → apply macOS
system defaults (`macos.sh`) → rebuild the Dock (`dock.sh`).

It's idempotent — safe to re-run — in the **config-as-code** sense: it
*converges* the machine to the declared state rather than preserving local
tweaks. Packages and symlinks are adopted, not clobbered; but the two
declarative system steps **re-assert** themselves every run — `macos.sh`
re-applies its system preferences and `dock.sh` **rebuilds the Dock** from its
list (replacing your current one). The Dock rebuild prompts for confirmation
when run interactively; everything else runs unattended.

The iTerm2 step takes effect on iTerm's next launch — fully quit it first if
it's already open.

`install.sh` bootstraps Homebrew, uv, fisher, and the Claude Code CLI by running
each tool's **official upstream install script**, piped from its canonical URL.
These run as your user — never under `sudo` (the script fences the few privileged
steps separately) — but they are third-party code fetched at runtime: if you
don't trust those sources, review them before running.

`brew bundle` adopts casks whose app is already in `/Applications` (installed by
hand) in place, not redownloaded or clobbered — no "install fails, adopt later"
dance. `stow` refuses to clobber existing real files, so `install.sh` **preflights
for conflicts**: it assumes an otherwise clean `$HOME` for the paths it owns, and
if it finds pre-existing real files there it lists them all and aborts up front,
so you can back them up or merge their contents into the repo before re-running.

See [software_list.md](software_list.md) for the few human-only steps left
(Claude Code CLI, VS Code sign-in, 1Password browser extensions).

## Updating

- **New CLI tool / app:** add a `brew`/`cask` line to the `Brewfile`, then
  `brew bundle install --file=~/dotfiles/Brewfile`.
- **Dotfile change:** just edit the file under `home/` (or its symlink in
  `$HOME` — same file) and commit.
- **See what's installed but not tracked** (prune candidates):
  `brew bundle cleanup --file=~/dotfiles/Brewfile`

## Machine-local overlays

The tracked files are a generic baseline. Anything machine-specific (a work box,
a homelab node, personal-only software) lives in **untracked local files outside
the repo** that the tracked config reads — so I run one branch across all my
machines: `git pull` never conflicts, nothing machine-specific leaks into the
public repo, and there's no per-machine fork or `work`/`personal` branch. Once
you've forked, the same pattern serves all of *your* machines too.
`install.sh` creates each file empty on first run; fill in what a given machine
needs.

| Tool | Tracked baseline | Local overlay (untracked) | Wiring |
|------|------------------|---------------------------|--------|
| **SSH** | `home/.ssh/config` (generic) | `~/.ssh/config.local` | `Include`d by the tracked config |
| **git** | `home/.gitconfig` | `~/.gitconfig_local` | `[include]` in the tracked config |
| **fish** | `home/.config/fish/**` | `~/.config/dotfiles/local.fish` | sourced by `conf.d/zzz-local.fish` |
| **Homebrew** | `Brewfile` + tracked `Brewfile.d/<name>.brewfile` | `~/.config/dotfiles/Brewfile.local` (+ `bundles` selection) | loaded by `install.sh` |

**Per-directory git identity** — the cleanest way to use a work email/signing key
only in work repos, set in `~/.gitconfig_local`:

```gitconfig
[includeIf "gitdir:~/work/"]
    path = ~/.gitconfig.work   # work email, signing key, etc. — untracked
```

**Homebrew — baseline, opt-in bundles, and private additions.** Three layers:

- `Brewfile` — the **baseline**, installed on every machine.
- `Brewfile.d/<name>.brewfile` — **tracked** opt-in bundles (same Ruby DSL as
  `Brewfile`). `brew bundle` ignores the filename; the `.brewfile` extension is
  there so hawkeye auto-manages their SPDX headers and the editor highlights them.
  On first run `install.sh` shows an `fzf` multi-select of the available bundles,
  and your choice persists to `~/.config/dotfiles/bundles` (one name per line) for
  idempotent re-runs. This repo ships `personal` and `homelab`; a machine that
  picks nothing gets just the baseline.
- `~/.config/dotfiles/Brewfile.local` — **untracked**, machine-private additions
  (e.g. work-only software you don't want in the public repo). Auto-loaded by
  `install.sh` if present — the Homebrew analogue of `~/.gitconfig_local`.

```bash
# install.sh's bundle step shows an fzf multi-select; pick "personal" and/or
# "homelab" there. To enable one without re-running the full installer:
echo personal >> ~/.config/dotfiles/bundles
brew bundle install --file=~/dotfiles/Brewfile.d/personal.brewfile

# Work-only software the public repo shouldn't carry → the private file:
printf 'cask "company-vpn"\n' >> ~/.config/dotfiles/Brewfile.local
```

Add a tracked bundle by dropping a new `Brewfile.d/<name>.brewfile` — hawkeye
auto-inserts and maintains its SPDX header (the `brewfile` extension is mapped in
`licenserc.toml`), so you never hand-write one. Then select it on machines that
want it.
