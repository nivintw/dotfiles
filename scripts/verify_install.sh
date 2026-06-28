# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Post-install verification for install.sh. Re-derives the intended end state and
# reports it; it NEVER mutates anything and NEVER needs sudo (every probe here —
# brew bundle check, the firewall global state, the login shell, pam_tid, bioutil —
# reads fine as your user), so it's safe to run any time and can't trigger a
# password prompt of its own.
#
# Two ways in:
#   - install.sh sources this and calls `verify_install "$DOTFILES"` at the end to
#     build its closing summary.
#   - Standalone:  bash scripts/verify_install.sh   (re-check a machine any time;
#     exits non-zero if anything needs attention).
#
# Sourcing has NO side effects — it only defines functions. The pure path/JSON
# predicates (vi_symlink_into_repo / vi_is_json_object / vi_gitconfig_includes) are
# unit-tested by tests/verify_install.bats. Kept bash 3.2-safe to match install.sh.
#
# verify_install emits one tab-separated record per check to stdout:
#     OK<TAB><message>      a check passed
#     BAD<TAB><message>     a check failed (belongs in "needs attention")
# The caller renders these however it likes; the standalone main below prints them
# plainly. Keeping render OUT of this function is what lets install.sh fold the BAD
# lines into the same "needs attention" list as its collected runtime warnings.

# Under the --core install profile (DOTFILES_CORE=1) the baseline check below verifies the
# casks-stripped subset, so source the pure brewfile_core() filter. Guarded so it's a no-op
# when install.sh already sourced it; sourced relative to this file so the standalone /
# harness path (which sources only verify_install.sh) still finds it. Defines a function
# only — no other side effect.
# shellcheck source=brewfile_core.sh disable=SC1091
command -v brewfile_core >/dev/null 2>&1 || . "$(dirname "${BASH_SOURCE[0]}")/brewfile_core.sh"

# --- pure predicates (no system state; unit-tested) -------------------------

# Abbreviate a leading $HOME to ~ for display. The ~ lives in the REPLACEMENT half
# of the expansion, so it's a literal character, not a path shellcheck should warn
# about expanding (SC2088).
vi_tilde() { printf '%s\n' "${1/#$HOME/\~}"; }

