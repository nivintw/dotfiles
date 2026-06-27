#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# End-to-end installer smoke test: boot a clean Tart VM, run install.sh inside it from
# scratch, and assert the post-install verification passes. This is the one thing the
# unit/config tests can't do — prove the installer works on a genuinely clean machine.
#
# Heavy + opt-in: the first run pulls a multi-GB base image and the full install takes
# many minutes. Run it directly (scripts/vm-smoke.sh) or via the opt-in pytest:
#   DOTFILES_VM_SMOKE=1 uv run pytest -m integration

set -euo pipefail

# Resolve the repo root with builtins only, so --help and the preflight check work even
# under a stripped PATH (the bats tests rely on this).
DOTFILES="$(cd "${BASH_SOURCE[0]%/*}/.." && pwd)"

IMAGE="${VM_SMOKE_IMAGE:-ghcr.io/cirruslabs/macos-sequoia-base:latest}"
VM_USER="${VM_SMOKE_USER:-admin}"
VM_PASS="${VM_SMOKE_PASS:-admin}"
KEEP=0
VM_IP=""

usage() {
  cat <<EOF
Usage: vm-smoke.sh [--image REF] [--keep] [-h|--help]

Boot a clean Tart VM from a base image, run install.sh end-to-end inside it, and verify
the result. Requires tart and sshpass (both in the Brewfile).

  --image REF   Base VM image to clone (default: ${IMAGE})
  --keep        Don't delete the VM on exit (for debugging a failed run)
  -h, --help    Show this help

Env: VM_SMOKE_IMAGE, VM_SMOKE_USER (default admin), VM_SMOKE_PASS (default admin).
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
  --image) IMAGE="${2:?--image needs a value}" && shift 2 ;;
  --image=*) IMAGE="${1#*=}" && shift ;;
  --keep) KEEP=1 && shift ;;
  -h | --help) usage && exit 0 ;;
  *)
    printf 'vm-smoke.sh: unexpected argument: %s\n\n' "$1" >&2
    usage >&2
    exit 2
    ;;
  esac
done

for tool in tart sshpass; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf 'vm-smoke.sh: %s not found on PATH (brew bundle from the Brewfile installs it).\n' \
      "$tool" >&2
    exit 1
  fi
done

VM_NAME="dotfiles-smoke-$$"

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

cleanup() {
  if [ "$KEEP" -eq 1 ]; then
    log "Leaving VM '${VM_NAME}' in place (--keep). Delete with: tart delete ${VM_NAME}"
    return
  fi
  tart stop "$VM_NAME" >/dev/null 2>&1 || true
  tart delete "$VM_NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

ssh_vm() {
  sshpass -p "$VM_PASS" ssh \
    -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR \
    "${VM_USER}@${VM_IP}" "$@"
}

# wait_for DESC TIMEOUT_SECONDS CMD... — poll CMD until it succeeds or the timeout elapses.
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

log "Cloning ${IMAGE} -> ${VM_NAME} (pulls the base image on first run; multi-GB)"
tart clone "$IMAGE" "$VM_NAME"

log "Booting ${VM_NAME} headless with the repo mounted read-only"
tart run --no-graphics --dir="dotfiles:${DOTFILES}:ro" "$VM_NAME" >/dev/null 2>&1 &

log "Waiting for the VM to acquire an IP"
wait_for "an IP address" 180 tart ip "$VM_NAME"
VM_IP="$(tart ip "$VM_NAME")"
log "VM is up at ${VM_IP}"

log "Waiting for SSH"
wait_for "SSH" 180 ssh_vm true

log "Running install.sh end-to-end inside the VM (the slow part)"
# shellcheck disable=SC2016  # intentional: $HOME / paths must expand inside the VM, not here
ssh_vm 'set -euo pipefail
  cp -R "/Volumes/My Shared Files/dotfiles" "$HOME/dotfiles"
  cd "$HOME/dotfiles"
  ./install.sh --no-bundles
  bash scripts/verify_install.sh'

log "Smoke test PASSED — install.sh ran clean and verify_install reported healthy."
