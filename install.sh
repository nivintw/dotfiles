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
  C_RESET=$'\033[0m'
  C_BOLD=$'\033[1m'
  C_DIM=$'\033[2m'
  C_BLUE=$'\033[34m'
  C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m'
  C_RED=$'\033[31m'
  G_OK='✔'
  G_ACTIVE='●'
  G_WARN='⚠'
  G_ERR='✗'
else
  C_RESET=''
  C_BOLD=''
  C_DIM=''
  C_BLUE=''
  C_GREEN=''
  C_YELLOW=''
  C_RED=''
  G_OK='[ok]'
  G_ACTIVE='[..]'
  G_WARN='[!!]'
  G_ERR='[xx]'
fi

ui_banner() { printf '\n%s%s%s\n' "$C_BOLD" "$1" "$C_RESET"; }
ui_step() { printf '\n%s%s==>%s %s\n' "$C_BOLD" "$C_BLUE" "$C_RESET" "$1"; }
ui_ok() { printf '%s%s%s %s\n' "$C_GREEN" "$G_OK" "$C_RESET" "$1"; }
ui_active() { printf '%s%s%s %s\n' "$C_BLUE" "$G_ACTIVE" "$C_RESET" "$1"; }
# Every ui_warn is also remembered (WARNINGS) so the closing summary can replay
# everything that needed attention — you never have to scroll back through a long,
# noisy install (e.g. a transient brew download failure) to find what went wrong.
WARNINGS=()
ui_warn() {
  WARNINGS=(${WARNINGS[@]+"${WARNINGS[@]}"} "$1")
  printf '%s%s%s %s\n' "$C_YELLOW" "$G_WARN" "$C_RESET" "$1"
}
ui_err() { printf '%s%s%s %s\n' "$C_RED" "$G_ERR" "$C_RESET" "$1" >&2; }
ui_detail() { printf '   %s%s%s\n' "$C_DIM" "$1" "$C_RESET"; }

# retry DESC MAX CMD... — run CMD, retrying up to MAX times with a short backoff. Returns 0
# on the first success, non-zero if every attempt fails. For network bootstraps (fisher,
# TPM/git clones, curl|bash installers, package downloads) where a transient blip shouldn't
# abort an otherwise idempotent install. Callers make it non-fatal with `|| ui_warn ...` so
# a persistent failure degrades to a warning + re-run hint instead of killing the bootstrap.
retry() {
  local desc="$1" max="$2" n=1
  shift 2
  while :; do
    if "$@"; then return 0; fi
    [ "$n" -ge "$max" ] && return 1
    ui_detail "$desc failed (attempt $n/$max) — retrying in 3s"
    n=$((n + 1))
    sleep 3
  done
}

