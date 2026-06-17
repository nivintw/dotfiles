#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Bootstrap a machine from this dotfiles repo.
#
# Idempotent — safe to re-run. Installs Homebrew and uv if missing, then
# everything else (incl. fish) via brew bundle. Run from anywhere:
#
#   ~/dotfiles/install.sh
#
set -euo pipefail

DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }

# --- sudo, acquired just-in-time --------------------------------------------
# A few steps need root (Touch-ID PAM, /etc/shells + chsh, firewall). We do NOT
# stamp sudo up front and keep it warm: the curl|bash bootstraps (Homebrew, uv,
# fisher, Claude Code) would then run with a live, passwordless sudo timestamp
# available — needless blast radius if an upstream installer were compromised or
# MITM'd. Instead ALL privileged steps are grouped into one block (step 2)
# fenced by `need_sudo` ... `sudo -k`, run right after brew bundle. Homebrew/uv
# above and fisher/Claude below therefore never see a warm ticket; and because
# the grouped steps run back-to-back within sudo's ~5-min timestamp, you still
# authenticate only once.
need_sudo() { sudo -v; }

# --- 0. Bootstrap toolchain (Homebrew + uv) ---------------------------------
# Everything else (fish, stow, the rest) comes from brew bundle below.
if ! command -v brew >/dev/null 2>&1; then
  log "Installing Homebrew"
  NONINTERACTIVE=1 /bin/bash -c \
    "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Put brew on PATH for the rest of this script (Apple Silicon vs Intel).
  for brew_bin in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [ -x "$brew_bin" ] && eval "$("$brew_bin" shellenv)" && break
  done
fi
command -v brew >/dev/null 2>&1 || { echo "Homebrew install failed." >&2; exit 1; }

if ! command -v uv >/dev/null 2>&1; then
  log "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # uv installs to ~/.local/bin (newer) or ~/.cargo/bin (older); cover both.
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || { echo "uv install failed." >&2; exit 1; }

# --- 1. Homebrew formulae + casks -------------------------------------------
# brew bundle adopts already-present casks in place rather than clobbering them.
log "Installing Homebrew packages (brew bundle)"
brew bundle install --file="$DOTFILES/Brewfile"

# Opt-in bundles (tracked, public): each name in ~/.config/dotfiles/brewfiles
# (untracked, one per line) pulls in the matching Brewfile.d/<name>. Absent/empty
# list = baseline only — which is exactly what a machine that shouldn't get the
# personal apps leaves it as. See "Machine-local overlays" in the README.
brew_bundle_list="$HOME/.config/dotfiles/brewfiles"
if [ -f "$brew_bundle_list" ]; then
  while IFS= read -r bundle; do
    case "$bundle" in '' | \#*) continue ;; esac
    bundle_file="$DOTFILES/Brewfile.d/$bundle"
    if [ -f "$bundle_file" ]; then
      log "Installing opt-in Brewfile bundle: $bundle"
      brew bundle install --file="$bundle_file"
    else
      log "  skipping opt-in bundle '$bundle' (no $bundle_file)"
    fi
  done < "$brew_bundle_list"
fi

# Machine-PRIVATE additions (untracked, never in the public repo): work-only
# software, etc. The Homebrew analogue of ~/.gitconfig_local and ~/.ssh/config.local.
brew_local="$HOME/.config/dotfiles/Brewfile.local"
if [ -f "$brew_local" ]; then
  log "Installing machine-local Brewfile additions (Brewfile.local)"
  brew bundle install --file="$brew_local"
fi

# --- 2. Privileged setup — one sudo session ---------------------------------
# Everything that needs root is grouped here so a single authentication covers
# it all: sudo caches its timestamp (~5 min) and these steps run back-to-back.
# Nothing long-running or curl|bash sits between need_sudo and the sudo -k at the
# end of the block — that's what keeps the Homebrew/uv bootstraps above and the
# fisher/Claude installers below from ever running with a warm ticket.
need_sudo

