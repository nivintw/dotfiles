#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# Scoped, idempotent uninstaller — the safe reverse of install.sh.
#
# Design (see issue #36): it reverses only what the installer demonstrably OWNS, it
# never destroys your data, and it never surprises you. Rather than journaling state
# at install time and replaying it, it is INTERACTIVE and present-state-aware: it
# removes the provably-ours things automatically, OFFERS the bigger/created artifacts
# (default no), ASKS about the few lossy system changes, and REPORTS — with exact
# copy-paste commands — everything it deliberately leaves alone. The closing summary
# is the point: you always know what changed and what is left to do by hand.
#
# Tiers:
#   1. auto      — provably ours + reversible: stow -D, MCP registrations, the iTerm2
#                  prefs pointer (only if it still points at this repo).
#   2. offer     — created/enumerable, default NO: the TPM clone (install.sh reuses a
#                  pre-existing one, so we can't prove ownership), uv tools, Ollama models.
#   3. ask       — lossy system changes: login shell, /etc/pam.d/sudo_local (only if
#                  its contents are the ones we wrote).
#   4. report    — never touched, with how-to: Homebrew/uv/Claude CLI, atuin's DB,
#                  brew packages, macos.sh defaults, the Dock, the firewall, /etc/shells,
#                  and all machine-local user data (~/.config/dotfiles/*, *.pre-stow.bak,
#                  the generated ~/.claude/settings.json).
#
# Flags: --dry-run/-n (preview, mutate nothing), --yes/-y (skip the top confirm; Tier-2/3
# prompts still default to the SAFE choice — skip + report), --help/-h.
#
# Best-effort by construction: it runs under `set -uo pipefail` WITHOUT `-e` (set in the
# standalone entrypoint, not at top level, so sourcing for tests doesn't flip the caller's
# shell options) so a single failed reversal degrades to a warning and the rest of the
# uninstall (and the summary) still completes. Re-running is safe — every step self-checks.

# --- presentation (own copy; the repo convention is each top-level script defines
# its own logging — there is no shared lib to source without side effects) ----------
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_RESET=$'\033[0m' C_BOLD=$'\033[1m' C_DIM=$'\033[2m'
  C_BLUE=$'\033[34m' C_GREEN=$'\033[32m' C_YELLOW=$'\033[33m' C_RED=$'\033[31m'
  G_OK=$'✓' G_ACTIVE=$'…' G_WARN=$'⚠' G_ERR=$'✗'
else
  C_RESET='' C_BOLD='' C_DIM='' C_BLUE='' C_GREEN='' C_YELLOW='' C_RED=''
  G_OK='[ok]' G_ACTIVE='[..]' G_WARN='[!!]' G_ERR='[xx]'
fi
ui_step() { printf '\n%s%s==>%s %s\n' "$C_BOLD" "$C_BLUE" "$C_RESET" "$1"; }
ui_ok() { printf '%s%s%s %s\n' "$C_GREEN" "$G_OK" "$C_RESET" "$1"; }
ui_active() { printf '%s%s%s %s\n' "$C_BLUE" "$G_ACTIVE" "$C_RESET" "$1"; }
ui_warn() { printf '%s%s%s %s\n' "$C_YELLOW" "$G_WARN" "$C_RESET" "$1"; }
ui_err() { printf '%s%s%s %s\n' "$C_RED" "$G_ERR" "$C_RESET" "$1" >&2; }
ui_detail() { printf '   %s%s%s\n' "$C_DIM" "$1" "$C_RESET"; }

# --- pure helpers (unit-tested in tests/uninstall.bats) ----------------------------

# un_uv_tool_name LINE — the uv tool NAME from a uv_tools.txt line: the first
# whitespace-delimited token with any [extras] stripped. Empty for blank/comment
# lines. `reuse[charset-normalizer]` -> `reuse`; `ansible --with jc` -> `ansible`.
un_uv_tool_name() {
  local line="$1" first
  case "$line" in '' | \#*) return 0 ;; esac
  first="${line%%[[:space:]]*}" # first token
  printf '%s\n' "${first%%\[*}" # strip [extras]
}

