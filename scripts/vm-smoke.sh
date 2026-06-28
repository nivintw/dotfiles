#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# End-to-end installer smoke test: boot a clean Tart VM, run install.sh inside it from
# scratch, and assert the post-install verification passes. This is the one thing the
# unit/config tests can't do — prove the installer works on a genuinely clean machine.
# It targets today's bash, macOS-only install.sh and is the verification gate the Python
# installer rewrite (#53) gets tested against.
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
#   - Gate on verify_install's OK/BAD stream, tolerating only the Touch-ID-no-sensor BAD
#     (a VM has no biometric sensor); the firewall and everything else stay strict.
#
# Heavy + opt-in: the first run pulls a multi-GB base image and a full install takes
# many minutes. Run it directly (scripts/vm-smoke.sh) or via the opt-in pytest:
#   DOTFILES_VM_SMOKE=1 uv run pytest -m integration

# ============================================================================
# Pure helpers — safe to `source` (no side effects at load time). tests/vm_smoke.bats
# sources this file to exercise the gate logic without booting a VM, so nothing below
# the function definitions runs until main() is invoked from the entrypoint guard.
# Kept bash 3.2-safe to match install.sh / verify_install.sh.
# ============================================================================

usage() {
  cat <<EOF
Usage: vm-smoke.sh [--image REF] [--once] [--negative] [--keep] [-h|--help]

Boot a clean Tart VM, run install.sh end-to-end inside it, and verify the result.
Requires tart (in the Brewfile) and an Apple Silicon host.

  --image REF   Base VM image to clone (default: \$VM_SMOKE_IMAGE or the cirruslabs
                macos-sequoia-base image)
  --once        Install only once (default installs twice to prove idempotency)
  --negative    Self-test the gate: after a clean install, break the firewall in the VM
                and assert the gate now FAILS (proves the gate isn't a rubber stamp)
  --keep        Don't delete the VM on exit (for debugging a failed run)
  -h, --help    Show this help

Env: VM_SMOKE_IMAGE, VM_SMOKE_USER (default admin), VM_SMOKE_PASS (default admin),
     VM_SMOKE_INSTALL_TIMEOUT (seconds, default 3600).
EOF
}

# Progress logs go to stderr so stdout stays reserved for the verify_install record
# stream that evaluate_stream parses.
log() { printf '\033[1;34m==>\033[0m %s\n' "$*" >&2; }

# is_tolerated MSG — true when a BAD verify record is an expected-in-a-VM failure.
# A headless Tart VM has no Touch ID sensor, so install.sh wires pam_tid but no
# fingerprint can ever enroll; verify_install flags that as BAD. That single case is
# tolerated. Every other BAD — crucially the application firewall — stays strict.
is_tolerated() {
  case "$1" in
  *"NO fingerprint is enrolled"*) return 0 ;;
  *) return 1 ;;
  esac
}

# evaluate_stream — read verify_install's `OK<TAB>msg` / `BAD<TAB>msg` records, plus a
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

  local IMAGE="${VM_SMOKE_IMAGE:-ghcr.io/cirruslabs/macos-sequoia-base:latest}"
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

  # wait_for DESC TIMEOUT CMD... — poll CMD until it succeeds or TIMEOUT seconds elapse.
  wait_for() {
    local desc="$1" timeout="$2" waited=0
    shift 2
    until "$@" >/dev/null 2>&1; do
      if [ "$waited" -ge "$timeout" ]; then
        printf 'vm-smoke.sh: timed out after %ss waiting for %s\n' "$timeout" "$desc" >&2
        return 1
      fi
      sleep 2
      waited=$((waited + 2))
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
    # shellcheck disable=SC2016
    ssh_vm 'cd "$HOME/dotfiles" \
      && rm -f .install.rc .install.log \
      && nohup sh -c "./install.sh --no-bundles --core >.install.log 2>&1; echo \$? >.install.rc" \
           >/dev/null 2>&1 < /dev/null & \
      exit 0'
    log "$label: waiting for install to finish (timeout ${INSTALL_TIMEOUT}s)"
    # shellcheck disable=SC2016
    if ! wait_for "install to finish" "$INSTALL_TIMEOUT" \
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

  # verify_gate LABEL — source verify_install.sh in the VM, capture its OK/BAD stream plus
  # the VERIFY_DONE sentinel, and pipe it through evaluate_stream here. Returns non-zero if
  # any untolerated BAD is present or the stream was truncated. `bash` is forced because the
  # guest login shell may not be bash and verify_install.sh uses bashisms.
  verify_gate() {
    local label="$1"
    log "$label: running verify_install in the VM and evaluating the result"
    ssh_vm 'bash -s' <<'REMOTE' | evaluate_stream
cd "$HOME/dotfiles"
# Match the --core install: verify the casks-stripped baseline, not the full Brewfile.
export DOTFILES_CORE=1
# shellcheck source=/dev/null
source scripts/verify_install.sh
verify_install "$PWD"
printf 'VERIFY_DONE\t%s\n' "$?"
REMOTE
  }

  log "Cloning ${IMAGE} -> ${VM_NAME} (pulls the base image on first run; multi-GB)"
  tart clone "$IMAGE" "$VM_NAME"

  log "Booting ${VM_NAME} headless"
  tart run --no-graphics "$VM_NAME" >"$RUN_LOG" 2>&1 &

  log "Waiting for the VM to acquire an IP"
  if ! wait_for "an IP address" 180 tart ip "$VM_NAME"; then
    log "VM never came up — 'tart run' console log:"
    cat "$RUN_LOG" >&2 || true
    return 1
  fi
  VM_IP="$(tart ip "$VM_NAME")"
  log "VM is up at ${VM_IP}"

  log "Waiting for SSH"
  wait_for "SSH" 180 ssh_vm true

  # install.sh runs sudo repeatedly across a multi-minute install. Crucially its keepalive
  # calls `sudo -v`, which RE-AUTHENTICATES — and NOPASSWD does NOT cover `sudo -v`, so a
  # headless SSH session (no tty) would die at "Privileged setup". Install a sudoers drop-in
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

  if [ "$ONCE" -eq 0 ]; then
    if ! run_install "idempotency re-run (2/2)"; then
      log "Idempotency re-run FAILED — install.sh is not cleanly re-runnable."
      return 1
    fi
    if ! verify_gate "re-verify"; then
      log "Verification FAILED after the idempotency re-run — install.sh is not cleanly re-runnable."
      return 1
    fi
  fi

  if [ "$NEGATIVE" -eq 1 ]; then
    log "Negative self-test: disabling the firewall in the VM; the gate MUST now fail"
    ssh_vm 'sudo -n /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate off' \
      >/dev/null 2>&1 || true
    if verify_gate "negative"; then
      printf 'vm-smoke.sh: NEGATIVE self-test FAILED — the gate passed with the firewall OFF, so it is not actually checking.\n' >&2
      return 1
    fi
    log "Negative self-test PASSED — the gate correctly rejected a broken install."
  fi

  log "Smoke test PASSED — install.sh ran clean and verify_install reported healthy."
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  main "$@"
fi