# Touch ID for sudo via /etc/pam.d/sudo_local — NOT /etc/pam.d/sudo, which macOS
# overwrites on OS updates. pam_reattach (from the Brewfile) makes it work inside
# tmux/screen panes too; its line must precede pam_tid. macOS 14+ already has
# `auth include sudo_local` near the top of /etc/pam.d/sudo. On a fresh Mac this
# isn't wired up yet, so the need_sudo above is a password prompt the first time;
# every step in this block then reuses that one ticket.
if [ -f /etc/pam.d/sudo ] && grep -q 'sudo_local' /etc/pam.d/sudo; then
  if ! sudo grep -qs 'pam_tid.so' /etc/pam.d/sudo_local 2>/dev/null; then
    pam_reattach="$(brew --prefix)/lib/pam/pam_reattach.so"
    log "Enabling Touch ID for sudo (/etc/pam.d/sudo_local)"
    sudo tee /etc/pam.d/sudo_local >/dev/null <<EOF
auth       optional       $pam_reattach
auth       sufficient     pam_tid.so
EOF
  fi
else
  log "Skipping Touch ID for sudo (/etc/pam.d/sudo has no sudo_local include)"
fi

# Make fish the default login shell. fish is brew-installed (see Brewfile); a
# brew upgrade can disturb an already-open fish session until it's restarted —
# accepted tradeoff. Register it in /etc/shells, then chsh *via sudo*: root can
# set the login shell without a separate password prompt, keeping this inside the
# single sudo session (a bare `chsh` would prompt for your password on its own).
fish_bin="$(command -v fish)"
if ! grep -qxF "$fish_bin" /etc/shells; then
  log "Registering $fish_bin in /etc/shells"
  echo "$fish_bin" | sudo tee -a /etc/shells >/dev/null
fi
if [ "${SHELL:-}" != "$fish_bin" ]; then
  log "Setting fish as the default shell (chsh)"
  sudo chsh -s "$fish_bin" "$(id -un)"
fi

# macOS application firewall + stealth mode (don't respond to ping/port scans);
# both ship OFF on macOS. Done here to stay within the single sudo session rather
# than at the very end of the run.
log "Enabling the macOS application firewall + stealth mode"
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on >/dev/null
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on >/dev/null

# Done with root. Drop the ticket so nothing downstream (the fisher/Claude
# curl|bash installers included) runs with a warm sudo timestamp.
sudo -k

# --- 3. Symlink dotfiles into $HOME -----------------------------------------
# Stow refuses to overwrite existing real files. Remove known managed files that
# tools may generate as real files on first run so stow can replace them with
# symlinks. Only real files are removed (never existing symlinks), so this stays
# idempotent; stow recreates each as a symlink below.
managed_files=(
  "$HOME/Library/Application Support/Code/User/settings.json"  # VS Code / Settings Sync
  "$HOME/.config/atuin/config.toml"                            # atuin writes a default on first run
  "$HOME/.config/topgrade.toml"                                # topgrade --edit-config seeds a default
)
for f in "${managed_files[@]}"; do
  if [ -f "$f" ] && [ ! -L "$f" ]; then
    log "Removing existing real file so stow can symlink it: $f"
    rm "$f"
  fi
done

# Preflight: stow aborts mid-run on the FIRST conflicting file, so do a dry run
# (-n) first to surface ALL conflicts up front. The dry run plans without touching
# the filesystem and applies stow's own ignore rules (.stow-local-ignore: .DS_Store,
# the control file, README/LICENSE, etc.), so it never false-positives on files
# stow wouldn't link anyway. This repo expects to own its paths in a clean $HOME;
# the managed_files above are the known auto-generated exceptions, already cleared.
log "Checking for stow conflicts (dry run)"
if ! stow_plan="$(stow -n -v --dir="$DOTFILES" --target="$HOME" home 2>&1)"; then
  echo "ERROR: these files already exist in \$HOME and would be replaced by this repo's versions, so aborting." >&2
  echo "Back them up and/or merge their contents into the repo, then re-run install.sh:" >&2
  printf '%s\n' "$stow_plan" | grep -E 'cannot stow' >&2 || printf '%s\n' "$stow_plan" >&2
  exit 1
fi

log "Symlinking dotfiles with stow"
stow --dir="$DOTFILES" --target="$HOME" home