# un_pam_is_ours CONTENT — true iff every non-empty line is one of the two forms
# install.sh writes (a pam_tid `sufficient` line, optionally preceded by a
# pam_reattach `optional` line) AND the pam_tid line is present. Matching by shape
# rather than an exact string keeps it robust to the machine-specific brew prefix in
# the pam_reattach path. This is also Apple's documented Touch-ID-for-sudo content, so a
# user's hand-rolled file can match too — which is why removal is always gated behind an
# explicit prompt (never automatic), and we still reject anything with an unknown line.
un_pam_is_ours() {
  local content="$1" line have_tid=0
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    case "$line" in
    *pam_tid.so)
      printf '%s' "$line" | grep -Eq '^auth[[:space:]]+sufficient[[:space:]]+pam_tid\.so$' || return 1
      have_tid=1
      ;;
    *pam_reattach.so)
      printf '%s' "$line" | grep -Eq '^auth[[:space:]]+optional[[:space:]]+.*/pam_reattach\.so$' || return 1
      ;;
    *) return 1 ;;
    esac
  done <<EOF
$content
EOF
  [ "$have_tid" = 1 ]
}

# un_mcp_names BASELINE [OVERLAY] — the MCP server names (object keys) from the
# baseline config deep-merged with the optional machine-local overlay, mirroring how
# install.sh registers them so we remove exactly the set it added.
un_mcp_names() {
  local base="$1" overlay="${2:-}"
  if [ -n "$overlay" ] && [ -f "$overlay" ] && jq empty "$overlay" >/dev/null 2>&1; then
    jq -s -r '(.[0] * .[1]) | keys[]' "$base" "$overlay"
  else
    jq -r 'keys[]' "$base"
  fi
}

# un_is_yes ANSWER — true for an affirmative prompt reply (y/yes, any case). One place
# for the accept pattern so the proceed gate and the per-item offers can't drift.
un_is_yes() {
  case "$1" in [yY] | [yY][eE][sS]) return 0 ;; *) return 1 ;; esac
}

# --- run-state + summary ledger ----------------------------------------------------
DRY_RUN=0
ASSUME_YES=0
DOTFILES="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REMOVED=()  # things actually reversed
DECLINED=() # offers the user (or non-interactive default) said no to
LEFT=()     # deliberately not touched, with the reason
MANUAL=()   # copy-paste commands to finish by hand
FAILED=()   # reversals attempted that errored — surfaced so the summary can't hide a failure
rec_removed() { REMOVED+=("$1"); }
# In a dry run an offer isn't truly "declined" (it was never asked), so don't log it as one —
# the inline "[dry-run] would ask:" lines already show what would be prompted.
rec_declined() { [ "$DRY_RUN" = 1 ] || DECLINED+=("$1"); }
rec_left() { LEFT+=("$1"); }
rec_manual() { MANUAL+=("$1"); }
rec_failed() { FAILED+=("$1"); }

# proceed_gate — one confirmation before any mutation. --dry-run and --yes pass; a
# non-interactive run without --yes refuses rather than destroying state unattended.
proceed_gate() {
  [ "$DRY_RUN" = 1 ] && return 0
  [ "$ASSUME_YES" = 1 ] && return 0
  if [ ! -t 0 ]; then
    ui_err "refusing to modify your system unattended; re-run with --yes or --dry-run."
    exit 1
  fi
  printf '%sThis removes the dotfiles symlinks and installer-owned setup. Proceed? [y/N]%s ' "$C_BOLD" "$C_RESET"
  local ans
  read -r ans
  un_is_yes "$ans" && return 0
  ui_warn "aborted — nothing changed."
  exit 0
}

# offer QUESTION — a Tier-2/3 prompt that DEFAULTS TO NO. In --dry-run it only
# announces; under --yes or non-interactively it takes the safe path (no). Returns 0
# only on an explicit interactive yes.
offer() {
  local q="$1"
  if [ "$DRY_RUN" = 1 ]; then
    ui_detail "[dry-run] would ask: $q"
    return 1
  fi
  { [ "$ASSUME_YES" = 1 ] || [ ! -t 0 ]; } && return 1
  printf '   %s [y/N] ' "$q"
  local ans
  read -r ans
  un_is_yes "$ans"
}

# do_or_echo DESC CMD... — run CMD (recording DESC as removed), or in --dry-run just
# announce it. A failing command degrades to a warning, never aborts the run.
do_or_echo() {
  local desc="$1"
  shift
  if [ "$DRY_RUN" = 1 ]; then
    ui_detail "[dry-run] would $desc"
    return 0
  fi
  ui_active "$desc"
  if "$@"; then
    rec_removed "$desc"
  else
    # Non-fatal, but never silent: a failed reversal is exactly "left to finish by hand", so
    # record it (with the command to retry) into the ledger the closing summary surfaces.
    # `printf %q` shell-escapes each argument so the retry hint stays copy-pasteable even
    # when a path or value contains spaces or metacharacters.
    ui_warn "failed: $desc (continuing)"
    rec_failed "$desc — retry by hand: $(printf '%q ' "$@")"
  fi
}

