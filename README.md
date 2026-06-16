<!--
SPDX-FileCopyrightText: © 2026 Tyler Nivin
SPDX-License-Identifier: MIT
-->

# dotfiles

My personal dotfiles.

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

No prerequisites — `install.sh` installs Homebrew and uv if they're missing.

```bash
git clone <this-repo> ~/dotfiles
~/dotfiles/install.sh
```

`install.sh` runs, in order: install Homebrew + uv if missing → `brew bundle`
(CLI tools, fish, GUI casks, the MesloLGS NF font) → set fish as the default
login shell → `stow` symlinks → fisher plugins → point iTerm2 at `iterm2/` →
uv tools → register Claude Code MCP servers (`claude_mcp.json`). It's
idempotent — safe to re-run.

The iTerm2 step takes effect on iTerm's next launch — fully quit it first if
it's already open.

`brew bundle` adopts casks whose app is already in `/Applications` (installed by
hand) in place, not redownloaded or clobbered — no "install fails, adopt later"
dance. Likewise `stow` refuses to clobber existing real files; if it reports
conflicts, back up and remove those files, then re-run.

See [software_list.md](software_list.md) for the few human-only steps left
(Claude Code CLI, VS Code sign-in, 1Password browser extensions).

## Updating

- **New CLI tool / app:** add a `brew`/`cask` line to the `Brewfile`, then
  `brew bundle install --file=~/dotfiles/Brewfile`.
- **Dotfile change:** just edit the file under `home/` (or its symlink in
  `$HOME` — same file) and commit.
- **See what's installed but not tracked** (prune candidates):
  `brew bundle cleanup --file=~/dotfiles/Brewfile`
