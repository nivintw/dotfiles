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

# --- UI helpers -------------------------------------------------------------
# Presentation only; every step's behavior below is unchanged. Color is emitted
# ONLY when stdout is a TTY and NO_COLOR is unset (https://no-color.org). When
# piped, redirected, or NO_COLOR is set, the C_* vars are empty strings and the
# glyph helpers fall back to ASCII tags, so logs stay greppable and CI-clean.
# All of this is bash 3.2-safe: the early steps run under Apple's /bin/bash
# (before brew installs bash 5), so no associative arrays, no ${v^^} — just
# $'...' ANSI literals.
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'
  C_BLUE=$'\033[34m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'
  G_OK='✔'; G_ACTIVE='●'; G_WARN='⚠'; G_ERR='✗'
else
  C_RESET=''; C_BOLD=''; C_DIM=''
  C_BLUE=''; C_GREEN=''; C_YELLOW=''; C_RED=''
  G_OK='[ok]'; G_ACTIVE='[..]'; G_WARN='[!!]'; G_ERR='[xx]'
fi

ui_banner() { printf '\n%s%s%s\n' "$C_BOLD" "$1" "$C_RESET"; }
ui_step()   { printf '\n%s%s==>%s %s\n' "$C_BOLD" "$C_BLUE" "$C_RESET" "$1"; }
ui_ok()     { printf '%s%s%s %s\n'     "$C_GREEN"  "$G_OK"     "$C_RESET" "$1"; }
ui_active() { printf '%s%s%s %s\n'     "$C_BLUE"   "$G_ACTIVE" "$C_RESET" "$1"; }
ui_warn()   { printf '%s%s%s %s\n'     "$C_YELLOW" "$G_WARN"   "$C_RESET" "$1"; }
ui_err()    { printf '%s%s%s %s\n' >&2 "$C_RED"    "$G_ERR"    "$C_RESET" "$1"; }
ui_detail() { printf '   %s%s%s\n' "$C_DIM" "$1" "$C_RESET"; }

ui_banner "dotfiles bootstrap"

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
  ui_step "Installing Homebrew"
  NONINTERACTIVE=1 /bin/bash -c \
    "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Put brew on PATH for the rest of this script (Apple Silicon vs Intel).
  for brew_bin in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [ -x "$brew_bin" ] && eval "$("$brew_bin" shellenv)" && break
  done
fi
command -v brew >/dev/null 2>&1 || { ui_err "Homebrew install failed."; exit 1; }

if ! command -v uv >/dev/null 2>&1; then
  ui_step "Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # uv installs to ~/.local/bin (newer) or ~/.cargo/bin (older); cover both.
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || { ui_err "uv install failed."; exit 1; }

# --- 1. Homebrew formulae + casks -------------------------------------------
# brew bundle adopts already-present casks in place rather than clobbering them.
ui_step "Homebrew packages (brew bundle)"
brew bundle install --file="$DOTFILES/Brewfile"
ui_ok "Homebrew packages installed"

# Opt-in bundles (tracked, public): each Brewfile.d/<name>.brewfile is an overlay
# of software not wanted on every machine. The per-machine selection lives in
# ~/.config/dotfiles/bundles (untracked, one bundle name per line). Selection model:
#   - file exists             -> use it verbatim, no prompt (idempotent re-runs / CI)
#   - missing + TTY + fzf      -> interactive fzf --multi picker, persist the result
#   - missing, non-TTY/no fzf  -> seed a commented template, baseline only this run
# Absent/empty selection = baseline only, exactly what a machine that shouldn't get
# the personal apps leaves it as. See "Machine-local overlays" in the README.
ui_step "Opt-in Brewfile bundles"
bundles_dir="$DOTFILES/Brewfile.d"
bundles_sel="$HOME/.config/dotfiles/bundles"
mkdir -p "$HOME/.config/dotfiles"

# One-time migration from the pre-rename ~/.config/dotfiles/brewfiles list.
bundles_legacy="$HOME/.config/dotfiles/brewfiles"
if [ ! -f "$bundles_sel" ] && [ -f "$bundles_legacy" ]; then
  cp "$bundles_legacy" "$bundles_sel"
  ui_detail "migrated selection from legacy ~/.config/dotfiles/brewfiles"
fi