# --- Tier 1: auto-reverse the provably-ours, reversible state ----------------------
tier1_unstow() {
  ui_step "Removing dotfiles symlinks (stow)"
  if ! command -v stow >/dev/null 2>&1; then
    ui_warn "stow not found — cannot unlink the dotfiles automatically."
    rec_manual "install stow, then: stow --no-folding -D --dir='$DOTFILES' --target=\"\$HOME\" home"
    return 0
  fi
  # stow -D removes exactly the symlinks pointing back into this repo — the safest
  # "only reverse what we own" primitive here. A no-op (exit 0) if already unstowed.
  do_or_echo "unstow dotfiles (stow --no-folding -D … home)" \
    stow --no-folding -D --dir="$DOTFILES" --target="$HOME" home
}

tier1_mcp() {
  command -v claude >/dev/null 2>&1 || return 0
  local base="$DOTFILES/claude_mcp.json"
  [ -f "$base" ] || return 0
  command -v jq >/dev/null 2>&1 || {
    rec_manual "remove MCP servers manually: claude mcp list --scope user, then claude mcp remove <name> --scope user"
    return 0
  }
  ui_step "Removing Claude Code MCP server registrations (user scope)"
  local name
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    if [ "$DRY_RUN" = 1 ]; then
      ui_detail "[dry-run] would deregister MCP server '$name' (if registered)"
    elif claude mcp remove "$name" --scope user >/dev/null 2>&1; then
      ui_active "deregister MCP server '$name'"
      rec_removed "deregister MCP server '$name'"
    else
      # `claude mcp remove` exits non-zero when the server isn't registered — the common
      # re-run or install-skipped case. That IS the desired end state, so report it as a
      # no-op (left), not a failure; mirrors install.sh's own `|| true` on this call.
      rec_left "MCP server '$name' not registered (nothing to remove)"
    fi
  done < <(un_mcp_names "$base" "$HOME/.config/dotfiles/claude_mcp.local.json")
}

tier1_iterm2() {
  command -v defaults >/dev/null 2>&1 || return 0
  local cur
  cur="$(defaults read com.googlecode.iterm2 PrefsCustomFolder 2>/dev/null || true)"
  [ -n "$cur" ] || return 0
  ui_step "Resetting iTerm2 preferences pointer"
  if [ "$cur" != "$DOTFILES/iterm2" ]; then
    rec_left "iTerm2 PrefsCustomFolder points elsewhere ($cur) — not ours, left as-is"
    return 0
  fi
  do_or_echo "clear iTerm2 PrefsCustomFolder" defaults delete com.googlecode.iterm2 PrefsCustomFolder
  do_or_echo "clear iTerm2 LoadPrefsFromCustomFolder" defaults delete com.googlecode.iterm2 LoadPrefsFromCustomFolder
}

# --- Tier 2: offer to remove the created/enumerable artifacts (default no) ---------
tier2_tpm() {
  local tpm_dir="$HOME/.config/tmux/plugins/tpm"
  [ -d "$tpm_dir" ] || return 0
  ui_step "TPM (tmux plugin manager)"
  # install.sh clones TPM to the standard path but REUSES one that's already there, so a
  # present dir doesn't prove we put it there — offer rather than auto-remove.
  if offer "Remove the TPM clone at $tpm_dir? (skip if you had TPM before these dotfiles)"; then
    do_or_echo "remove TPM clone ($tpm_dir)" rm -rf "$tpm_dir"
  else
    rec_declined "TPM left in place ($tpm_dir)"
  fi
  rec_left "tmux plugins under ~/.config/tmux/plugins/ (installed by TPM; left in place)"
}

tier2_uv_tools() {
  command -v uv >/dev/null 2>&1 || return 0
  local list="$DOTFILES/uv_tools.txt"
  [ -f "$list" ] || return 0
  local names=() name line
  while IFS= read -r line; do
    name="$(un_uv_tool_name "$line")"
    [ -n "$name" ] && names+=("$name")
  done <"$list"
  [ "${#names[@]}" -gt 0 ] || return 0
  ui_step "uv-managed CLI tools (installed from uv_tools.txt)"
  ui_detail "${names[*]}"
  if offer "Uninstall these ${#names[@]} uv tools? (some you may use outside this repo)"; then
    for name in "${names[@]}"; do
      do_or_echo "uv tool uninstall $name" uv tool uninstall "$name"
    done
  else
    rec_declined "uv tools left installed (${#names[@]}): ${names[*]}"
  fi
}