# True when $1 is a symlink that resolves to a path inside repo dir $2. Used to
# confirm stow actually linked a file into this repo (not a stale real file or a
# link into some other tree). A dangling or out-of-tree link fails.
vi_symlink_into_repo() {
  link="$1"
  repo="$2"
  [ -L "$link" ] || return 1
  target="$(readlink "$link")" || return 1
  # Relative link target -> resolve against the link's own directory.
  case "$target" in
  /*) ;;
  *) target="$(cd "$(dirname "$link")" 2>/dev/null && cd "$(dirname "$target")" 2>/dev/null && pwd)/$(basename "$target")" || return 1 ;;
  esac
  repo_abs="$(cd "$repo" 2>/dev/null && pwd)" || return 1
  case "$target" in
  "$repo_abs"/*) return 0 ;;
  *) return 1 ;;
  esac
}

# True when file $1 exists and is a JSON OBJECT (not just any valid JSON). Mirrors
# the install.sh settings-merge guard: an array/scalar/empty file must NOT pass.
vi_is_json_object() {
  [ -f "$1" ] || return 1
  command -v jq >/dev/null 2>&1 || return 1
  jq -e 'type == "object"' "$1" >/dev/null 2>&1
}

# True when git config file $1 has an [include] path equal to $2 (after ~ expansion).
# That's the mechanism the dotfiles rely on for the machine-local overlay to win.
vi_gitconfig_includes() {
  cfg="$1"
  want="${2/#\~/$HOME}"
  { [ -f "$cfg" ] || [ -L "$cfg" ]; } || return 1
  command -v git >/dev/null 2>&1 || return 1
  # Process substitution keeps the loop in THIS shell, so `return` works directly.
  while IFS= read -r p; do
    [ "${p/#\~/$HOME}" = "$want" ] && return 0
  done < <(git config -f "$cfg" --get-all include.path 2>/dev/null)
  return 1
}

# --- system probes ----------------------------------------------------------

# Count of fingerprints enrolled for the current user (0 if none / no sensor /
# tool unavailable). Touch ID for sudo (pam_tid) silently falls back to a password
# when this is 0, which is the confusing "why is it still asking?" failure.
vi_touchid_enrolled_count() {
  command -v bioutil >/dev/null 2>&1 || {
    printf '0\n'
    return 0
  }
  # "User 501:\t1 biometric template(s)" -> sum the leading integers. The grep
  # stages exit non-zero when bioutil's output doesn't match (a sensor with ZERO
  # enrolled prints, no sensor at all, or different wording) — which is precisely
  # the no-fingerprint case this is meant to catch. Under the caller's
  # `set -o pipefail` that non-zero would propagate and abort, so `|| true` guards
  # it; awk's END runs even on empty input, so we always get an integer, and the
  # ${count:-0} default covers any remaining edge. Total function: one int, exit 0.
  count="$(bioutil -c 2>/dev/null |
    grep -oE '[0-9]+ biometric template' |
    grep -oE '^[0-9]+' |
    awk '{s += $1} END {print s + 0}' || true)"
  printf '%s\n' "${count:-0}"
}

# True when Touch ID for sudo is wired into /etc/pam.d/sudo_local (mode 644, so no
# sudo needed to read it).
vi_pam_tid_enabled() {
  grep -qs 'pam_tid.so' /etc/pam.d/sudo_local 2>/dev/null
}

# Emit OK/BAD records to stdout (see header). $1 is the repo (dotfiles) dir; all
# other paths default to the live machine.
verify_install() {
  dotfiles="${1:?usage: verify_install <dotfiles-dir>}"
  ok() { printf 'OK\t%s\n' "$1"; }
  bad() { printf 'BAD\t%s\n' "$1"; }

  # 1. Baseline Homebrew packages all installed. Under the --core profile (DOTFILES_CORE=1),
  #    check the casks-stripped subset instead, since the GUI casks were never installed.
  if command -v brew >/dev/null 2>&1; then
    if [ "${DOTFILES_CORE:-0}" = "1" ]; then
      core_bf="$(mktemp -t brewfile-core)"
      brewfile_core "$dotfiles/Brewfile" >"$core_bf"
      if brew bundle check --file="$core_bf" >/dev/null 2>&1; then
        ok "Homebrew core (CLI formulae) packages all installed"
      else
        bad "Homebrew core packages missing — run: DOTFILES_CORE=1 brew bundle check --verbose --file=$core_bf"
      fi
      rm -f "$core_bf"
    elif brew bundle check --file="$dotfiles/Brewfile" >/dev/null 2>&1; then
      ok "Homebrew baseline packages all installed"
    else
      bad "Homebrew baseline packages missing — run: brew bundle check --verbose --file=$dotfiles/Brewfile"
    fi

    # 2. Each selected opt-in bundle installed (read the selection file directly so
    #    this works standalone, without install.sh's in-memory state).
    sel="$HOME/.config/dotfiles/bundles"
    if [ -f "$sel" ]; then
      while IFS= read -r b; do
        [ -n "$b" ] || continue
        bf="$dotfiles/Brewfile.d/$b.brewfile"
        [ -f "$bf" ] || continue
        if brew bundle check --file="$bf" >/dev/null 2>&1; then
          ok "opt-in bundle '$b' installed"
        else
          bad "opt-in bundle '$b' has missing packages — run: brew bundle check --verbose --file=$bf"
        fi
      done < <(grep -vE '^[[:space:]]*(#|$)' "$sel" 2>/dev/null)
    fi

    # 3. Machine-private additions, if any.
    local_bf="$HOME/.config/dotfiles/Brewfile.local"
    if [ -f "$local_bf" ] && grep -qvE '^[[:space:]]*(#|$)' "$local_bf" 2>/dev/null; then
      if brew bundle check --file="$local_bf" >/dev/null 2>&1; then
        ok "machine-private Brewfile.local installed"
      else
        bad "Brewfile.local has missing packages — run: brew bundle check --verbose --file=$local_bf"
      fi
    fi
  else
    bad "Homebrew not found on PATH — the bundle step did not complete"
  fi

  # 4. fish is the login shell.
  fish_bin="$(command -v fish 2>/dev/null || true)"
  login_shell="$(dscl . -read "/Users/$(id -un)" UserShell 2>/dev/null | awk '{print $2}')"
  if [ -n "$fish_bin" ] && [ "$login_shell" = "$fish_bin" ]; then
    ok "fish is the login shell"
  else
    bad "login shell is '${login_shell:-unknown}', not fish (${fish_bin:-not installed})"
  fi

  # 5. Touch ID for sudo: enabled AND a fingerprint enrolled.
  if vi_pam_tid_enabled; then
    enrolled="$(vi_touchid_enrolled_count)"
    if [ "${enrolled:-0}" -ge 1 ]; then
      ok "Touch ID for sudo enabled ($enrolled fingerprint(s) enrolled)"
    else
      bad "Touch ID for sudo is enabled but NO fingerprint is enrolled — sudo will keep prompting for your password. Enroll one in System Settings → Touch ID & Password (or this Mac has no Touch ID sensor)."
    fi
  else
    bad "Touch ID for sudo not enabled (/etc/pam.d/sudo_local) — sudo will prompt for your password"
  fi

  # 6. Application firewall on (readable without sudo).
  fw="/usr/libexec/ApplicationFirewall/socketfilterfw"
  if [ -x "$fw" ] && "$fw" --getglobalstate 2>/dev/null | grep -qi enabled; then
    ok "application firewall enabled"
  else
    bad "application firewall is OFF — enable it in System Settings → Network → Firewall"
  fi

  # 7. Key dotfiles symlinks resolve into this repo.
  for link in \
    "$HOME/.gitconfig" \
    "$HOME/.config/fish/config.fish" \
    "$HOME/.claude/CLAUDE.md"; do
    if vi_symlink_into_repo "$link" "$dotfiles"; then
      ok "symlinked into repo: $(vi_tilde "$link")"
    else
      bad "not symlinked into repo (stow may not have run): $(vi_tilde "$link")"
    fi
  done

  # 8. Generated Claude settings is a valid JSON object.
  settings="$HOME/.claude/settings.json"
  if vi_is_json_object "$settings"; then
    ok "$(vi_tilde "$settings") is valid JSON"
  else
    bad "$(vi_tilde "$settings") missing or not a JSON object"
  fi

  # 9. ~/.gitconfig Include-s the machine-local overlay (so it can override).
  gitconfig="$HOME/.gitconfig"
  gitconfig_local="$HOME/.gitconfig_local"
  if vi_gitconfig_includes "$gitconfig" "$gitconfig_local"; then
    ok "$(vi_tilde "$gitconfig") includes $(vi_tilde "$gitconfig_local")"
  else
    bad "$(vi_tilde "$gitconfig") does not [include] $(vi_tilde "$gitconfig_local")"
  fi
}

# --- standalone entrypoint --------------------------------------------------
# Only runs when executed directly (bash scripts/verify_install.sh), not when
# sourced by install.sh. Renders the records plainly and exits non-zero if any
# check failed, so it's usable as a one-shot health check or in CI.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  set -euo pipefail
  here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  problems=0
  while IFS=$'\t' read -r status msg; do
    case "$status" in
    OK) printf '  \033[32m✔\033[0m %s\n' "$msg" ;;
    BAD)
      printf '  \033[33m⚠\033[0m %s\n' "$msg"
      problems=$((problems + 1))
      ;;
    esac
  done < <(verify_install "$here")
  if [ "$problems" -eq 0 ]; then
    printf '\n\033[32mAll checks passed.\033[0m\n'
    exit 0
  fi
  printf '\n\033[33m%d check(s) need attention.\033[0m\n' "$problems"
  exit 1
fi