# --- 4. Machine-local overlay files -----------------------------------------
# Untracked files the tracked config Include-s/sources for per-machine specifics
# (work vs personal vs homelab). Created empty so the includes never dangle; put
# machine-specific entries in them, never in the public repo. See README.
if [ ! -f "$HOME/.ssh/config.local" ]; then
  log "Creating ~/.ssh/config.local (untracked SSH host overrides)"
  mkdir -p "$HOME/.ssh"
  touch "$HOME/.ssh/config.local"
  chmod 600 "$HOME/.ssh/config.local"
fi
# git Include-s this (home/.gitconfig [include]); git ignores a missing include,
# but create it so it's discoverable. Good home for a per-dir work identity:
#   [includeIf "gitdir:~/work/"]\n     path = ~/.gitconfig.work
if [ ! -f "$HOME/.gitconfig_local" ]; then
  log "Creating ~/.gitconfig_local (untracked git overrides)"
  touch "$HOME/.gitconfig_local"
fi
# fish sources this (conf.d/zzz-local.fish); kept outside the stowed tree.
if [ ! -f "$HOME/.config/dotfiles/local.fish" ]; then
  log "Creating ~/.config/dotfiles/local.fish (untracked fish overrides)"
  mkdir -p "$HOME/.config/dotfiles"
  touch "$HOME/.config/dotfiles/local.fish"
fi
# brew reads this opt-in list (one Brewfile.d/<name> bundle name per line); see step 1.
if [ ! -f "$HOME/.config/dotfiles/brewfiles" ]; then
  log "Creating ~/.config/dotfiles/brewfiles (untracked opt-in Brewfile bundle list)"
  mkdir -p "$HOME/.config/dotfiles"
  touch "$HOME/.config/dotfiles/brewfiles"
fi
# brew loads this for machine-private additions (work-only software); see step 1.
if [ ! -f "$HOME/.config/dotfiles/Brewfile.local" ]; then
  log "Creating ~/.config/dotfiles/Brewfile.local (untracked Brewfile additions)"
  mkdir -p "$HOME/.config/dotfiles"
  touch "$HOME/.config/dotfiles/Brewfile.local"
fi

# --- 5. Fish plugins (fisher) -----------------------------------------------
# fisher update installs everything listed in the now-symlinked fish_plugins.
log "Installing fish plugins (fisher)"
fish -c '
  if not functions -q fisher
    curl -sL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source
    fisher install jorgebucaran/fisher
  end
  fisher update
'

# --- 6. tmux plugins (TPM) --------------------------------------------------
# Clone TPM if missing, then install the plugins declared in the stowed tmux.conf.
TPM_DIR="$HOME/.config/tmux/plugins/tpm"
if [ ! -d "$TPM_DIR" ]; then
  log "Installing TPM (tmux plugin manager)"
  git clone --depth 1 https://github.com/tmux-plugins/tpm "$TPM_DIR"
fi
log "Installing tmux plugins (TPM)"
"$TPM_DIR/bin/install_plugins" >/dev/null 2>&1 || true

# --- 7. atuin history import ------------------------------------------------
# atuin starts with an empty database and only records commands run after it's
# installed. Backfill the pre-existing shell history (fish/bash/zsh) once so
# Ctrl+R search sees it. Idempotent: atuin dedupes on import, and it's a no-op
# on a machine with no prior history.
if command -v atuin >/dev/null 2>&1; then
  log "Importing existing shell history into atuin"
  atuin import auto >/dev/null 2>&1 || true
fi

# --- 8. iTerm2 preferences --------------------------------------------------
# Point iTerm2 at the tracked prefs folder in the repo. iTerm writes the plist
# back here on quit, so it's pointed directly at the repo (no stow symlink to
# clobber). Takes effect on iTerm2's next launch; fully quit it first if open.
log "Pointing iTerm2 at tracked preferences ($DOTFILES/iterm2)"
defaults write com.googlecode.iterm2 PrefsCustomFolder -string "$DOTFILES/iterm2"
defaults write com.googlecode.iterm2 LoadPrefsFromCustomFolder -bool true

# --- 9. Python CLI tools (uv) -----------------------------------------------
# Each non-comment line of uv_tools.txt is an argument list for uv tool install.
log "Installing uv tools"
# set -f (noglob) for the loop: lines are split on IFS intentionally, but a
# token like reuse[charset-normalizer] would otherwise glob-expand against the
# caller's CWD. The subshell keeps noglob from leaking into the rest of install.
(
  set -f
  while IFS= read -r tool; do
    case "$tool" in '' | \#*) continue ;; esac
    # shellcheck disable=SC2086  # intentional split: line holds tool + --with args
    uv tool install $tool
  done < "$DOTFILES/uv_tools.txt"
)