tier2_ollama_models() {
  command -v ollama >/dev/null 2>&1 || return 0
  curl -fsS -m 2 http://localhost:11434/api/tags >/dev/null 2>&1 || {
    rec_left "Ollama models not checked (server not running); start Ollama and re-run to manage them"
    return 0
  }
  # The model names come from the same shared fragment the installer provisions from, so we
  # always offer to remove exactly what it pulls — no drift if a model tag changes. Guard the
  # source: if it fails, silently offering nothing would read as "no models installed" —
  # degrade to an honest manual hint instead.
  # shellcheck source=scripts/ollama_models.sh disable=SC1091
  if ! . "$DOTFILES/scripts/ollama_models.sh" 2>/dev/null || [ -z "${OLLAMA_MODEL:-}" ]; then
    rec_manual "couldn't load the model list; remove models by hand: ollama list, then ollama rm <model>"
    return 0
  fi
  local present model
  present="$(ollama list 2>/dev/null | awk 'NR>1 {print $1}')"
  ui_step "Ollama models provisioned by this repo"
  # ${VAR:-} defaults: a fragment missing a var (hand-edited, trimmed by a fork) must skip
  # that role, not abort the whole run under set -u before the summary prints. The legacy
  # list expands unquoted on purpose — it is a space-separated list of retired tags.
  # shellcheck disable=SC2086
  for model in "${OLLAMA_MODEL:-}" "${OLLAMA_VISION_MODEL:-}" "${OLLAMA_MLX_MODEL:-}" "${OLLAMA_BRAINSTORM_MODEL:-}" ${OLLAMA_LEGACY_MODELS:-}; do
    [ -n "$model" ] || continue
    printf '%s\n' "$present" | grep -qxF "$model" || continue
    if offer "Remove Ollama model $model?"; then
      do_or_echo "ollama rm $model" ollama rm "$model"
    else
      rec_declined "Ollama model left: $model"
    fi
  done
}

# --- Tier 3: ask about the lossy system changes ------------------------------------
tier3_login_shell() {
  local cur
  cur="$(dscl . -read "/Users/$(id -un)" UserShell 2>/dev/null | awk '{print $2}')"
  [ -n "$cur" ] || cur="${SHELL:-}"
  case "$cur" in
  /bin/zsh) return 0 ;; # the macOS system shell; not something we set
  *fish | *zsh) ;;      # ours: fish, or a Homebrew-installed zsh (#35)
  *) return 0 ;;
  esac
  ui_step "Login shell"
  if offer "Reset your login shell from $cur back to /bin/zsh (macOS default)?"; then
    # chsh prompts for your password; we do not pre-warm sudo for a single call.
    do_or_echo "reset login shell to /bin/zsh (chsh)" chsh -s /bin/zsh
  else
    rec_declined "login shell left as $cur"
    rec_manual "reset your login shell: chsh -s /bin/zsh"
  fi
}

tier3_pam() {
  local pam=/etc/pam.d/sudo_local
  [ -f "$pam" ] || return 0
  ui_step "Touch ID for sudo (/etc/pam.d/sudo_local)"
  if ! un_pam_is_ours "$(cat "$pam" 2>/dev/null)"; then
    rec_left "$pam exists but is not the file we wrote — left untouched"
    return 0
  fi
  if offer "Remove $pam (disables Touch ID for sudo; needs your password)?"; then
    do_or_echo "remove $pam (sudo)" sudo rm -f "$pam"
  else
    rec_declined "Touch ID for sudo left enabled ($pam)"
    rec_manual "disable Touch ID for sudo: sudo rm /etc/pam.d/sudo_local"
  fi
}