# Discover available bundles (basename minus the .brewfile suffix). bash 3.2 has
# no nullglob, so a non-matching glob stays literal — guard each candidate with -e.
# Every possibly-empty array expansion uses ${arr[@]+"${arr[@]}"} so `set -u`
# doesn't error on an unset array.
avail=()
for bf in "$bundles_dir"/*.brewfile; do
  [ -e "$bf" ] || continue
  avail=(${avail[@]+"${avail[@]}"} "$(basename "$bf" .brewfile)")
done

# Write the selection file: a self-documenting header + the available bundles as
# commented hints + the chosen names (bare, one per line). "$@" = chosen names.
write_bundles() {
  {
    echo '# Opt-in Brewfile bundles for this machine, one name per line. Each maps'
    echo '# to <repo>/Brewfile.d/<name>.brewfile. Lines starting with # are ignored.'
    echo '# Edit and re-run install.sh to change what gets installed.'
    echo '#'
    echo '# Available bundles:'
    for b in ${avail[@]+"${avail[@]}"}; do echo "#   $b"; done
    echo
    for n in "$@"; do echo "$n"; done
  } > "$bundles_sel"
}

if [ -f "$bundles_sel" ]; then
  : # existing selection — use as-is, no prompt
elif [ "${#avail[@]}" -eq 0 ]; then
  ui_detail "no bundles found in Brewfile.d/*.brewfile — baseline only"
  write_bundles
elif [ -t 0 ] && command -v fzf >/dev/null 2>&1; then
  ui_active "select bundles  ·  TAB toggles · ENTER confirms · ESC = none"
  # fzf --multi over the discovered names; --preview cats the bundle so you see
  # its casks/brews before opting in. ESC exits 130, which under `set -e` would
  # abort the whole bootstrap — swallow it with `|| true`; an empty pick is the
  # correct "baseline only" outcome.
  picked="$(
    printf '%s\n' ${avail[@]+"${avail[@]}"} \
      | fzf --multi --height=40% --reverse --border \
            --prompt='bundles> ' \
            --header='opt-in Brewfile bundles (none = baseline only)' \
            --preview="cat '$bundles_dir'/{}.brewfile" \
            --preview-window=right,60% \
      || true
  )"
  # shellcheck disable=SC2046  # intentional split of the newline-separated picks
  write_bundles $(printf '%s' "$picked")
  ui_detail "saved selection to ~/.config/dotfiles/bundles"
else
  ui_detail "non-interactive / no fzf — baseline only; edit ~/.config/dotfiles/bundles to opt in"
  write_bundles
fi

# Install each selected bundle. Same brew bundle call as the baseline; only the
# file path convention changed (Brewfile.d/<name>.brewfile).
installed_bundles=()
while IFS= read -r bundle; do
  case "$bundle" in '' | \#*) continue ;; esac
  bundle_file="$bundles_dir/$bundle.brewfile"
  if [ -f "$bundle_file" ]; then
    ui_active "installing opt-in bundle: $bundle"
    brew bundle install --file="$bundle_file"
    installed_bundles=(${installed_bundles[@]+"${installed_bundles[@]}"} "$bundle")
  else
    ui_warn "skipping opt-in bundle '$bundle' (no $bundle_file)"
  fi
done < "$bundles_sel"

if [ "${#installed_bundles[@]}" -eq 0 ]; then
  ui_ok "opt-in bundles: baseline only"
else
  ui_ok "opt-in bundles: ${installed_bundles[*]}"
fi

# Machine-PRIVATE additions (untracked, never in the public repo): work-only
# software, etc. The Homebrew analogue of ~/.gitconfig_local and ~/.ssh/config.local.
brew_local="$HOME/.config/dotfiles/Brewfile.local"
if [ -f "$brew_local" ]; then
  ui_step "Machine-private Brewfile additions (Brewfile.local)"
  brew bundle install --file="$brew_local"
  ui_ok "machine-private additions installed"
fi

# --- 2. Privileged setup — one sudo session ---------------------------------
# Everything that needs root is grouped here so a single authentication covers
# it all: sudo caches its timestamp (~5 min) and these steps run back-to-back.
# Nothing long-running or curl|bash sits between need_sudo and the sudo -k at the
# end of the block — that's what keeps the Homebrew/uv bootstraps above and the
# fisher/Claude installers below from ever running with a warm ticket.
ui_step "Privileged setup (single sudo session)"
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
    ui_active "enabling Touch ID for sudo (/etc/pam.d/sudo_local)"
    sudo tee /etc/pam.d/sudo_local >/dev/null <<EOF
auth       optional       $pam_reattach
auth       sufficient     pam_tid.so
EOF
    ui_ok "Touch ID for sudo enabled"
  else
    ui_ok "Touch ID for sudo already enabled"
  fi
else
  ui_warn "skipping Touch ID for sudo (/etc/pam.d/sudo has no sudo_local include)"
fi

# Make fish the default login shell. fish is brew-installed (see Brewfile); a
# brew upgrade can disturb an already-open fish session until it's restarted —
# accepted tradeoff. Register it in /etc/shells, then chsh *via sudo*: root can
# set the login shell without a separate password prompt, keeping this inside the
# single sudo session (a bare `chsh` would prompt for your password on its own).
fish_bin="$(command -v fish)"
if ! grep -qxF "$fish_bin" /etc/shells; then
  ui_active "registering $fish_bin in /etc/shells"
  echo "$fish_bin" | sudo tee -a /etc/shells >/dev/null
fi
if [ "${SHELL:-}" != "$fish_bin" ]; then
  ui_active "setting fish as the default shell (chsh)"
  sudo chsh -s "$fish_bin" "$(id -un)"
  ui_ok "fish set as the default shell"
else
  ui_ok "fish already the default shell"
fi

# macOS application firewall + stealth mode (don't respond to ping/port scans);
# both ship OFF on macOS. Done here to stay within the single sudo session rather
# than at the very end of the run.
ui_active "enabling the macOS application firewall + stealth mode"
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on >/dev/null
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on >/dev/null

# Done with root. Drop the ticket so nothing downstream (the fisher/Claude
# curl|bash installers included) runs with a warm sudo timestamp.
sudo -k
ui_ok "privileged setup complete"

# --- 3. Symlink dotfiles into $HOME -----------------------------------------
# Stow refuses to overwrite existing real files. Remove known managed files that
# tools may generate as real files on first run so stow can replace them with
# symlinks. Only real files are removed (never existing symlinks), so this stays
# idempotent; stow recreates each as a symlink below.
ui_step "dotfiles symlinks (stow)"
managed_files=(
  "$HOME/Library/Application Support/Code/User/settings.json"  # VS Code / Settings Sync
  "$HOME/.config/atuin/config.toml"                            # atuin writes a default on first run
  "$HOME/.config/topgrade.toml"                                # topgrade --edit-config seeds a default
)
for f in "${managed_files[@]}"; do
  if [ -f "$f" ] && [ ! -L "$f" ]; then
    ui_active "removing existing real file so stow can symlink it: $f"
    rm "$f"
  fi
done

# Preflight: stow aborts mid-run on the FIRST conflicting file, so do a dry run
# (-n) first to surface ALL conflicts up front. The dry run plans without touching
# the filesystem and applies stow's own ignore rules (.stow-local-ignore: .DS_Store,
# the control file, README/LICENSE, etc.), so it never false-positives on files
# stow wouldn't link anyway. This repo expects to own its paths in a clean $HOME;
# the managed_files above are the known auto-generated exceptions, already cleared.
ui_active "checking for conflicts (dry run)"
if ! stow_plan="$(stow -n -v --dir="$DOTFILES" --target="$HOME" home 2>&1)"; then
  ui_err "these files already exist in \$HOME and would be replaced by this repo's versions, so aborting."
  ui_detail "Back them up and/or merge their contents into the repo, then re-run install.sh:"
  printf '%s\n' "$stow_plan" | grep -E 'cannot stow' >&2 || printf '%s\n' "$stow_plan" >&2
  exit 1
fi

stow --dir="$DOTFILES" --target="$HOME" home
ui_ok "dotfiles symlinked (stow, 0 conflicts)"

# --- 4. Machine-local overlay files -----------------------------------------
# Untracked files the tracked config Include-s/sources for per-machine specifics
# (work vs personal vs homelab). Seeded with commented examples so the includes
# never dangle and the format is self-documenting; put machine-specific entries in
# them, never in the public repo. See README. (The opt-in bundle selection,
# ~/.config/dotfiles/bundles, is created in step 1.)
ui_step "Machine-local overlay files"

seed_if_absent() {
  # $1 = destination path; commented template arrives on stdin (a heredoc). The
  # file is created (with parent dirs) only when absent, so this stays idempotent
  # and never clobbers content you've added. Untracked + outside the repo, so no
  # SPDX header is needed.
  if [ ! -f "$1" ]; then
    mkdir -p "$(dirname "$1")"
    cat > "$1"
    ui_active "created $1"
  fi
}

# SSH Include-s this (home/.ssh/config). Kept 0600 — ssh ignores group/world-
# readable include files.
seed_if_absent "$HOME/.ssh/config.local" <<'EOF'
# Machine-local SSH config (untracked). Included by ~/.ssh/config.
# Example:
#   Host myserver
#       HostName 10.0.0.5
#       User me
EOF
chmod 600 "$HOME/.ssh/config.local"

# git Include-s this (home/.gitconfig [include]); git ignores a missing include,
# but seed it so it's discoverable. Good home for a per-dir work identity.
seed_if_absent "$HOME/.gitconfig_local" <<'EOF'
# Machine-local git config (untracked). Included by ~/.gitconfig.
# Good home for a per-directory work identity:
#   [includeIf "gitdir:~/work/"]
#       path = ~/.gitconfig.work   # work email, signing key, etc. — untracked
EOF

# fish sources this (conf.d/zzz-local.fish); kept outside the stowed tree.
seed_if_absent "$HOME/.config/dotfiles/local.fish" <<'EOF'
# Machine-local fish config (untracked). Sourced last by conf.d/zzz-local.fish.
# Example:
#   set -gx SOME_API_TOKEN ...
#   alias work-vpn 'sudo openconnect ...'
EOF

# brew loads this for machine-private additions (work-only software); see step 1.
seed_if_absent "$HOME/.config/dotfiles/Brewfile.local" <<'EOF'
# Machine-private Homebrew additions (untracked — never committed). Same Ruby DSL
# as the repo Brewfile; loaded automatically by install.sh. For work-only or
# sensitive software the public repo shouldn't carry.
# Example:
#   cask "company-vpn"
#   brew "internal-cli-tool"
EOF

ui_ok "overlay files ready"

# --- 5. Fish plugins (fisher) -----------------------------------------------
# fisher update installs everything listed in the now-symlinked fish_plugins.
ui_step "Fish plugins (fisher)"
fish -c '
  if not functions -q fisher
    curl -sL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source
    fisher install jorgebucaran/fisher
  end
  fisher update
'
ui_ok "fish plugins installed"

# --- 6. tmux plugins (TPM) --------------------------------------------------
# Clone TPM if missing, then install the plugins declared in the stowed tmux.conf.
ui_step "tmux plugins (TPM)"
TPM_DIR="$HOME/.config/tmux/plugins/tpm"
if [ ! -d "$TPM_DIR" ]; then
  ui_active "installing TPM (tmux plugin manager)"
  git clone --depth 1 https://github.com/tmux-plugins/tpm "$TPM_DIR"
fi
"$TPM_DIR/bin/install_plugins" >/dev/null 2>&1 || true
ui_ok "tmux plugins installed"

# --- 7. atuin history import ------------------------------------------------
# atuin starts with an empty database and only records commands run after it's
# installed. Backfill the pre-existing shell history (fish/bash/zsh) once so
# Ctrl+R search sees it. Idempotent: atuin dedupes on import, and it's a no-op
# on a machine with no prior history.
if command -v atuin >/dev/null 2>&1; then
  ui_step "Importing existing shell history into atuin"
  atuin import auto >/dev/null 2>&1 || true
  ui_ok "shell history imported into atuin"
fi

# --- 8. iTerm2 preferences --------------------------------------------------
# Point iTerm2 at the tracked prefs folder in the repo. iTerm writes the plist
# back here on quit, so it's pointed directly at the repo (no stow symlink to
# clobber). Takes effect on iTerm2's next launch; fully quit it first if open.
ui_step "iTerm2 preferences"
defaults write com.googlecode.iterm2 PrefsCustomFolder -string "$DOTFILES/iterm2"
defaults write com.googlecode.iterm2 LoadPrefsFromCustomFolder -bool true
ui_ok "iTerm2 pointed at tracked preferences ($DOTFILES/iterm2)"

# --- 9. Python CLI tools (uv) -----------------------------------------------
# Each non-comment line of uv_tools.txt is an argument list for uv tool install.
ui_step "Python CLI tools (uv)"
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
ui_ok "uv tools installed"

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
ui_active "installing Playwright Chromium (browser for the docs-site tests)"
uv run --project "$DOTFILES" playwright install chromium \
  || ui_warn "Playwright Chromium install failed; re-run install.sh to retry."

# --- 10. Auto-install prek hooks on clone (git template dir) ----------------
# .gitconfig's init.templateDir points at ~/.config/git/template; prek writes
# shims for all hook types so any stage a cloned repo configures gets installed.
# Each shim no-ops on repos without a pre-commit config.
if command -v prek >/dev/null 2>&1; then
  ui_step "prek git template dir (~/.config/git/template)"
  # prek installs all the hook shims successfully, then runs a cosmetic
  # post-install check comparing `git config init.templateDir` against the target
  # via same_file::is_same_file, which does NOT expand `~`. Our templateDir is
  # stored tilde'd (correct — git expands it itself), so that stat hits a path
  # literally named `~/.config/git/template`, fails with ENOENT, and prek exits
  # non-zero (`error: No such file or directory (os error 2)`). The hooks are
  # already in place, so this is swallowed. Upstream bug in j178/prek (present on
  # main as of 2026-06). Does NOT affect `git clone`: git copies these shims into
  # new repos itself; prek's check only runs here, when we call init-template-dir.
  if prek init-template-dir "$HOME/.config/git/template" \
    -t pre-commit -t pre-merge-commit -t pre-push -t pre-rebase -t prepare-commit-msg \
    -t commit-msg -t post-checkout -t post-commit -t post-merge -t post-rewrite; then
    ui_ok "prek hook shims installed"
  else
    ui_warn "prek init-template-dir exited non-zero (hooks installed; known prek tilde-expansion bug in its init.templateDir check — harmless)"
  fi
else
  ui_warn "skipping prek git template dir (prek not installed)"
fi

# --- 11. Claude Code CLI (native installer; self-updates) -------------------
# Installed via the native installer (NOT a brew cask) on purpose: we want
# Claude Code's background auto-updates for this fast-moving tool. Installs to
# ~/.local/bin (already on PATH, same as the uv tools above). Only install when
# absent — the auto-updater keeps it current afterwards. Runs before the MCP
# step below so a first-run bootstrap can register servers without a re-run.
if ! command -v claude >/dev/null 2>&1; then
  ui_step "Installing Claude Code CLI (native installer)"
  curl -fsSL https://claude.ai/install.sh | bash
  export PATH="$HOME/.local/bin:$PATH"
  ui_ok "Claude Code CLI installed"
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
  ui_step "Claude Code MCP servers (claude_mcp.json)"

  if command -v op >/dev/null 2>&1 && op whoami >/dev/null 2>&1; then
    resolved_mcp="$(op inject -i "$DOTFILES/claude_mcp.json")"
  else
    if grep -q 'op://' "$DOTFILES/claude_mcp.json"; then
      ui_warn "1Password not signed in — skipping secret-backed servers; re-run after 'op signin'."
    fi
    resolved_mcp="$(cat "$DOTFILES/claude_mcp.json")"
  fi

  while IFS=$'\t' read -r name json; do
    if printf '%s' "$json" | grep -q 'op://'; then
      ui_warn "skipping '$name' (unresolved 1Password reference)"
      continue
    fi
    claude mcp remove "$name" --scope user >/dev/null 2>&1 || true
    claude mcp add-json "$name" "$json" --scope user >/dev/null
  done < <(printf '%s' "$resolved_mcp" | jq -r 'to_entries[] | "\(.key)\t\(.value | tojson)"')
  ui_ok "MCP servers registered"
else
  ui_warn "skipping Claude Code MCP setup (claude CLI not installed; see software_list.md)"
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
  ui_step "Ollama model for GitLens ($OLLAMA_MODEL)"
  if ! curl -fsS -m 2 http://localhost:11434/api/tags >/dev/null 2>&1; then
    ui_active "starting Ollama (server + login auto-start)"
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
        || ui_warn "Ollama server didn't come up; start it and re-run to pull the model."
    fi
  fi
  if ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -qx "$OLLAMA_MODEL"; then
    ui_ok "Ollama model $OLLAMA_MODEL already present"
  else
    ui_active "pulling Ollama model $OLLAMA_MODEL (~4.7GB, one-time)"
    if ollama pull "$OLLAMA_MODEL"; then
      ui_ok "Ollama model $OLLAMA_MODEL pulled"
    else
      ui_warn "Ollama pull failed (network?); re-run install.sh to retry."
    fi
  fi
else
  ui_warn "skipping Ollama setup (ollama not installed; see Brewfile 'ollama-app')"
fi

# --- 14. macOS system defaults ----------------------------------------------
# Curated `defaults write` tweaks. Idempotent; restarts Finder/Dock at the end.
# Comment this out if you'd rather run it by hand (~/dotfiles/macos.sh).
ui_step "macOS system defaults (macos.sh)"
bash "$DOTFILES/macos.sh"
ui_ok "macOS defaults applied"

# --- 15. Dock layout --------------------------------------------------------
# Declarative Dock via dockutil. NOTE: this removes every current Dock item and
# rebuilds from dock.sh's list. Edit dock.sh (or comment out this step) first.
ui_step "Dock layout (dock.sh)"
bash "$DOTFILES/dock.sh"
ui_ok "Dock layout applied"

ui_banner "dotfiles bootstrap complete"
ui_detail "Restart your shell (or run 'exec fish') to pick everything up."