# uv drops tool shims into ~/.local/bin. Put it on PATH now so the later
# `command -v` checks (prek, claude) find them even when uv was already present
# (so the fresh-uv export near the top never ran) and the caller's PATH lacks it.
export PATH="$HOME/.local/bin:$PATH"

# Playwright needs a browser binary beyond the Python package. Install Chromium
# via the repo's *locked* dev dependency — the exact version `uv run pytest` uses
# (and what CI installs) — not the floating global `playwright` tool, whose version
# can drift and point pytest at a Chromium revision that was never downloaded. The
# build lands in a shared OS cache, so the global tool reuses it when versions
# match. Idempotent (skips if present); non-fatal so a slow/failed download never
# aborts the bootstrap.
log "Installing Playwright Chromium (browser for the docs-site tests)"
uv run --project "$DOTFILES" playwright install chromium \
  || log "  Playwright Chromium install failed; re-run install.sh to retry."

# --- 10. Auto-install prek hooks on clone (git template dir) ----------------
# .gitconfig's init.templateDir points at ~/.config/git/template; prek writes
# shims for all hook types so any stage a cloned repo configures gets installed.
# Each shim no-ops on repos without a pre-commit config.
if command -v prek >/dev/null 2>&1; then
  log "Configuring prek git template dir (~/.config/git/template)"
  # prek installs all the hook shims successfully, then runs a cosmetic
  # post-install check comparing `git config init.templateDir` against the target
  # via same_file::is_same_file, which does NOT expand `~`. Our templateDir is
  # stored tilde'd (correct — git expands it itself), so that stat hits a path
  # literally named `~/.config/git/template`, fails with ENOENT, and prek exits
  # non-zero (`error: No such file or directory (os error 2)`). The hooks are
  # already in place, so this is swallowed. Upstream bug in j178/prek (present on
  # main as of 2026-06). Does NOT affect `git clone`: git copies these shims into
  # new repos itself; prek's check only runs here, when we call init-template-dir.
  prek init-template-dir "$HOME/.config/git/template" \
    -t pre-commit -t pre-merge-commit -t pre-push -t pre-rebase -t prepare-commit-msg \
    -t commit-msg -t post-checkout -t post-commit -t post-merge -t post-rewrite \
    || log "prek init-template-dir exited non-zero (hooks installed; known prek tilde-expansion bug in its init.templateDir check — harmless)"
else
  log "Skipping prek git template dir (prek not installed)"
fi

# --- 11. Claude Code CLI (native installer; self-updates) -------------------
# Installed via the native installer (NOT a brew cask) on purpose: we want
# Claude Code's background auto-updates for this fast-moving tool. Installs to
# ~/.local/bin (already on PATH, same as the uv tools above). Only install when
# absent — the auto-updater keeps it current afterwards. Runs before the MCP
# step below so a first-run bootstrap can register servers without a re-run.
if ! command -v claude >/dev/null 2>&1; then
  log "Installing Claude Code CLI (native installer)"
  curl -fsSL https://claude.ai/install.sh | bash
  export PATH="$HOME/.local/bin:$PATH"
fi

