#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# End-to-end installer smoke test: boot a clean Tart VM, run install.sh inside it from
# scratch, and assert the post-install verification passes. This is the one thing the
# unit/config tests can't do — prove the installer works on a genuinely clean machine.
# install.sh is now a thin uv shim that hands off to the dotfiles-install Python installer,
# so this exercises that installer end-to-end and is the verification gate for changes to it.
#
# How it works:
#   - tart clone + run a headless ephemeral VM (deleted on exit unless --keep).
#   - SSH in via SSH_ASKPASS (no password ever lands in argv).
#   - Ship the repo in with `git archive HEAD` — no .git, no shared-mount race.
#   - Run install.sh --core DETACHED (nohup; rc -> marker, output -> log), polled over fresh
#     SSH connections so the run survives the installer toggling the firewall mid-install. The
#     --core profile installs CLI formulae only — skipping the GUI app/font casks and the
#     Ollama model pull a headless smoke VM doesn't need — and verify runs core-aware to match.
#   - By default install TWICE (idempotency); --once does a single pass.
#   - Gate on the installer's `dotfiles-install --verify-stream` OK/BAD output, tolerating only
#     the Touch-ID-no-sensor BAD (a VM has no biometric sensor); everything else stays strict.
#
# Heavy + opt-in: the first run pulls a multi-GB base image and a full install takes
# many minutes. Run it directly (scripts/vm-smoke.sh) or via the opt-in pytest:
#   DOTFILES_VM_SMOKE=1 uv run pytest -m integration

# ============================================================================
# Pure helpers — safe to `source` (no side effects at load time). tests/vm_smoke.bats
# sources this file to exercise the gate logic without booting a VM, so nothing below
# the function definitions runs until main() is invoked from the entrypoint guard.
# Kept bash 3.2-safe (it runs on the host, and forces bash in the guest).
# ============================================================================

usage() {
  cat <<EOF
Usage: vm-smoke.sh [--os macos|linux] [--image REF] [--once] [--negative] [--keep] [-h|--help]

Boot a clean Tart VM, run install.sh end-to-end inside it, and verify the result.
Requires tart (in the Brewfile) and an Apple Silicon host.

  --os OS       Guest OS to smoke: macos (default) or linux. Both run the full,
                strict --verify-stream gate — the verification probes are OS-aware
                (dscl/socketfilterfw on macOS; passwd/ufw on Linux; Touch ID is
                macOS-only). Only the macOS-purpose phases (iTerm2, macos.sh, Dock)
                are skipped on linux.
  --image REF   Base VM image to clone (default: \$VM_SMOKE_IMAGE, else the cirruslabs
                macos-sequoia-base / ubuntu image for the chosen --os)
  --once        Install only once (default installs twice to prove idempotency)
  --negative    Self-test the gate: after a clean install, break the firewall in the VM
                (socketfilterfw off on macOS, ufw disable on linux) and assert the gate
                now FAILS (proves the gate isn't a rubber stamp).
  --keep        Don't delete the VM on exit (for debugging a failed run)
  -h, --help    Show this help

Env: VM_SMOKE_OS (default macos), VM_SMOKE_IMAGE, VM_SMOKE_USER (default admin),
     VM_SMOKE_PASS (default admin), VM_SMOKE_INSTALL_TIMEOUT (seconds, default 3600).
EOF
}

# Progress logs go to stderr so stdout stays reserved for the installer's --verify-stream
# record stream that evaluate_stream parses.
log() { printf '\033[1;34m==>\033[0m %s\n' "$*" >&2; }

# is_tolerated MSG — true when a BAD verify record is an expected-in-a-VM failure.
# A headless Tart VM has no Touch ID sensor, so the installer wires pam_tid but no
# fingerprint can ever enroll; verification flags that as BAD. That single case is
# tolerated. Every other BAD — crucially the application firewall — stays strict.
is_tolerated() {
  case "$1" in
  *"NO fingerprint is enrolled"*) return 0 ;;
  *) return 1 ;;
  esac
}