# --- Tier 4: report what we deliberately never touch -------------------------------
tier4_report() {
  # Lossy system state with no captured prior value — we report, never guess.
  rec_left "macOS defaults (macos.sh) and the Dock (dock.sh) — overwritten with no prior-state backup; not reversible"
  rec_manual "reset the Dock to defaults if you want: defaults delete com.apple.dock; killall Dock"
  rec_left "application firewall + stealth mode — installer turned these ON; left on"
  rec_manual "disable the firewall if you want: sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate off"

  local shell_bin
  for shell_bin in "$(command -v fish 2>/dev/null || true)" "$(command -v zsh 2>/dev/null || true)"; do
    [ -n "$shell_bin" ] || continue
    [ "$shell_bin" = /bin/zsh ] && continue # macOS's own zsh; not something we registered
    if grep -qxF "$shell_bin" /etc/shells 2>/dev/null; then
      rec_left "$shell_bin remains registered in /etc/shells (harmless)"
      rec_manual "remove it if you want: sudo sed -i '' '\\|^$shell_bin\$|d' /etc/shells"
    fi
  done

  # Shared tooling we installed but do not own outright — never auto-removed.
  rec_left "Homebrew, uv, and the Claude CLI — shared, system-wide; not removed"
  rec_manual "review brew packages (this repo's are in Brewfile): brew leaves, then brew uninstall <name>"
  command -v atuin >/dev/null 2>&1 &&
    rec_left "atuin's history database (~/.local/share/atuin/) — your shell history; left in place"

  # User-authored, machine-local data — never deleted.
  rec_left "machine-local config under ~/.config/dotfiles/ (overlays, secrets refs) — your data; left in place"
  rec_left "the generated ~/.claude/settings.json (accrued local prefs) — left in place"
  # Surface any pre-stow backups the installer made of YOUR divergent files.
  local bak found=0
  for bak in "$HOME/Library/Application Support/Code/User/settings.json".pre-stow.bak* \
    "$HOME/.config/atuin/config.toml".pre-stow.bak* \
    "$HOME/.config/topgrade.toml".pre-stow.bak* \
    "$HOME/.gitconfig".pre-stow.bak*; do
    [ -e "$bak" ] || continue
    rec_left "backup of your pre-install file: $bak"
    found=1
  done
  [ "$found" = 1 ] && rec_manual "your pre-install configs were preserved as *.pre-stow.bak — restore or delete them as you see fit"
  return 0
}

# --- summary -----------------------------------------------------------------------
_print_section() {
  local title="$1" color="$2"
  shift 2
  [ "$#" -gt 0 ] || return 0
  printf '\n%s%s%s\n' "$color" "$title" "$C_RESET"
  local item
  for item in "$@"; do printf '  %s\n' "$item"; done
}

print_summary() {
  printf '\n%s%s── uninstall summary ──%s\n' "$C_BOLD" "$C_BLUE" "$C_RESET"
  [ "$DRY_RUN" = 1 ] && ui_detail "(dry run — nothing was changed)"
  _print_section "Removed:" "$C_GREEN" ${REMOVED[@]+"${REMOVED[@]}"}
  _print_section "You declined:" "$C_DIM" ${DECLINED[@]+"${DECLINED[@]}"}
  _print_section "Left in place:" "$C_YELLOW" ${LEFT[@]+"${LEFT[@]}"}
  _print_section "Failed — finish by hand:" "$C_RED" ${FAILED[@]+"${FAILED[@]}"}
  _print_section "To finish manually:" "$C_BOLD" ${MANUAL[@]+"${MANUAL[@]}"}
  printf '\n'
}

usage() {
  cat <<EOF
Usage: uninstall.sh [--dry-run] [--yes] [--help]

Safe, idempotent reverse of install.sh. Removes the provably-ours setup (stow
symlinks, MCP registrations, the iTerm2 pointer), OFFERS to remove what it can't prove
it owns (the TPM clone, uv tools, Ollama models), ASKS about lossy system changes
(login shell, Touch-ID PAM), and REPORTS everything it leaves alone with how to finish.

  -n, --dry-run   Show what would happen; change nothing.
  -y, --yes       Skip the top confirmation. Tier-2/3 prompts still default to the
                  SAFE choice (skip + report), so --yes never removes anything you
                  were not asked about.
  -h, --help      Show this help.
EOF
}

main() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
    -n | --dry-run) DRY_RUN=1 ;;
    -y | --yes) ASSUME_YES=1 ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      ui_err "unknown argument: $1"
      usage
      exit 2
      ;;
    esac
    shift
  done

  if [ "$(uname)" != "Darwin" ]; then
    ui_err "uninstall.sh supports macOS only (detected $(uname))."
    exit 1
  fi

  printf '%suninstall.sh%s — reversing this dotfiles install (%s)\n' "$C_BOLD" "$C_RESET" "$DOTFILES"
  [ "$DRY_RUN" = 1 ] && ui_detail "dry run: previewing only"
  proceed_gate

  tier1_unstow
  tier1_mcp
  tier1_iterm2
  tier2_tpm
  tier2_uv_tools
  tier2_ollama_models
  tier3_login_shell
  tier3_pam
  tier4_report

  print_summary
}

# Only run when executed directly — sourcing (e.g. tests/uninstall.bats) just loads
# the pure helpers above without performing any action.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  set -uo pipefail
  main "$@"
fi