# --- 12. Claude Code user-scope MCP servers ---------------------------------
# claude registers user-scope MCP servers into ~/.claude.json, which is
# machine-local state (project history, OAuth) and not stowable. So the
# declarative source of truth lives in claude_mcp.json and is replayed here,
# idempotently (remove-then-add).
#
# Secrets in claude_mcp.json are 1Password references ({{ op://... }}) resolved
# at install time via `op inject`, so no token is committed. Resolution runs as
# you, using the desktop app's CLI integration — the token only ever lands in
# ~/.claude.json (0600), never in the repo.
#
# Two skip paths keep first-run bootstrap safe:
#   - claude CLI absent          -> skip (normally installed by step 11 above;
#                                   safety net if that install failed).
#   - op absent / not signed in  -> register only secret-free servers; entries
#     whose {{ op://... }} couldn't resolve are left untouched (not clobbered),
#     so re-running after `op signin` adds them without disturbing the rest.
if command -v claude >/dev/null 2>&1; then
  log "Registering Claude Code MCP servers (claude_mcp.json)"

  if command -v op >/dev/null 2>&1 && op whoami >/dev/null 2>&1; then
    resolved_mcp="$(op inject -i "$DOTFILES/claude_mcp.json")"
  else
    grep -q 'op://' "$DOTFILES/claude_mcp.json" && \
      log "  1Password not signed in — skipping secret-backed servers; re-run after 'op signin'."
    resolved_mcp="$(cat "$DOTFILES/claude_mcp.json")"
  fi

  while IFS=$'\t' read -r name json; do
    if printf '%s' "$json" | grep -q 'op://'; then
      log "  skipping '$name' (unresolved 1Password reference)"
      continue
    fi
    claude mcp remove "$name" --scope user >/dev/null 2>&1 || true
    claude mcp add-json "$name" "$json" --scope user >/dev/null
  done < <(printf '%s' "$resolved_mcp" | jq -r 'to_entries[] | "\(.key)\t\(.value | tojson)"')
else
  log "Skipping Claude Code MCP setup (claude CLI not installed; see software_list.md)"
fi

# --- 13. Ollama model for GitLens' local AI ---------------------------------
# The stowed VS Code settings point GitLens' AI features at a local Ollama model
# (gitlens.ai.model = "ollama:qwen2.5-coder:7b"), so commit-message generation
# and explain-commit run offline — no cloud key, no Copilot. ollama-app (Brewfile
# cask) ships both the `ollama` CLI and a menu-bar app that serves the API on
# :11434 and auto-starts on login. Make sure the server is up and the model is
# pulled. Idempotent: re-launching a running app is a no-op and the (~4.7GB) pull
# is skipped when the model already exists; a failed pull is non-fatal.
OLLAMA_MODEL="qwen2.5-coder:7b"
if command -v ollama >/dev/null 2>&1; then
  if ! curl -fsS -m 2 http://localhost:11434/api/tags >/dev/null 2>&1; then
    log "Starting Ollama (server + login auto-start)"
    # Prefer the GUI app (it also registers the login item). `open -a` returns as
    # soon as the launch is *accepted*, not when the server is listening — so key
    # the fallback on actual API readiness, not on open's exit code: probe (curl
    # --retry-connrefused waits without a foreground sleep), and only if it's still
    # down, start a headless `ollama serve` and probe again.
    open -a Ollama 2>/dev/null || true
    if ! curl -fsS --retry 20 --retry-delay 1 --retry-connrefused -m 30 \
         http://localhost:11434/api/tags >/dev/null 2>&1; then
      ollama serve >/dev/null 2>&1 &
      curl -fsS --retry 20 --retry-delay 1 --retry-connrefused -m 30 \
        http://localhost:11434/api/tags >/dev/null 2>&1 \
        || log "  Ollama server didn't come up; start it and re-run to pull the model."
    fi
  fi
  if ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "$OLLAMA_MODEL"; then
    log "Ollama model $OLLAMA_MODEL already present"
  else
    log "Pulling Ollama model $OLLAMA_MODEL (~4.7GB, one-time)"
    ollama pull "$OLLAMA_MODEL" \
      || log "  Ollama pull failed (network?); re-run install.sh to retry."
  fi
else
  log "Skipping Ollama setup (ollama not installed; see Brewfile 'ollama-app')"
fi

# --- 14. macOS system defaults ----------------------------------------------
# Curated `defaults write` tweaks. Idempotent; restarts Finder/Dock at the end.
# Comment this out if you'd rather run it by hand (~/dotfiles/macos.sh).
log "Applying macOS system defaults (macos.sh)"
bash "$DOTFILES/macos.sh"

# --- 15. Dock layout --------------------------------------------------------
# Declarative Dock via dockutil. NOTE: this removes every current Dock item and
# rebuilds from dock.sh's list. Edit dock.sh (or comment out this step) first.
log "Applying Dock layout (dock.sh)"
bash "$DOTFILES/dock.sh"

log "Done. Restart your shell (or run 'exec fish') to pick everything up."