# evaluate_stream — read the installer's `OK<TAB>msg` / `BAD<TAB>msg` records, plus a
# trailing `VERIFY_DONE<TAB>rc` sentinel, on stdin. Render each to stderr and succeed only
# when every BAD is tolerated AND the sentinel was seen. The sentinel makes a truncated
# SSH stream (connection dropped mid-verify) fail closed instead of reading as a pass.
evaluate_stream() {
  local status msg untolerated=0 saw_done=0
  while IFS=$'\t' read -r status msg; do
    case "$status" in
    OK) printf '    \033[32mok \033[0m %s\n' "$msg" >&2 ;;
    BAD)
      if is_tolerated "$msg"; then
        printf '    \033[33mtol\033[0m %s\n' "$msg" >&2
      else
        printf '    \033[31mBAD\033[0m %s\n' "$msg" >&2
        untolerated=$((untolerated + 1))
      fi
      ;;
    VERIFY_DONE) saw_done=1 ;;
    esac
  done
  if [ "$saw_done" -ne 1 ]; then
    printf 'vm-smoke.sh: verify stream incomplete (no VERIFY_DONE sentinel) — failing closed\n' >&2
    return 1
  fi
  [ "$untolerated" -eq 0 ]
}

# ============================================================================
# main — the actual VM lifecycle. Everything with side effects lives here (and in the
# functions it nests), so sourcing the file for tests stays inert.
# ============================================================================