# --- Opt-in bundle discovery + CLI args -------------------------------------
# Discover the available opt-in bundles (Brewfile.d/<name>.brewfile, basename
# minus the suffix) up front because both --help (lists them) and --bundle
# (validates against them) run before the macOS guard below. bash 3.2 has no
# nullglob, so a non-matching glob stays literal — guard each candidate with -e.
# Every possibly-empty array expansion uses ${arr[@]+"${arr[@]}"} so `set -u`
# doesn't error on an unset array.
bundles_dir="$DOTFILES/Brewfile.d"
avail=()
for bf in "$bundles_dir"/*.brewfile; do
  [ -e "$bf" ] || continue
  avail=(${avail[@]+"${avail[@]}"} "$(basename "$bf" .brewfile)")
done

usage() {
  local list='  (none found)'
  [ "${#avail[@]}" -gt 0 ] && list="$(printf '  %s\n' ${avail[@]+"${avail[@]}"})"
  cat <<EOF
dotfiles bootstrap — converge this Mac to the state declared in the repo.

Usage: install.sh [options]

Options:
  --bundle NAME    Opt into Brewfile bundle NAME and persist the choice.
                   Repeatable; bypasses the interactive picker (scriptable).
  --no-bundles     Opt into no bundles (baseline only); bypass the picker.
  --keep-bundles   Keep the saved selection as-is; skip the picker without
                   rewriting it. Can't be combined with --bundle/--no-bundles.
  --core           Core profile: install CLI formulae only — skip the GUI app and
                   font casks (and, with them, the Ollama app + its model pull). For
                   headless/minimal installs and the VM smoke harness.
  -h, --help       Show this help and exit.

Opt-in Brewfile bundles (Brewfile.d/<name>.brewfile):
$list

With no --bundle/--no-bundles flag on an interactive terminal, install.sh opens
an fzf multi-select pre-seeded with the current selection, ready to amend.
--keep-bundles skips that picker and reuses the saved selection unchanged.
Without a usable fzf picker (non-interactive, or fzf missing) it reuses
~/.config/dotfiles/bundles, or installs the baseline only when that file is absent.
EOF
}

# Fail fast (before any install work) if a requested bundle name isn't one of the
# discovered ones, so a typo can't silently persist a bogus selection file.
require_known_bundle() {
  local want="$1" a
  for a in ${avail[@]+"${avail[@]}"}; do
    [ "$a" = "$want" ] && return 0
  done
  ui_err "unknown bundle: '$want'"
  ui_detail "available: ${avail[*]:-(none)}"
  exit 2
}

# Append NAME to requested_bundles unless it's already there, so a repeated
# --bundle flag persists one line per bundle, not a duplicate.
add_requested_bundle() {
  local want="$1" b
  for b in ${requested_bundles[@]+"${requested_bundles[@]}"}; do
    [ "$b" = "$want" ] && return 0
  done
  requested_bundles=(${requested_bundles[@]+"${requested_bundles[@]}"} "$want")
}

# Parse CLI args. --bundle/--no-bundles set an authoritative selection that
# bypasses the picker; bundles_from_flags records that a flag was given, so an
# explicit empty selection (--no-bundles) stays distinct from "no flag → prompt".
# --keep-bundles is the opposite: skip the picker but leave the saved selection
# untouched (keep_bundles), so it can't be combined with the two that rewrite it.
requested_bundles=()
bundles_from_flags=0
keep_bundles=0
# Core profile. Exported so it reaches _brew_bundle and the verify_install call at the end of
# this run (and any sub-shell). The Ollama step isn't flag-driven: --core skips the ollama-app
# cask, so its `command -v ollama` guard self-skips — a transitive effect, not a DOTFILES_CORE read.
export DOTFILES_CORE=0
while [ "$#" -gt 0 ]; do
  case "$1" in
  -h | --help)
    usage
    exit 0
    ;;
  --core)
    DOTFILES_CORE=1
    shift
    ;;
  --no-bundles)
    bundles_from_flags=1
    shift
    ;;
  --keep-bundles)
    keep_bundles=1
    shift
    ;;
  --bundle)
    shift
    [ "$#" -gt 0 ] || {
      ui_err "--bundle requires a NAME"
      exit 2
    }
    require_known_bundle "$1"
    add_requested_bundle "$1"
    bundles_from_flags=1
    shift
    ;;
  --bundle=*)
    _name="${1#--bundle=}"
    require_known_bundle "$_name"
    add_requested_bundle "$_name"
    bundles_from_flags=1
    shift
    ;;
  --)
    shift
    break
    ;;
  -* | *)
    ui_err "unexpected argument: $1"
    echo >&2
    usage >&2
    exit 2
    ;;
  esac
done

# --keep-bundles preserves the saved selection; --bundle/--no-bundles rewrite it.
# Asking for both is contradictory — reject it rather than silently pick one.
if [ "$keep_bundles" -eq 1 ] && [ "$bundles_from_flags" -eq 1 ]; then
  ui_err "--keep-bundles can't be combined with --bundle/--no-bundles"
  exit 2
fi

ui_banner "dotfiles bootstrap"

# --- macOS only -------------------------------------------------------------
# This bootstrap is macOS-specific: Homebrew prefixes, Touch-ID PAM, chsh, the
# application firewall, `defaults`, and dockutil all assume macOS. Fail fast
# rather than dying mid-run (e.g. at the firewall step inside the sudo fence) —
# matching the self-guards already in dock.sh and macos.sh.
if [ "$(uname)" != "Darwin" ]; then
  ui_err "install.sh supports macOS only (detected $(uname)). Aborting."
  exit 1
fi

# --- sudo: one authentication for the post-bundle privileged block ----------
# Root is needed for Touch-ID PAM, /etc/shells + chsh, the firewall, and the rare
# cask that ships a .pkg (microsoft-office is the only one in this repo).
#
# The fact this design is built around: `brew bundle` INVALIDATES the sudo
# timestamp. A ticket acquired before the bundle is gone by the time the bundle
# finishes — confirmed on this stack for BOTH the tty-keyed default and a global
# (timestamp_type=global) timestamp, and it is NOT a `sudo -k` (Homebrew issues
# none). So a ticket cannot be "kept warm" across the bundle by any means: an
# earlier background-refresher design (acquire before the bundle, refresh every 50s)
# could not survive the wipe — once it lands, a non-interactive `sudo -n` refresh
# can't revive the ticket — so it re-prompted anyway. Acquiring sudo BEFORE the
# bundle is pure waste: it spends a prompt brew then discards, and the privileged
# block after the bundle has to authenticate AGAIN — the "two Touch ID prompts" bug.
#
# So we do NOT span the bundle. Touch ID is enabled up front (free on a re-run —
# the contents check in enable_touch_id_sudo reads sudo_local WITHOUT sudo — and on
# a fresh machine it makes any cask password prompt during the bundle a fingerprint
# tap). sudo proper is acquired exactly ONCE, for the single contiguous privileged
# block AFTER the bundle (Touch-ID finalize, /etc/shells + chsh, firewall): one
# authentication, a fingerprint tap on a re-run. The ticket is dropped (sudo -k) at
# the end of that block, BEFORE any curl|bash installer runs (Homebrew/uv already
# ran above; fisher/Claude run later), so no third-party bootstrap executes with a
# live, passwordless ticket. The EXIT trap drops it even if the run aborts.
trap 'sudo -k 2>/dev/null || true' EXIT

# Enable (and keep current) Touch ID for sudo via /etc/pam.d/sudo_local — NOT
# /etc/pam.d/sudo, which macOS rewrites on OS updates. pam_reattach (Brewfile) makes
# it work inside tmux/screen and must precede pam_tid; it only exists AFTER brew
# bundle, so this is called twice: once before the bundle (pam_tid only — enough for
# the terminal running the installer) and again after (adds the pam_reattach line).
# Idempotent: the file is only rewritten when its contents would change. The
# contents check reads sudo_local with a plain `cat` (it's world-readable, mode
# 0644 — verify_install.sh reads it the same way), NOT `sudo cat`, so a re-run where
# the file is already correct needs no sudo here at all — which is what lets the
# pre-bundle call cost zero prompts (see the sudo notes above).
#
# The "Touch ID is on but it still asks for my password" failure (enabled here, but
# no fingerprint enrolled, so pam_tid SILENTLY falls back to a password) is caught
# and reported once, deterministically, by the closing verification summary —
# scripts/verify_install.sh check #5, via bioutil -c. Not nagged here so the
# message isn't emitted twice (this runs twice per install).
enable_touch_id_sudo() {
  if [ ! -f /etc/pam.d/sudo ] || ! grep -q 'sudo_local' /etc/pam.d/sudo; then
    ui_warn "Touch ID for sudo unavailable (/etc/pam.d/sudo has no sudo_local include — likely MDM-managed); sudo will prompt for your password"
    return 0
  fi
  pam_reattach="$(brew --prefix 2>/dev/null)/lib/pam/pam_reattach.so"
  desired="auth       sufficient     pam_tid.so"
  if [ -f "$pam_reattach" ]; then
    desired="auth       optional       $pam_reattach
auth       sufficient     pam_tid.so"
  fi
  if [ "$(cat /etc/pam.d/sudo_local 2>/dev/null)" != "$desired" ]; then
    printf '%s\n' "$desired" | sudo tee /etc/pam.d/sudo_local >/dev/null
    ui_ok "Touch ID for sudo enabled (/etc/pam.d/sudo_local)"
  fi
}

# --- 0. Bootstrap toolchain (Homebrew + uv) ---------------------------------
# Everything else (fish, stow, the rest) comes from brew bundle below.
# These two are network curl|bash bootstraps like the later fisher/Claude steps, so they get
# the same retry treatment — a transient blip on the very first network op shouldn't kill the
# whole install. Capture the installer script first (so a failed download actually fails the
# attempt and triggers a retry — piping curl straight into a shell hides a fetch failure as an
# empty no-op), then run it. A PERSISTENT failure still aborts via the command -v check below.
if ! command -v brew >/dev/null 2>&1; then
  ui_step "Installing Homebrew"
  _install_brew() {
    local script
    script="$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || return 1
    [ -n "$script" ] || return 1
    NONINTERACTIVE=1 /bin/bash -c "$script"
  }
  retry "Homebrew install" 3 _install_brew || true
  # Put brew on PATH for the rest of this script (Apple Silicon vs Intel).
  for brew_bin in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [ -x "$brew_bin" ] && eval "$("$brew_bin" shellenv)" && break
  done
fi
command -v brew >/dev/null 2>&1 || {
  ui_err "Homebrew install failed."
  exit 1
}

if ! command -v uv >/dev/null 2>&1; then
  ui_step "Installing uv"
  _install_uv() {
    local script
    script="$(curl -LsSf https://astral.sh/uv/install.sh)" || return 1
    [ -n "$script" ] || return 1
    printf '%s\n' "$script" | sh
  }
  retry "uv install" 3 _install_uv || true
  # uv installs to ~/.local/bin (newer) or ~/.cargo/bin (older); cover both.
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
command -v uv >/dev/null 2>&1 || {
  ui_err "uv install failed."
  exit 1
}

# --- 1. Homebrew formulae + casks -------------------------------------------

# Homebrew refuses to load a formula/cask from an UNTRUSTED third-party tap, which aborts
# `brew bundle` outright on a clean machine (e.g. terraform-linters/tap for tflint,
# cirruslabs/cli for tart). So before bundling from any Brewfile, trust the taps it declares.
# `brew trust` changes Homebrew's trusted-tap set, so this is explicit (not silent) and only
# attempted where the subcommand exists — older Homebrew has no trust gate. Non-fatal: a
# failed trust is a warning; the closing `brew bundle check` still reports anything missing.
# brewfile_taps()/brewfile_core() are the pure, unit-tested Brewfile parsers
# (scripts/brewfile_taps.sh, scripts/brewfile_core.sh).
# shellcheck source=/dev/null
. "$DOTFILES/scripts/brewfile_taps.sh"
# shellcheck source=/dev/null
. "$DOTFILES/scripts/brewfile_core.sh"
_trust_brewfile_taps() {
  brew commands 2>/dev/null | grep -qx trust || return 0
  while IFS= read -r _tap; do
    [ -n "$_tap" ] || continue
    brew tap "$_tap" >/dev/null 2>&1 || true
    if brew trust "$_tap" >/dev/null 2>&1; then
      ui_detail "trusted tap: $_tap"
    else
      ui_warn "could not trust tap $_tap — its packages may fail to install (retry: brew trust $_tap)"
    fi
  done <<EOF
$(brewfile_taps "$1")
EOF
}
# Every bundle install goes through here: trust the file's declared taps, then bundle. Under
# the --core profile (DOTFILES_CORE=1) bundle a casks-stripped copy so only CLI formulae land.
_brew_bundle() {
  _trust_brewfile_taps "$1"
  if [ "${DOTFILES_CORE:-0}" != "1" ]; then
    brew bundle install --file="$1"
    return
  fi
  local core_bf rc
  core_bf="$(mktemp -t brewfile-core)"
  brewfile_core "$1" >"$core_bf"
  brew bundle install --file="$core_bf"
  rc=$?
  rm -f "$core_bf"
  return "$rc"
}

# Enable Touch ID for sudo BEFORE the bundle — but do NOT acquire a lasting ticket
# here (brew bundle would wipe it; see the sudo notes above). On a re-run this is a
# no-op that needs no sudo (the contents check reads sudo_local without sudo); on a
# fresh machine it costs one typed password to write the PAM file, so that any cask
# password prompt during the bundle is a fingerprint tap instead. sudo proper is
# acquired once, after the bundle, in step 2.
ui_step "Touch ID for sudo"
enable_touch_id_sudo # pam_tid now; the pam_reattach (tmux) line is added in step 2

# brew bundle adopts already-present casks in place rather than clobbering them.
# Non-fatal: a transient single-package failure shouldn't abort the whole bootstrap
# (the rest is idempotent and re-runnable). The closing summary runs `brew bundle
# check` and lists precisely what's still missing, so you don't scroll back.
ui_step "Homebrew packages (brew bundle)"
if _brew_bundle "$DOTFILES/Brewfile"; then
  ui_ok "Homebrew packages installed"
else
  ui_warn "some baseline Homebrew packages failed to install (see output above) — the summary lists what's still missing; re-run install.sh to retry"
fi

# Opt-in bundles (tracked, public): each Brewfile.d/<name>.brewfile is an overlay
# of software not wanted on every machine. The per-machine selection lives in
# ~/.config/dotfiles/bundles (untracked, one bundle name per line). Precedence,
# matching the if/elif chain below in order:
#   - --keep-bundles flag          -> reuse the saved selection as-is, no picker, no rewrite
#   - --bundle/--no-bundles flags  -> authoritative, validated, persisted, no prompt (scriptable)
#   - else no bundles available    -> baseline only (nothing to pick)
#   - else TTY + fzf               -> interactive picker, pre-seeded with the current selection
#   - else existing selection file -> reuse as-is, no picker (idempotent non-TTY / CI re-runs)
#   - else                         -> baseline only, seed a commented template
# Absent/empty selection = baseline only, exactly what a machine that shouldn't get
# the personal apps leaves it as. See "Machine-local overlays" in the README.
ui_step "Opt-in Brewfile bundles"
# write_bundles / parse_bundles / fzf_preselect_bind — the selection-file writer,
# its inverse parser, and the picker pre-seed helper, factored into a sourceable
# lib so they're unit-tested (tests/bundle_select.bats) without running this
# bootstrap. Sourcing has no side effects. (avail/bundles_dir are set up top.)
# shellcheck source=scripts/bundle_select.sh
. "$DOTFILES/scripts/bundle_select.sh"
bundles_sel="$HOME/.config/dotfiles/bundles"
mkdir -p "$HOME/.config/dotfiles"

# One-time migration from the pre-rename ~/.config/dotfiles/brewfiles list.
bundles_legacy="$HOME/.config/dotfiles/brewfiles"
if [ ! -f "$bundles_sel" ] && [ -f "$bundles_legacy" ]; then
  cp "$bundles_legacy" "$bundles_sel"
  ui_detail "migrated selection from legacy ~/.config/dotfiles/brewfiles"
fi

if [ "$keep_bundles" -eq 1 ]; then
  # Skip the picker and leave the saved selection untouched. A missing file
  # parses to nothing downstream, i.e. baseline only — so no write is needed.
  if [ -f "$bundles_sel" ]; then
    ui_detail "keeping saved selection (--keep-bundles) — ~/.config/dotfiles/bundles"
  else
    ui_detail "--keep-bundles: no saved selection — baseline only"
  fi
elif [ "$bundles_from_flags" -eq 1 ]; then
  write_bundles "$bundles_sel" ${avail[@]+"${avail[@]}"} -- ${requested_bundles[@]+"${requested_bundles[@]}"}
  if [ "${#requested_bundles[@]}" -eq 0 ]; then
    ui_detail "bundles from flags: baseline only (--no-bundles) — saved to ~/.config/dotfiles/bundles"
  else
    ui_detail "bundles from flags: ${requested_bundles[*]} — saved to ~/.config/dotfiles/bundles"
  fi
elif [ "${#avail[@]}" -eq 0 ]; then
  ui_detail "no bundles found in Brewfile.d/*.brewfile — baseline only"
  write_bundles "$bundles_sel" --
elif [ -t 0 ] && command -v fzf >/dev/null 2>&1; then
  ui_active "select bundles  ·  TAB toggles · ENTER confirms · ESC cancels"
  # Pre-seed the picker with the current selection (if any) so a re-run shows
  # today's choices already toggled, ready to amend. fzf_preselect_bind maps the
  # saved names to their 1-based menu positions and emits a `load:` select bind.
  current=()
  if [ -f "$bundles_sel" ]; then
    while IFS= read -r _b; do
      current=(${current[@]+"${current[@]}"} "$_b")
    done < <(parse_bundles "$bundles_sel")
  fi
  # The pre-seed positions are 1-based over the SAME "$avail" order the printf
  # below feeds fzf — keep these two expansions identically ordered or the binds
  # would pre-select the wrong rows.
  preseed="$(fzf_preselect_bind ${avail[@]+"${avail[@]}"} -- ${current[@]+"${current[@]}"})"
  fzf_seed=()
  [ -n "$preseed" ] && fzf_seed=(--bind "$preseed")
  # ESC/ctrl-c/error all exit non-zero; `|| fzf_rc=$?` keeps `set -e` from
  # aborting, and any non-zero is treated as a cancel below (leaves the existing
  # selection untouched — the safe default). --preview cats the bundle so you
  # see its casks/brews before opting in.
  fzf_rc=0
  picked="$(
    printf '%s\n' ${avail[@]+"${avail[@]}"} |
      fzf --multi --height=40% --reverse --border \
        --prompt='bundles> ' \
        --header='opt-in bundles · ENTER confirms · ESC cancels (--no-bundles to clear)' \
        --preview="cat '$bundles_dir'/{}.brewfile" \
        --preview-window=right,60% \
        ${fzf_seed[@]+"${fzf_seed[@]}"}
  )" || fzf_rc=$?
  # A cancel (non-zero) leaves an existing selection untouched; on a fresh machine
  # with nothing saved yet it falls through to a baseline-only file so the install
  # loop below has a well-defined file to read. ENTER (rc 0) always rewrites.
  if [ "$fzf_rc" -ne 0 ] && [ -f "$bundles_sel" ]; then
    ui_detail "selection unchanged"
  else
    # shellcheck disable=SC2046  # intentional split of the newline-separated picks
    write_bundles "$bundles_sel" ${avail[@]+"${avail[@]}"} -- $(printf '%s' "$picked")
    ui_detail "saved selection to ~/.config/dotfiles/bundles"
  fi
elif [ -f "$bundles_sel" ]; then
  ui_detail "non-interactive — using existing ~/.config/dotfiles/bundles"
else
  ui_detail "non-interactive / no fzf — baseline only; pass --bundle NAME or edit ~/.config/dotfiles/bundles to opt in"
  write_bundles "$bundles_sel" ${avail[@]+"${avail[@]}"} --
fi

# Install each selected bundle. parse_bundles yields the chosen names (blanks and
# comments already stripped); same brew bundle call as the baseline, only the file
# path convention differs (Brewfile.d/<name>.brewfile).
installed_bundles=()
while IFS= read -r bundle; do
  bundle_file="$bundles_dir/$bundle.brewfile"
  if [ -f "$bundle_file" ]; then
    ui_active "installing opt-in bundle: $bundle"
    # Non-fatal (as with the baseline above): the summary's brew bundle check
    # surfaces anything that didn't land.
    _brew_bundle "$bundle_file" ||
      ui_warn "opt-in bundle '$bundle' had install failures (see output above) — the summary lists what's missing"
    installed_bundles=(${installed_bundles[@]+"${installed_bundles[@]}"} "$bundle")
  else
    ui_warn "skipping opt-in bundle '$bundle' (no $bundle_file)"
  fi
done < <(parse_bundles "$bundles_sel")

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
  if _brew_bundle "$brew_local"; then
    ui_ok "machine-private additions installed"
  else
    ui_warn "some Brewfile.local packages failed to install (see output above) — the summary lists what's missing"
  fi
fi

# --- 2. Privileged setup — fish shell, firewall, finalize Touch ID ----------
# Acquire sudo ONCE here, for this whole contiguous block. brew bundle just wiped
# any earlier timestamp, so this is THE single authentication of the run — a
# fingerprint tap on a re-run. The Touch-ID finalize, /etc/shells + chsh, and the
# firewall below all run off this one ticket (no brew between them to invalidate
# it); it's dropped (sudo -k) at the end, before the fisher/Claude curl|bash
# installers, so no third-party bootstrap runs with a warm ticket.
#
# Acquiring sudo here (after the bundle, by design — see the sudo notes up top)
# means it can't fail fast before the bundle, so guard it: if the auth is declined
# or fails, WARN and skip ONLY these privileged steps. The rest of the run (stow,
# the dotfiles, every non-root step below) still completes — losing root must not
# cost the user their symlinks — and the closing summary flags whatever's missing.
ui_step "Privileged setup (fish shell, firewall)"
if ! sudo -v; then
  ui_warn "couldn't authenticate for sudo — skipping privileged setup (Touch ID for sudo, fish as the default shell, firewall); re-run install.sh as an administrator to finish these"
else
  # Finalize Touch ID for sudo: now that brew bundle has installed pam_reattach, the
  # sudo_local file gains the tmux/screen line (pam_tid alone was written before the
  # bundle on a fresh machine). Idempotent — rewrites only if the contents differ.
  enable_touch_id_sudo

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
  # socketfilterfw is the least version-stable call here: on recent macOS
  # --setglobalstate can print a deprecation and no-op while still exiting 0. So
  # don't trust the exit code (and don't let it abort the bootstrap) — apply, then
  # verify the actual state and warn if it didn't take.
  sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on >/dev/null 2>&1 || true
  sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on >/dev/null 2>&1 || true
  if sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null | grep -qi enabled; then
    ui_ok "application firewall enabled"
  else
    ui_warn "could not confirm the firewall is on (macOS may have changed socketfilterfw); enable it in System Settings → Network → Firewall"
  fi

  # Done with root. Drop the ticket so nothing downstream (the fisher/Claude
  # curl|bash installers included) runs with a warm sudo timestamp.
  sudo -k
  ui_ok "privileged setup complete"
fi

# --- 3. Symlink dotfiles into $HOME -----------------------------------------
# Stow refuses to overwrite existing real files. Clear known managed files that
# tools may generate as real files on first run so stow can replace them with
# symlinks. Only real files are touched (never existing symlinks), so this stays
# idempotent; stow recreates each as a symlink below.
#
# A real file byte-identical to the repo's version is just removed — the symlink
# will point at the same content, so nothing is lost. One that DIFFERS is moved to
# <file>.pre-stow.bak instead of being destroyed: it may hold edits you (or a tool
# like VS Code Settings Sync) made and haven't merged into the repo yet. Better to
# preserve them next to the file and warn than to silently delete divergent config.
ui_step "dotfiles symlinks (stow)"
managed_files=(
  "$HOME/Library/Application Support/Code/User/settings.json" # VS Code / Settings Sync
  "$HOME/.config/atuin/config.toml"                           # atuin writes a default on first run
  "$HOME/.config/topgrade.toml"                               # topgrade --edit-config seeds a default
)
for f in "${managed_files[@]}"; do
  [ -f "$f" ] && [ ! -L "$f" ] || continue
  # The stow source mirrors $HOME under home/, so strip $HOME to find the repo copy.
  repo_src="$DOTFILES/home/${f#"$HOME"/}"
  # If the repo doesn't actually ship this path, stow won't symlink it — so leave
  # the user's real file untouched rather than moving it aside to no purpose. Guards
  # a future managed_files entry that has no home/ counterpart.
  if [ ! -e "$repo_src" ]; then
    ui_warn "no repo copy for $f (skipping; not a stow-managed path)"
    continue
  fi
  if cmp -s "$f" "$repo_src"; then
    ui_active "removing existing real file so stow can symlink it: $f"
    # -f so a write-protected managed file (e.g. a read-only atuin/VS Code config)
    # can't stall the install on an interactive "remove write-protected file?" prompt
    # mid-run. We already know it's a real file identical to the repo copy — nothing
    # to preserve. Mirrors the rm -f in gitconfig_migrate.sh.
    rm -f "$f"
  else
    # Don't clobber a backup from an earlier run — number it so each divergent
    # version is preserved rather than overwriting the last.
    backup="$f.pre-stow.bak"
    n=1
    while [ -e "$backup" ]; do
      backup="$f.pre-stow.bak.$n"
      n=$((n + 1))
    done
    ui_warn "backing up modified $f -> $backup (differs from the repo version)"
    mv "$f" "$backup"
  fi
done

# Migrate the git template hooks dir to the notify-on-clone design. Earlier this
# repo (like a plain `prek init-template-dir`) wrote a prek shim for EVERY hook type
# into ~/.config/git/template/hooks, which makes a fresh clone auto-run that repo's
# hooks. The current design instead ships a single tracked post-checkout (notify-on-
# clone) stowed here. Remove only the prek-GENERATED shims — they're regenerable
# artifacts (matched by prek's own generator marker), not content you authored — so
# stow can place the notify hook and clones stop silently auto-running hooks.
# A HAND-WRITTEN hook at this path is NOT a prek shim, so it's left untouched and
# surfaces as a loud stow conflict below for you to resolve — never clobbered.
# Re-enable auto-install any time: git config --file ~/.gitconfig_local dotfiles.autoInstallHooks true
tmpl_hooks="$HOME/.config/git/template/hooks"
if [ -d "$tmpl_hooks" ]; then
  removed_shims=""
  for hook in "$tmpl_hooks"/*; do
    [ -e "$hook" ] || continue
    [ -L "$hook" ] && continue
    if grep -qs 'File generated by prek' "$hook"; then
      rm -f "$hook"
      removed_shims="$removed_shims $(basename "$hook")"
    fi
  done
  if [ -n "$removed_shims" ]; then
    ui_active "migrated git template to notify-on-clone (removed prek shims:$removed_shims)"
  fi
fi

# A pre-existing real ~/.gitconfig (manual git setup, or a machine adopting this
# repo) would make the stow preflight below abort. Rather than fail or stomp it,
# back it up and fold its contents into ~/.gitconfig_local — the overlay the
# baseline Include-s LAST, so the user's settings survive and override ours. This
# is a one-time migration: afterwards ~/.gitconfig is our symlink and it's a no-op.
# shellcheck source=scripts/gitconfig_migrate.sh
. "$DOTFILES/scripts/gitconfig_migrate.sh"
# `if ! var="$(...)"` so a non-zero return actually aborts — a bare assignment from
# a command substitution would swallow the helper's exit status and march on.
if ! gitconfig_action="$(gitconfig_migrate "$HOME/.gitconfig" "$HOME/.gitconfig_local" "$DOTFILES/home/.gitconfig")"; then
  ui_err "couldn't safely adopt your existing ~/.gitconfig (see the error above)."
  ui_detail "Your config was left in place or backed up to ~/.gitconfig.pre-stow.bak — resolve it, then re-run install.sh."
  exit 1
fi
if [ -n "$gitconfig_action" ]; then
  case "$gitconfig_action" in
  backed\ up*) ui_warn "$gitconfig_action" ;;
  *) ui_active "$gitconfig_action" ;;
  esac
fi

# Preflight: stow aborts mid-run on the FIRST conflicting file, so do a dry run
# (-n) first to surface ALL conflicts up front. The dry run plans without touching
# the filesystem and applies stow's own ignore rules (.stow-local-ignore: .DS_Store,
# the control file, README/LICENSE, etc.), so it never false-positives on files
# stow wouldn't link anyway. This repo expects to own its paths in a clean $HOME;
# the managed_files above are the known auto-generated exceptions, already cleared.
#
# --no-folding is essential: without it, stow "tree-folds" a target directory that doesn't
# yet exist into a SINGLE symlink (e.g. on a fresh machine ~/.claude -> repo/home/.claude).
# That breaks two things this repo relies on: per-file symlinks (so ~/.claude/CLAUDE.md is a
# real symlink, not a file reached through a folded dir), and — worse — it would route a
# GENERATED real file like ~/.claude/settings.json INTO the repo through the folded dir.
# --no-folding makes stow always create real directories and link files individually, so the
# result is identical whether or not the target dir already existed.
ui_active "checking for conflicts (dry run)"
if ! stow_plan="$(stow --no-folding -n -v --dir="$DOTFILES" --target="$HOME" home 2>&1)"; then
  ui_err "these files already exist in \$HOME and would be replaced by this repo's versions, so aborting."
  ui_detail "Back them up and/or merge their contents into the repo, then re-run install.sh:"
  printf '%s\n' "$stow_plan" | grep -E 'cannot stow' >&2 || printf '%s\n' "$stow_plan" >&2
  exit 1
fi

stow --no-folding --dir="$DOTFILES" --target="$HOME" home
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
    cat >"$1"
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
# Machine-local git config (untracked). Included LAST by ~/.gitconfig, so anything
# here overrides the tracked baseline.
#
# Set your git identity here — it is intentionally NOT in the public repo. Without
# it `git commit` fails with "Please tell me who you are":
#   [user]
#       name = Your Name
#       email = you@example.com
#       signingkey = ssh-ed25519 AAAA...   # your SSH signing key (if you sign)
#
# Good home for a per-directory work identity, too:
#   [includeIf "gitdir:~/work/"]
#       path = ~/.gitconfig.work   # work email, signing key, etc. — untracked
#
# Commit signing: the tracked ~/.gitconfig signs commits with 1Password's
# op-ssh-sign. On a machine WITHOUT 1Password, install.sh disables signing here
# automatically (adds commit.gpgsign=false below) so commits still work — the
# [include] of this file sits after commit.gpgsign=true in the tracked config, so
# this wins. To sign with a different tool instead, set your own program + key:
#   [gpg "ssh"]
#       program = /opt/homebrew/bin/ssh-keygen   # or a work signer
#   [user]
#       signingkey = ~/.ssh/id_ed25519.pub
#   [commit]
#       gpgsign = true
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

# Claude Code imports this from the tracked ~/.claude/CLAUDE.md
# (@~/.config/dotfiles/CLAUDE.local.md). Seeded so the import target always exists.
seed_if_absent "$HOME/.config/dotfiles/CLAUDE.local.md" <<'EOF'
<!-- Machine-local Claude Code instructions (untracked). Imported by the tracked
     ~/.claude/CLAUDE.md via `@~/.config/dotfiles/CLAUDE.local.md`. Put work-vs-personal
     guidance here that shouldn't live in the public repo. Markdown, same format as
     CLAUDE.md. Example:

       ## Work
       - Internal package registry: https://nexus.corp.example/...
       - Never push to the public mirror from a work checkout.
-->
EOF

# Claude Code MCP overlay: install.sh (step 12) deep-merges this over the tracked
# claude_mcp.json (this file wins), so a machine can add or override MCP servers.
# Strict JSON only — it's parsed by jq, so no comments. Seeded as an empty object.
# Example contents:
#   { "my-server": { "type": "stdio", "command": "/path/to/server", "args": [] } }
seed_if_absent "$HOME/.config/dotfiles/claude_mcp.local.json" <<'EOF'
{}
EOF

# Claude Code settings overlay: install.sh (step 13) deep-merges this over the
# tracked claude_settings.json baseline and writes the result as a REAL file to
# ~/.claude/settings.json (which is NOT stowed). The overlay wins per scalar key;
# arrays (permissions.allow/deny, hooks.<event>) UNION, so a machine adds to the
# baseline rather than replacing it. Whatever the live settings.json holds beyond
# the baseline is folded back in here on every run, so machine-local prefs accrue
# instead of being clobbered. Strict JSON only — parsed by jq, no comments.
# Examples:
#   { "theme": "light", "permissions": { "allow": ["Bash(kubectl *)"] } }
#   machine-local hook (script lives in ~/.config/dotfiles/claude-hooks.local/):
#   { "hooks": { "Stop": [ { "hooks": [ { "type": "command",
#       "command": "$HOME/.config/dotfiles/claude-hooks.local/notify.sh" } ] } ] } }
seed_if_absent "$HOME/.config/dotfiles/claude_settings.local.json" <<'EOF'
{}
EOF

# Home for machine-local Claude Code hook scripts referenced from the settings
# overlay above. Untracked + outside the repo, so a work-only hook never lands in
# the public repo. (Shared user-level hooks instead go under home/.claude/hooks/.)
seed_if_absent "$HOME/.config/dotfiles/claude-hooks.local/README.md" <<'EOF'
# Machine-local Claude Code hook scripts (untracked)

Put per-machine hook scripts here and reference them by absolute path from the
`hooks` block of `~/.config/dotfiles/claude_settings.local.json`. install.sh
merges that overlay's `hooks` into the generated `~/.claude/settings.json`
alongside any shared hooks from the tracked `claude_settings.json` baseline.

Keep work-vs-personal hooks here so they never reach the public repo. Shared
hooks that should apply on every machine belong in the baseline (and their
scripts under `home/.claude/hooks/`).
EOF

# macos.sh sources this just before it restarts Finder/Dock, so per-machine
# `defaults` writes are applied in the same pass. Use `dwrite ...` (defined in
# macos.sh) for the same MDM-safe "warn and continue" behavior on managed boxes.
seed_if_absent "$HOME/.config/dotfiles/macos.local.sh" <<'EOF'
# Machine-local macOS defaults (untracked). Sourced by macos.sh before it restarts
# Finder/Dock. Use the same `defaults write` calls as macos.sh; prefer the `dwrite`
# wrapper so a write blocked by an MDM profile warns and keeps going instead of
# aborting. Example:
#   dwrite com.apple.dock tilesize -int 64
EOF

# Commit signing degrades gracefully on a machine without 1Password. The tracked
# ~/.gitconfig signs commits via 1Password's op-ssh-sign; if that binary is absent
# and you haven't set commit.gpgsign yourself in the overlay, disable signing here so
# commits don't fail. The [include] of ~/.gitconfig_local sits AFTER commit.gpgsign=true
# in the tracked config, so this override wins. Personal machines (1Password present)
# are untouched and keep signing.
op_ssh_sign="/Applications/1Password.app/Contents/MacOS/op-ssh-sign"
if [ ! -x "$op_ssh_sign" ]; then
  if [ -z "$(git config --file "$HOME/.gitconfig_local" --get commit.gpgsign 2>/dev/null || true)" ]; then
    git config --file "$HOME/.gitconfig_local" commit.gpgsign false
    ui_warn "1Password not found — disabled commit signing in ~/.gitconfig_local (set commit.gpgsign yourself to re-enable)."
  else
    ui_detail "1Password not found, but commit.gpgsign is already set in ~/.gitconfig_local — leaving it as-is"
  fi
fi

ui_ok "overlay files ready"

# --- 5. Fish plugins (fisher) -----------------------------------------------
# fisher update installs everything listed in the now-symlinked fish_plugins.
ui_step "Fish plugins (fisher)"
_install_fisher() {
  fish -c '
    if not functions -q fisher
      curl -sL https://raw.githubusercontent.com/jorgebucaran/fisher/main/functions/fisher.fish | source
      fisher install jorgebucaran/fisher
    end
    fisher update
  '
}
if retry "fisher (fish plugins)" 3 _install_fisher; then
  ui_ok "fish plugins installed"
else
  ui_warn "fisher bootstrap failed (network?) — fish plugins not installed; re-run install.sh to retry"
fi

# --- 6. tmux plugins (TPM) --------------------------------------------------
# Clone TPM if missing, then install the plugins declared in the stowed tmux.conf.
ui_step "tmux plugins (TPM)"
TPM_DIR="$HOME/.config/tmux/plugins/tpm"
# rm -rf before each clone attempt so a retry after a partial clone can't fail on a
# non-empty target directory.
_clone_tpm() { rm -rf "$TPM_DIR" && git clone --depth 1 https://github.com/tmux-plugins/tpm "$TPM_DIR"; }
# Key the (re)clone off the actual entrypoint, not just the directory: a previous run could
# have left a partial/corrupt checkout (dir present but bin/install_plugins missing), which a
# bare `-d` test would skip — leaving plugins silently uninstalled. _clone_tpm rm -rf's first.
if [ ! -x "$TPM_DIR/bin/install_plugins" ]; then
  ui_active "installing TPM (tmux plugin manager)"
  retry "TPM clone" 3 _clone_tpm ||
    ui_warn "TPM clone failed (network?) — tmux plugins not installed; re-run install.sh to retry"
fi
if [ -x "$TPM_DIR/bin/install_plugins" ]; then
  "$TPM_DIR/bin/install_plugins" >/dev/null 2>&1 || true
  ui_ok "tmux plugins installed"
fi

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
# set -f (noglob) for the loop: lines are split on IFS intentionally, but a token like
# reuse[charset-normalizer] would otherwise glob-expand against the caller's CWD. Scope it
# with `set +f` rather than a subshell, so a failing tool's ui_warn lands in the global
# WARNINGS summary (a subshell's mutations wouldn't propagate) and we can report OK vs WARN.
set -f
uv_tool_failures=0
while IFS= read -r tool; do
  case "$tool" in '' | \#*) continue ;; esac
  # shellcheck disable=SC2086  # intentional split: line holds tool + --with args
  retry "uv tool install $tool" 3 uv tool install $tool || {
    ui_warn "uv tool install failed for: $tool (re-run install.sh to retry)"
    uv_tool_failures=$((uv_tool_failures + 1))
  }
done <"$DOTFILES/uv_tools.txt"
set +f
if [ "$uv_tool_failures" -eq 0 ]; then
  ui_ok "uv tools installed"
else
  ui_warn "$uv_tool_failures uv tool(s) failed to install (see above) — re-run install.sh to retry"
fi

# uv drops tool shims into ~/.local/bin. Put it on PATH now so the later
# `command -v` checks (prek, claude) find them even when uv was already present
# (so the fresh-uv export near the top never ran) and the caller's PATH lacks it.
export PATH="$HOME/.local/bin:$PATH"

# Playwright needs a browser binary beyond the Python package. `--only-shell chromium`
# fetches just the Chromium headless shell (smaller than the full browser): the
# docs-site tests run headless with no channel, which uses the shell. The `chromium`
# arg is required — a bare `--only-shell` means "all browsers" and also pulls Firefox
# + WebKit. Install via the repo's *locked* dev dependency — the exact version
# `uv run pytest` uses (and what CI installs) — not the floating global `playwright`
# tool, whose version can drift and point pytest at a revision that was never
# downloaded. The build lands in a shared OS cache, so the global tool reuses it when
# versions match. Idempotent (skips if present); non-fatal so a slow/failed download
# never aborts the bootstrap.
ui_active "installing Playwright headless shell (browser for the docs-site tests)"
uv run --project "$DOTFILES" playwright install --only-shell chromium ||
  ui_warn "Playwright headless shell install failed; re-run install.sh to retry."

# --- 10. Git clone hook (notify-on-clone; opt-in auto-install) ---------------
# The git template at ~/.config/git/template (stowed in step 3, wired up by
# init.templateDir in the tracked ~/.gitconfig) drops a post-checkout hook into
# every fresh clone. By DEFAULT it only NOTIFIES when the cloned repo defines
# pre-commit hooks — it runs nothing from the clone, so the default carries no
# trust-on-clone risk. To auto-install those hooks on clone instead, opt in
# per-machine from the untracked overlay:
#
#   git config --file ~/.gitconfig_local dotfiles.autoInstallHooks true
#
# Nothing to install here — the hook is stowed and self-contained (it calls
# `prek install` itself, only when you've opted in). Just report the current mode
# so it's discoverable.
ui_step "Git clone hook (notify-on-clone)"
if [ "$(git config --bool --get dotfiles.autoInstallHooks 2>/dev/null || echo false)" = "true" ]; then
  ui_ok "fresh clones will auto-install pre-commit hooks (dotfiles.autoInstallHooks=true)"
else
  ui_detail "fresh clones will notify when a repo defines pre-commit hooks; set dotfiles.autoInstallHooks=true to auto-install"
fi

# --- 11. Claude Code CLI (native installer; self-updates) -------------------
# Installed via the native installer (NOT a brew cask) on purpose: we want
# Claude Code's background auto-updates for this fast-moving tool. Installs to
# ~/.local/bin (already on PATH, same as the uv tools above). Only install when
# absent — the auto-updater keeps it current afterwards. Runs before the MCP
# step below so a first-run bootstrap can register servers without a re-run.
if ! command -v claude >/dev/null 2>&1; then
  ui_step "Installing Claude Code CLI (native installer)"
  _install_claude() { curl -fsSL https://claude.ai/install.sh | bash; }
  if retry "Claude Code install" 3 _install_claude; then
    export PATH="$HOME/.local/bin:$PATH"
    ui_ok "Claude Code CLI installed"
  else
    ui_warn "Claude Code install failed (network?) — skipping; re-run install.sh to retry"
  fi
fi

# --- 12. Claude Code user-scope MCP servers ---------------------------------
# claude registers user-scope MCP servers into ~/.claude.json, which is
# machine-local state (project history, OAuth) and not stowable. So the
# declarative source of truth lives in claude_mcp.json and is replayed here,
# idempotently (remove-then-add).
#
# Layering: the tracked claude_mcp.json baseline is deep-merged with an optional
# untracked overlay ~/.config/dotfiles/claude_mcp.local.json (overlay wins; jq '*'
# merges nested objects), so a machine can add or override servers without touching
# the public repo.
#
# Secret resolution runs in order, so the github server works WITH or WITHOUT 1Password:
#   1. op signed in              -> `op inject` resolves {{ op://... }} (personal default).
#   2. else, GitHub PAT in env   -> rewrite the github server's auth header from the
#      first non-empty of $GITHUB_PERSONAL_ACCESS_TOKEN / $GH_TOKEN / $GITHUB_TOKEN.
#   3. else                      -> leave {{ op://... }} unresolved (those servers are
#      skipped below; re-run after `op signin` or after exporting a PAT).
# Either way the token only ever lands in ~/.claude.json (0600), never in the repo.
#
# Skip paths that keep first-run / no-1Password bootstrap safe:
#   - claude CLI absent              -> skip the whole step (safety net if step 11 failed).
#   - server with unresolved op://   -> skip that server (left untouched, re-runnable).
#   - stdio server whose absolute `command` binary is missing -> skip it (covers the
#     1password MCP server on a machine without the 1Password app installed).
if command -v claude >/dev/null 2>&1; then
  ui_step "Claude Code MCP servers (claude_mcp.json)"

  # Baseline ⊕ machine-local overlay (overlay wins on key conflicts). Validate the
  # overlay with `jq empty` BEFORE merging: a malformed overlay would make the merge
  # `jq` produce no output, leaving merged_mcp empty and silently dropping EVERY
  # server (baseline included). Instead, warn and fall back to the baseline only, so
  # one typo in the untracked overlay can't wipe out the tracked servers.
  mcp_local="$HOME/.config/dotfiles/claude_mcp.local.json"
  if [ -f "$mcp_local" ] && jq empty "$mcp_local" >/dev/null 2>&1; then
    merged_mcp="$(jq -s '.[0] * .[1]' "$DOTFILES/claude_mcp.json" "$mcp_local")"
  else
    if [ -f "$mcp_local" ]; then
      ui_warn "ignoring $mcp_local (not valid JSON) — registering baseline servers only; fix it and re-run"
    fi
    merged_mcp="$(cat "$DOTFILES/claude_mcp.json")"
  fi

  # Resolve secrets: 1Password first, else a GitHub PAT from the environment.
  if command -v op >/dev/null 2>&1 && op whoami >/dev/null 2>&1; then
    resolved_mcp="$(printf '%s' "$merged_mcp" | op inject)"
  else
    resolved_mcp="$merged_mcp"
    gh_pat="${GITHUB_PERSONAL_ACCESS_TOKEN:-${GH_TOKEN:-${GITHUB_TOKEN:-}}}"
    if [ -n "$gh_pat" ]; then
      # Only rewrite a github auth header that STILL holds an op:// placeholder — never
      # fabricate a server, and don't clobber a real token an overlay already supplied.
      resolved_mcp="$(printf '%s' "$resolved_mcp" | jq --arg t "Bearer $gh_pat" '
        if (.github.headers.Authorization? // "" | test("op://"))
        then .github.headers.Authorization = $t else . end')"
      ui_detail "using a GitHub PAT from the environment for the github MCP server"
    fi
    if printf '%s' "$resolved_mcp" | grep -q 'op://'; then
      ui_warn "1Password not signed in — skipping secret-backed servers; re-run after 'op signin' or export a GitHub PAT."
    fi
  fi

  while IFS=$'\t' read -r name json; do
    if printf '%s' "$json" | grep -q 'op://'; then
      ui_warn "skipping '$name' (unresolved 1Password reference)"
      continue
    fi
    # Skip a stdio server whose absolute command path isn't executable here (e.g. the
    # 1password MCP server when the 1Password app isn't installed). http servers and
    # bare-command (PATH-resolved) servers have no leading '/', so they pass through.
    cmd="$(printf '%s' "$json" | jq -r '.command // empty')"
    case "$cmd" in
    /*) if [ ! -x "$cmd" ]; then
      ui_warn "skipping '$name' (command not found: $cmd)"
      continue
    fi ;;
    esac
    claude mcp remove "$name" --scope user >/dev/null 2>&1 || true
    claude mcp add-json "$name" "$json" --scope user >/dev/null ||
      ui_warn "failed to register MCP server '$name' (re-run install.sh to retry)"
  done < <(printf '%s' "$resolved_mcp" | jq -r 'to_entries[] | "\(.key)\t\(.value | tojson)"')
  ui_ok "MCP servers registered"
else
  ui_warn "skipping Claude Code MCP setup (claude CLI not installed — step 11's install likely failed; re-run install.sh)"
fi

# --- 13. Claude Code user settings (baseline + machine-local overlay) --------
# ~/.claude/settings.json is a GENERATED REAL file — NOT stowed. The tracked
# claude_settings.json baseline is deep-merged with an untracked overlay
# (~/.config/dotfiles/claude_settings.local.json) and written out fresh each run.
# Merge rule (scripts/claude_settings_merge.sh): objects recurse, ARRAYS UNION
# (permissions.allow/deny and hooks.<event> accumulate instead of one clobbering
# the other — matching how Claude Code unions permissions across scopes), scalars
# overlay-wins.
#
# Every run also re-captures machine-local drift: whatever the live settings.json
# holds beyond the baseline (Claude Code's /config and /plugin write through it,
# or you edited it) is diffed out and folded into the overlay, so prefs accrue
# rather than being reset. That's the curation workflow: to make a baseline key
# machine-local, delete it from claude_settings.json — the next run finds it in
# the live file and moves it into this machine's overlay automatically.
#
# Migration: a machine from a previous (stow) install has ~/.claude/settings.json
# as a symlink into the repo. After this change the symlink's target is gone, so
# it's a dangling link — either way it's replaced with a real file here. Lossless
# on the primary machine because claude_settings.json starts as a verbatim copy of
# the old file, so baseline + (empty) overlay reproduce the prior contents.
#
# Safety: validate that every JSON input is an OBJECT (not merely valid JSON)
# before trusting it. `jq empty` is not enough — it passes empty/whitespace input
# (which then crashes `--argjson`) and valid-but-non-object JSON (an array/scalar
# would sail through and make the merge discard the entire baseline). A bad
# baseline skips the step (never wipe settings); a bad live file or overlay
# degrades to {} / the live delta with a warning. Both files are written via a
# temp file + atomic mv, so a failed write can never leave you with no settings.
if command -v jq >/dev/null 2>&1; then
  ui_step "Claude Code user settings (claude_settings.json)"
  # shellcheck source=scripts/claude_settings_merge.sh
  . "$DOTFILES/scripts/claude_settings_merge.sh"
  claude_baseline="$DOTFILES/claude_settings.json"
  claude_overlay="$HOME/.config/dotfiles/claude_settings.local.json"
  claude_settings="$HOME/.claude/settings.json"

  if ! jq -e 'type == "object"' "$claude_baseline" >/dev/null 2>&1; then
    ui_warn "claude_settings.json is not a JSON object — skipping settings generation (fix it and re-run)"
  else
    baseline_json="$(cat "$claude_baseline")"

    # CURRENT: the live settings. Missing/empty/corrupt/non-object -> treat as {}
    # so it can't poison the overlay or discard the baseline; the merge restores
    # the baseline. (A dangling migration symlink reads as absent here.)
    current_json='{}'
    if [ -e "$claude_settings" ]; then
      current_raw="$(cat "$claude_settings" 2>/dev/null || true)"
      if claude_settings_is_object "$current_raw"; then
        current_json="$current_raw"
      else
        ui_warn "existing ~/.claude/settings.json isn't a JSON object — ignoring it (regenerating from baseline + overlay)"
      fi
    fi

    # Compute BOTH outputs before writing either, so a mid-step failure can't
    # leave the overlay and the generated file out of sync. DELTA = keys/values in
    # CURRENT not already implied by the baseline; fold it into the overlay
    # (accrues machine-local prefs across runs). A non-object overlay must not
    # silently wipe accruals — warn and rebuild from the live delta only.
    delta_json="$(claude_settings_diff "$baseline_json" "$current_json")"
    overlay_json="$delta_json"
    if [ -e "$claude_overlay" ]; then
      if claude_settings_is_object "$(cat "$claude_overlay" 2>/dev/null || true)"; then
        overlay_json="$(claude_settings_merge "$(cat "$claude_overlay")" "$delta_json")"
      else
        ui_warn "ignoring $claude_overlay (not a JSON object) — rebuilding it from the live delta; fix it and re-run"
      fi
    fi
    merged_json="$(claude_settings_merge "$baseline_json" "$overlay_json")"

    # Write both via temp file + atomic mv (mv replaces a leftover symlink too, so
    # there is never a window with no settings file).
    mkdir -p "$(dirname "$claude_overlay")" "$(dirname "$claude_settings")"
    overlay_tmp="$claude_overlay.tmp.$$"
    printf '%s\n' "$overlay_json" >"$overlay_tmp" && mv -f "$overlay_tmp" "$claude_overlay"
    if [ -d "$claude_settings" ]; then
      ui_warn "refusing to write: ~/.claude/settings.json is a directory (remove it and re-run)"
    else
      settings_tmp="$claude_settings.tmp.$$"
      printf '%s\n' "$merged_json" >"$settings_tmp" && mv -f "$settings_tmp" "$claude_settings"
      ui_ok "Claude settings written (baseline + machine-local overlay)"
    fi
  fi
else
  ui_warn "skipping Claude Code settings (jq not installed — see Brewfile; re-run install.sh)"
fi

# --- 14. Ollama models for local AI -----------------------------------------
# Two consumers, two models:
#  • GitLens (stowed VS Code settings: gitlens.ai.model = "ollama:qwen2.5-coder:7b")
#    runs commit-message generation / explain-commit offline — no cloud key, no
#    Copilot. This is the baseline model, pulled on every capable machine.
#  • Claude bulk-offload (see ~/.config/dotfiles/CLAUDE.local.md) prefers the faster,
#    higher-quality MLX model qwen3.5:35b-a3b-coding-nvfp4. It runs on Ollama's MLX
#    engine, which needs Apple Silicon + >32GB unified memory, so it is GATED — other
#    machines are unaffected and keep just the 7b (also the non-MLX fallback).
#
# ollama-app (Brewfile cask) ships both the `ollama` CLI and a menu-bar app serving
# the API on :11434 (auto-starts on login). We make sure the server is up, then pull.
# Idempotent: re-launching a running app is a no-op and a pull is skipped when the
# model already exists; a failed pull is non-fatal.
#
# ⚠️ qwen3.5-a3b is a REASONING model: programmatic callers must send "think": false,
# or the token budget is spent on hidden thinking and the response comes back empty.
# That is why GitLens — which can't set think:false — stays on the 7b, not this model.
# OLLAMA_MODEL (GitLens + universal fallback) + OLLAMA_MLX_MODEL (gated, Claude offload)
# live in one shared fragment so uninstall.sh offers to remove exactly what we provision.
# shellcheck source=scripts/ollama_models.sh disable=SC1091
. "$DOTFILES/scripts/ollama_models.sh"

# ollama_pull_model MODEL SIZE INSTALLED — idempotent (skip if MODEL is already a line of
# INSTALLED, the model inventory captured once by the caller) and non-fatal (a failed pull
# degrades to a warning + re-run hint, never aborts the install).
ollama_pull_model() {
  local model="$1" size="$2" installed="$3"
  if printf '%s\n' "$installed" | grep -qx "$model"; then
    ui_ok "Ollama model $model already present"
  else
    ui_active "pulling Ollama model $model ($size, one-time)"
    if ollama pull "$model"; then
      ui_ok "Ollama model $model pulled"
    else
      ui_warn "Ollama pull failed for $model (network?); re-run install.sh to retry."
    fi
  fi
}

if command -v ollama >/dev/null 2>&1; then
  ui_step "Ollama models for local AI ($OLLAMA_MODEL + gated MLX)"
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
        http://localhost:11434/api/tags >/dev/null 2>&1 ||
        ui_warn "Ollama server didn't come up; start it and re-run to pull the model."
    fi
  fi
  # Capture the model inventory once (one daemon round-trip) and reuse it for both checks.
  installed_models="$(ollama list 2>/dev/null | awk 'NR>1 {print $1}')"
  # Baseline model — every capable machine.
  ollama_pull_model "$OLLAMA_MODEL" "~4.7GB" "$installed_models"
  # Gated MLX model — Apple Silicon + >32GB unified memory (32 GiB = 34359738368
  # bytes; require strictly more so exactly-32GB machines fall back to just the 7b).
  if [ "$(uname -m)" = "arm64" ] &&
    [ "$(sysctl -n hw.memsize 2>/dev/null || echo 0)" -gt 34359738368 ]; then
    ollama_pull_model "$OLLAMA_MLX_MODEL" "~21GB" "$installed_models"
  else
    ui_detail "skipping MLX model $OLLAMA_MLX_MODEL (needs Apple Silicon + >32GB RAM)"
  fi
else
  ui_warn "skipping Ollama setup (ollama not installed; see Brewfile 'ollama-app')"
fi

# --- 15. macOS system defaults ----------------------------------------------
# Curated `defaults write` tweaks. Idempotent; restarts Finder/Dock at the end.
# This is config-as-code: it *asserts* the declared prefs over whatever you've
# set by hand. Comment it out (or edit macos.sh) if you'd rather run it manually.
ui_step "macOS system defaults (macos.sh)"
ui_detail "applies the system preferences declared in macos.sh (overrides manual tweaks)"
# macos.sh runs under its own `set -e` and sources the untracked macos.local.sh; a
# bad line there (or any failure outside the dwrite wrapper) exits non-zero. Don't
# let that abort the whole bootstrap before the Dock step below — warn and carry on,
# matching dwrite's own "warn and continue" stance for managed-Mac write failures.
if bash "$DOTFILES/macos.sh"; then
  ui_ok "macOS defaults applied"
else
  ui_warn "macos.sh exited non-zero — continuing (check ~/.config/dotfiles/macos.local.sh; some defaults may not have applied)"
fi

# --- 16. Dock layout --------------------------------------------------------
# Declarative Dock via dockutil: removes every current Dock item and rebuilds
# from dock.sh's list. That's the config-as-code contract — like every other
# step here, it converges unconditionally (the pinned set is small, so the
# replacement is cheap). Run dock.sh yourself any time to re-apply.
ui_step "Dock layout (dock.sh)"
# Non-fatal (like macos.sh above): the Dock rebuild can fail without a GUI/Dock session
# (e.g. a headless VM), and that must not abort the run right before the verification
# summary. dock.sh is idempotent, so a re-run reapplies it.
if bash "$DOTFILES/dock.sh"; then
  ui_ok "Dock layout applied"
else
  ui_warn "dock.sh exited non-zero — continuing (the Dock may need a GUI session; re-run install.sh)"
fi

# --- 17. Verification & summary ---------------------------------------------
# Deterministic post-install check (scripts/verify_install.sh — also runnable
# standalone any time): re-derive the intended end state and report it, then replay
# every warning collected during the run. Two sections — what's verified, and what
# needs attention (failed checks ∪ run-time warnings) — so a long, noisy install
# (e.g. a transient brew failure) ends in one clear readout you never scroll past.
# Reads only; needs no sudo. Always exits 0 — this summarizes, it doesn't gate.
ui_banner "dotfiles bootstrap complete"

# shellcheck source=scripts/verify_install.sh
. "$DOTFILES/scripts/verify_install.sh"
verified=()
problems=()
while IFS=$'\t' read -r status msg; do
  case "$status" in
  OK) verified=(${verified[@]+"${verified[@]}"} "$msg") ;;
  BAD) problems=(${problems[@]+"${problems[@]}"} "$msg") ;;
  esac
done < <(verify_install "$DOTFILES")

ui_step "Verified"
for line in ${verified[@]+"${verified[@]}"}; do ui_ok "$line"; done

# Needs attention = failed checks + every ui_warn emitted during this run. Failed
# checks are NEW (only found now); the run-time warnings are a replay so you don't
# have to scroll back. De-dup isn't needed: the two sets describe different things.
attention=(${problems[@]+"${problems[@]}"} ${WARNINGS[@]+"${WARNINGS[@]}"})
ui_step "Needs attention"
if [ "${#attention[@]}" -eq 0 ]; then
  ui_ok "nothing — everything checks out"
else
  for line in ${attention[@]+"${attention[@]}"}; do ui_warn "$line"; done
  ui_detail "re-run ~/dotfiles/install.sh to retry, or 'bash ~/dotfiles/scripts/verify_install.sh' to re-check."
fi

printf '\n'
ui_detail "Restart your shell (or run 'exec fish') to pick everything up."