main() {
  set -euo pipefail

  local OS_TARGET="${VM_SMOKE_OS:-macos}"
  # The default image depends on --os, so resolve it after arg parsing; an explicit --image
  # or $VM_SMOKE_IMAGE still wins.
  local IMAGE="${VM_SMOKE_IMAGE:-}"
  local VM_USER="${VM_SMOKE_USER:-admin}"
  # Generous default: a from-scratch install downloads the full baseline Brewfile, including
  # heavy GUI casks, over the network into a fresh VM. Override with VM_SMOKE_INSTALL_TIMEOUT.
  local INSTALL_TIMEOUT="${VM_SMOKE_INSTALL_TIMEOUT:-3600}"
  local ONCE=0 NEGATIVE=0
  local VM_IP=""
  # KEEP, VM_NAME and WORK are read by the EXIT trap (cleanup), which can fire after main's
  # locals have gone out of scope — so they are deliberately GLOBAL, not local. They are
  # assigned only inside main, so sourcing the file for tests never sets them.
  KEEP=0
  VM_NAME=""
  WORK=""
  # Exported (not local) so the SSH_ASKPASS helper child process inherits it. Keeping
  # the password out of argv is the whole reason for the askpass dance.
  export VM_SMOKE_PASS="${VM_SMOKE_PASS:-admin}"

  while [ $# -gt 0 ]; do
    case "$1" in
    --os) OS_TARGET="${2:?--os needs a value}" && shift 2 ;;
    --os=*) OS_TARGET="${1#*=}" && shift ;;
    --image) IMAGE="${2:?--image needs a value}" && shift 2 ;;
    --image=*) IMAGE="${1#*=}" && shift ;;
    --once) ONCE=1 && shift ;;
    --negative) NEGATIVE=1 && shift ;;
    --keep) KEEP=1 && shift ;;
    -h | --help)
      usage
      return 0
      ;;
    *)
      printf 'vm-smoke.sh: unexpected argument: %s\n\n' "$1" >&2
      usage >&2
      return 2
      ;;
    esac
  done

  if ! command -v tart >/dev/null 2>&1; then
    printf 'vm-smoke.sh: tart not found on PATH (brew bundle from the Brewfile installs it).\n' >&2
    return 1
  fi

  # VM_USER is interpolated into a remote sudo command string below; require a plain username
  # so it can't break out of that quoting. Operator-set, so this is defense-in-depth.
  case "$VM_USER" in
  '' | *[!A-Za-z0-9_-]*)
    printf 'vm-smoke.sh: VM_SMOKE_USER must be a plain username ([A-Za-z0-9_-]); got: %s\n' "$VM_USER" >&2
    return 2
    ;;
  esac

  # Validate --os and resolve the per-OS default image (an explicit --image / $VM_SMOKE_IMAGE wins).
  case "$OS_TARGET" in
  macos) : "${IMAGE:=ghcr.io/cirruslabs/macos-sequoia-base:latest}" ;;
  linux) : "${IMAGE:=ghcr.io/cirruslabs/ubuntu:latest}" ;;
  *)
    printf 'vm-smoke.sh: --os must be macos or linux; got: %s\n' "$OS_TARGET" >&2
    return 2
    ;;
  esac

  # Repo root, resolved with builtins so the preflight above works under a stripped PATH.
  local DOTFILES
  DOTFILES="$(cd "${BASH_SOURCE[0]%/*}/.." && pwd)"

  # Scratch dir for the askpass helper + the `tart run` console log. Cleaned up on exit.
  WORK="$(mktemp -d -t vm-smoke)"
  local ASKPASS="$WORK/askpass" RUN_LOG="$WORK/run.log"
  cat >"$ASKPASS" <<'ASK'
#!/bin/sh
printf '%s\n' "${VM_SMOKE_PASS:-admin}"
ASK
  chmod 700 "$ASKPASS"

  VM_NAME="dotfiles-smoke-$$"

  # Defensive `${...:-}` reads: the trap can fire from anywhere, and under `set -u` a bare
  # reference to an unset global would itself abort the trap before the VM is deleted.
  cleanup() {
    if [ "${KEEP:-0}" -eq 1 ]; then
      log "Leaving VM '${VM_NAME:-?}' in place (--keep). Delete with: tart delete ${VM_NAME:-}"
    elif [ -n "${VM_NAME:-}" ]; then
      tart stop "$VM_NAME" >/dev/null 2>&1 || true
      tart delete "$VM_NAME" >/dev/null 2>&1 || true
    fi
    if [ -n "${WORK:-}" ]; then rm -rf "$WORK"; fi
  }
  trap cleanup EXIT

  # SSH that authenticates via SSH_ASKPASS. SSH_ASKPASS_REQUIRE=force makes ssh use the
  # helper even with a tty present, so the password is never read from argv or a prompt —
  # and stdin stays free to carry data (the git-archive tar, a heredoc script).
  ssh_vm() {
    SSH_ASKPASS="$ASKPASS" SSH_ASKPASS_REQUIRE=force DISPLAY=:0 \
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o LogLevel=ERROR -o ConnectTimeout=10 \
      "${VM_USER}@${VM_IP}" "$@"
  }

  # wait_for DESC TIMEOUT INTERVAL CMD... — poll CMD until it succeeds or TIMEOUT seconds
  # elapse, sleeping INTERVAL between probes. Use a fine INTERVAL where startup latency matters
  # (IP/SSH) and a coarse one for long waits (the multi-minute install) so we don't open
  # hundreds of fresh SSH connections just to poll a marker file.
  wait_for() {
    local desc="$1" timeout="$2" interval="$3" waited=0
    shift 3
    until "$@" >/dev/null 2>&1; do
      if [ "$waited" -ge "$timeout" ]; then
        printf 'vm-smoke.sh: timed out after %ss waiting for %s\n' "$timeout" "$desc" >&2
        return 1
      fi
      sleep "$interval"
      waited=$((waited + interval))
    done
  }

  # run_install LABEL — launch install.sh detached in the VM and wait for its rc marker.
  # Detaching is what lets the run survive the installer enabling the firewall/stealth
  # mode mid-install (which can sever a long-lived SSH session); we poll over fresh
  # connections instead of holding one open.
  # The single-quoted ssh_vm payloads below intentionally defer $HOME / $? expansion to
  # the guest, so SC2016 (don't-expand-in-single-quotes) is the desired behaviour, not a bug.
  run_install() {
    local label="$1" rc
    log "$label: launching install.sh --no-bundles --core (detached) in the VM"
    # --core: CLI formulae only — skip the heavy GUI app/font casks and the Ollama model
    # pull, which a headless smoke VM doesn't need and which would dominate the run time.
    # Run the preconditions (cd) in the FOREGROUND so a launch failure propagates as a
    # non-zero SSH exit and fails fast here — rather than only surfacing later as an rc-marker
    # timeout. Only the install itself is backgrounded.
    # shellcheck disable=SC2016
    if ! ssh_vm 'cd "$HOME/dotfiles" || exit 1
      rm -f .install.rc .install.log
      nohup sh -c "./install.sh --no-bundles --core >.install.log 2>&1; echo \$? >.install.rc" >/dev/null 2>&1 </dev/null &
      exit 0'; then
      log "$label: failed to launch install.sh in the VM"
      return 1
    fi
    log "$label: waiting for install to finish (timeout ${INSTALL_TIMEOUT}s)"
    # shellcheck disable=SC2016
    if ! wait_for "install to finish" "$INSTALL_TIMEOUT" 15 \
      ssh_vm 'test -f "$HOME/dotfiles/.install.rc"'; then
      log "$label: TIMED OUT — last 40 log lines from the VM:"
      # shellcheck disable=SC2016
      ssh_vm 'tail -n 40 "$HOME/dotfiles/.install.log" 2>/dev/null' >&2 || true
      return 1
    fi
    # shellcheck disable=SC2016
    rc="$(ssh_vm 'cat "$HOME/dotfiles/.install.rc"' | tr -dc '0-9')"
    if [ "${rc:-1}" != "0" ]; then
      log "$label: install.sh exited ${rc:-?} — last 40 log lines from the VM:"
      # shellcheck disable=SC2016
      ssh_vm 'tail -n 40 "$HOME/dotfiles/.install.log" 2>/dev/null' >&2 || true
      return 1
    fi
    log "$label: install.sh completed cleanly (rc=0)"
  }

  # verify_gate LABEL — run `dotfiles-install --verify-stream` in the VM, capture its OK/BAD
  # stream plus the VERIFY_DONE sentinel (the installer emits both), and pipe it through
  # evaluate_stream here. Returns non-zero if any untolerated BAD is present or the stream was
  # truncated. `bash` is forced (the guest login shell is fish after install) so PATH can be
  # set portably to find uv; --core matches the casks-stripped --core install above.
  verify_gate() {
    local label="$1"
    # iter_records is OS-aware (dscl/socketfilterfw on macOS; passwd/ufw on Linux; Touch ID is
    # macOS-only), so the same strict gate runs on both guest OSes. Only the Touch-ID-no-sensor
    # BAD is tolerated (see is_tolerated) — a macOS-only record, so Linux runs fully strict.
    log "$label: running 'dotfiles-install --verify-stream' in the VM and evaluating the result"
    # shellcheck disable=SC2016  # $HOME must expand in the guest, not here
    ssh_vm 'bash -s' <<'REMOTE' | evaluate_stream
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
cd "$HOME/dotfiles"
uv run --no-dev --project "$HOME/dotfiles" dotfiles-install --core --verify-stream
REMOTE
  }

  # _remote_env — emit (to stdout) the shell that puts the uv shims (~/.local/bin) and the brew
  # prefix on PATH inside the guest. Prepended to the assert REMOTE scripts below: ssh_vm runs
  # `bash -s` directly (a non-login session, whatever the login shell), so nothing sources the
  # fish/profile PATH setup and fish / claude / the uv tools wouldn't otherwise resolve. Quoted
  # heredoc — $HOME / $b expand in the guest, not here — and the inapplicable brew paths simply
  # don't exist on the other OS.
  _remote_env() {
    cat <<'ENV'
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
for b in /opt/homebrew/bin/brew /usr/local/bin/brew /home/linuxbrew/.linuxbrew/bin/brew "$HOME/.linuxbrew/bin/brew"; do
  [ -x "$b" ] && eval "$("$b" shellenv)" && break
done
ENV
  }

  # assert_install_outputs — gate coverage for the install steps this harness's own hardening
  # made NON-FATAL (fisher, TPM, uv tools, the Claude CLI). verify_install asserts system state
  # (brew/shell/firewall/symlinks/settings) but not these, so without this a swallowed bootstrap
  # failure — exactly what `retry` degrades to a warning — would slip through a green gate. Each
  # output is deterministic in a --core install with network; MCP is excluded (it needs the
  # 1Password/PAT secrets a clean VM lacks). Reuses evaluate_stream: any BAD fails the gate.
  assert_install_outputs() {
    log "checking deterministic install outputs (Claude CLI, uv tools, TPM, fisher)"
    {
      _remote_env
      cat <<'REMOTE'
say() { printf '%s\t%s\n' "$1" "$2"; }
command -v claude >/dev/null 2>&1 && say OK "Claude CLI installed" || say BAD "Claude CLI missing (native installer step failed)"
command -v prek   >/dev/null 2>&1 && say OK "uv tool prek installed" || say BAD "uv tool prek missing (uv tools step failed)"
command -v rumdl  >/dev/null 2>&1 && say OK "uv tool rumdl installed" || say BAD "uv tool rumdl missing (uv tools step failed)"
[ -d "$HOME/.config/tmux/plugins/tpm" ] && say OK "TPM installed" || say BAD "TPM missing (tmux plugin step failed)"
fish -c 'functions -q fisher' >/dev/null 2>&1 && say OK "fisher installed" || say BAD "fisher missing (fish plugin bootstrap failed)"
fish -c 'functions -q tide' >/dev/null 2>&1 && say OK "fish_plugins installed (tide)" || say BAD "fish_plugins missing (fisher update failed)"
printf 'VERIFY_DONE\t0\n'
REMOTE
    } | ssh_vm 'bash -s' | evaluate_stream
  }

  # assert_linux_packages — Linux-only spot check of this slice's deliverable (#112): Linuxbrew
  # bootstrapped (phase 0) and `brew bundle` installed the cross-platform CLI formulae (phase 1),
  # and stow linked the dotfiles (phase 3). macOS asserts the equivalent via verify_gate; on Linux
  # that gate is deferred to #113, so check the concrete outputs here instead.
  assert_linux_packages() {
    log "checking Linuxbrew packages + stow symlinks (Linux)"
    {
      _remote_env
      cat <<'REMOTE'
say() { printf '%s\t%s\n' "$1" "$2"; }
command -v brew >/dev/null 2>&1 && say OK "Linuxbrew on PATH" || say BAD "brew missing (phase 0 bootstrap failed)"
command -v fish >/dev/null 2>&1 && say OK "fish installed (brew bundle)" || say BAD "fish missing (phase 1 brew bundle failed)"
command -v stow >/dev/null 2>&1 && say OK "stow installed (brew bundle)" || say BAD "stow missing (phase 1 brew bundle failed)"
command -v rg   >/dev/null 2>&1 && say OK "ripgrep installed (brew bundle)" || say BAD "ripgrep missing (phase 1 brew bundle failed)"
[ -L "$HOME/.config/fish/config.fish" ] && say OK "dotfiles stowed (config.fish symlink)" || say BAD "config.fish not a symlink (phase 3 stow failed)"
printf 'VERIFY_DONE\t0\n'
REMOTE
    } | ssh_vm 'bash -s' | evaluate_stream
  }

  log "Cloning ${IMAGE} -> ${VM_NAME} (pulls the base image on first run; multi-GB)"
  tart clone "$IMAGE" "$VM_NAME"

  log "Booting ${VM_NAME} headless"
  tart run --no-graphics "$VM_NAME" >"$RUN_LOG" 2>&1 &

  log "Waiting for the VM to acquire an IP"
  if ! wait_for "an IP address" 180 2 tart ip "$VM_NAME"; then
    log "VM never came up — 'tart run' console log:"
    cat "$RUN_LOG" >&2 || true
    return 1
  fi
  VM_IP="$(tart ip "$VM_NAME")"
  log "VM is up at ${VM_IP}"

  log "Waiting for SSH"
  wait_for "SSH" 180 2 ssh_vm true

  # install.sh acquires sudo with `sudo -v` for its privileged block, which
  # RE-AUTHENTICATES — and NOPASSWD does NOT cover `sudo -v`, so a headless SSH session
  # (no tty) would die at "Privileged setup". Install a sudoers drop-in
  # that disables authentication for the install user entirely (the VM equivalent of a real
  # Mac's password/Touch-ID prompt; the same thing CI runners do). The password is supplied
  # on stdin for `sudo -S` (used only if the VM actually needs one to write the file); the
  # username is passed via argv ($1). umask 337 makes the drop-in mode 0440, as sudoers wants.
  log "Disabling sudo authentication in the VM (needed for an unattended install)"
  if ! printf '%s\n' "$VM_SMOKE_PASS" | ssh_vm \
    "sudo -S -p '' bash -c 'umask 337; { echo \"Defaults:\$1 !authenticate\"; echo \"\$1 ALL=(ALL) NOPASSWD: ALL\"; } >/etc/sudoers.d/dotfiles-vm-smoke' _ '$VM_USER'"; then
    printf 'vm-smoke.sh: could not write the sudoers drop-in in the VM (wrong VM_SMOKE_PASS?).\n' >&2
    return 1
  fi
  # Verify the EXACT capability install.sh needs: `sudo -v` must not prompt. `-n` turns a
  # would-be prompt into a failure, so this passes only if authentication is truly disabled.
  if ! ssh_vm 'sudo -n -v' >/dev/null 2>&1; then
    printf 'vm-smoke.sh: sudo still wants authentication in the VM — install.sh would hang. Diagnostics:\n' >&2
    ssh_vm 'echo "[drop-in]"; sudo -n cat /etc/sudoers.d/dotfiles-vm-smoke 2>&1
      echo "[includedir]"; sudo -n grep -i includedir /etc/sudoers 2>&1
      echo "[sudo -n -v]"; sudo -n -v 2>&1' >&2 || true
    return 1
  fi

  # git archive ships committed state only — warn if the working tree has uncommitted edits so
  # nobody iterates on an install.sh change and reads a green run that tested the OLD code.
  if [ -n "$(git -C "$DOTFILES" status --porcelain 2>/dev/null)" ]; then
    log "WARNING: working tree has uncommitted changes — git archive HEAD tests the COMMITTED state, not them."
  fi
  log "Shipping the repo into the VM (git archive HEAD)"
  # shellcheck disable=SC2016  # $HOME must expand in the guest, not here
  git -C "$DOTFILES" archive --format=tar HEAD |
    ssh_vm 'rm -rf "$HOME/dotfiles" && mkdir -p "$HOME/dotfiles" && tar -x -C "$HOME/dotfiles"'

  if ! run_install "install (1/$([ "$ONCE" -eq 1 ] && echo 1 || echo 2))"; then
    log "Install FAILED."
    return 1
  fi
  if ! verify_gate "verify"; then
    log "Verification FAILED after the first install."
    return 1
  fi
  if ! assert_install_outputs; then
    log "Install-output check FAILED — a non-fatal bootstrap step (fisher/TPM/uv tools/Claude CLI) didn't complete."
    return 1
  fi
  if [ "$OS_TARGET" = linux ] && ! assert_linux_packages; then
    log "Linux package/stow check FAILED — Linuxbrew bootstrap or brew bundle didn't land the core tools."
    return 1
  fi

  if [ "$ONCE" -eq 0 ]; then
    if ! run_install "idempotency re-run (2/2)"; then
      log "Idempotency re-run FAILED — install.sh is not cleanly re-runnable."
      return 1
    fi
    # Re-assert post-install STATE, not just rc=0 — otherwise a second run that exits 0 but
    # clobbered a stow symlink or dropped a package would pass green. The verify gate is
    # OS-aware and strict on both guests; Linux additionally re-runs the concrete output
    # checks (Claude CLI / uv tools / TPM / fisher / packages), which verify doesn't cover.
    if ! verify_gate "re-verify"; then
      log "Verification FAILED after the idempotency re-run — install.sh is not cleanly re-runnable."
      return 1
    fi
    if [ "$OS_TARGET" = linux ]; then
      if ! assert_install_outputs || ! assert_linux_packages; then
        log "Re-run state check FAILED — the idempotency re-run didn't preserve the installed state."
        return 1
      fi
    fi
  fi

  if [ "$NEGATIVE" -eq 1 ]; then
    log "Negative self-test: disabling the firewall in the VM; the gate MUST now fail"
    # The disable must actually land — swallowing its failure would leave the firewall ON, the
    # gate would (correctly) pass, and the self-test would then misdiagnose that as "the gate
    # is not actually checking".
    if [ "$OS_TARGET" = macos ]; then
      ssh_vm 'sudo -n /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate off' \
        >/dev/null 2>&1
    else
      ssh_vm 'sudo -n ufw disable' >/dev/null 2>&1
    fi || {
      printf 'vm-smoke.sh: could not disable the firewall in the VM — cannot run the negative self-test.\n' >&2
      return 1
    }
    if verify_gate "negative"; then
      printf 'vm-smoke.sh: NEGATIVE self-test FAILED — the gate passed with the firewall OFF, so it is not actually checking.\n' >&2
      return 1
    fi
    log "Negative self-test PASSED — the gate correctly rejected a broken install."
  fi

  log "Smoke test PASSED — the installer ran clean and verification reported healthy."
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  main "$@"
fi
