#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Unit tests for scripts/vm-smoke.sh — the arg-parsing/preflight contract and the pure
# verify-gate helpers (is_tolerated / evaluate_stream), all of which run without booting a
# VM. The script is written to be sourceable (its main() only runs from the entrypoint
# guard), so these tests source it to exercise the gate logic directly. The actual
# end-to-end VM run (boot, install, verify) is the opt-in pytest integration test
# (tests/test_vm_smoke.py) — it needs a real Tart host and many minutes.
#
# Run:  bats tests/vm_smoke.bats

setup() {
  SCRIPT="$BATS_TEST_DIRNAME/../scripts/vm-smoke.sh"
}

# --- arg parsing + preflight (the script executed) --------------------------

@test "--help prints usage and exits 0" {
  run bash "$SCRIPT" --help
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage: vm-smoke.sh"* ]]
}

@test "an unexpected argument exits 2 with a usage hint" {
  run bash "$SCRIPT" --bogus
  [ "$status" -eq 2 ]
  [[ "$output" == *"unexpected argument"* ]]
}

@test "preflight fails clearly when tart is absent" {
  # tart is a Homebrew tool, never in /usr/bin:/bin — so this PATH guarantees it is missing
  # while leaving the basic tools the script needs available.
  PATH="/usr/bin:/bin" run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"tart not found"* ]]
}

# --- pure gate helpers (the script sourced) ---------------------------------
# Sourcing is inert: vm-smoke.sh only runs main() when executed directly, so these load
# just the function definitions.

@test "is_tolerated matches only the Touch-ID-no-sensor BAD" {
  # shellcheck source=../scripts/vm-smoke.sh disable=SC1091
  source "$SCRIPT"
  run is_tolerated "Touch ID for sudo is enabled but NO fingerprint is enrolled — enroll one"
  [ "$status" -eq 0 ]
  run is_tolerated "application firewall is OFF — enable it"
  [ "$status" -ne 0 ]
}

@test "evaluate_stream passes when every record is OK and the sentinel is present" {
  run bash -c "source '$SCRIPT'; printf 'OK\ta\nOK\tb\nVERIFY_DONE\t0\n' | evaluate_stream"
  [ "$status" -eq 0 ]
}

@test "evaluate_stream tolerates the Touch-ID-no-sensor BAD" {
  run bash -c "source '$SCRIPT'; printf 'OK\ta\nBAD\tTouch ID for sudo is enabled but NO fingerprint is enrolled — x\nVERIFY_DONE\t0\n' | evaluate_stream"
  [ "$status" -eq 0 ]
}

@test "evaluate_stream fails on an untolerated BAD (firewall off)" {
  run bash -c "source '$SCRIPT'; printf 'OK\ta\nBAD\tapplication firewall is OFF — enable it\nVERIFY_DONE\t0\n' | evaluate_stream"
  [ "$status" -ne 0 ]
}

@test "evaluate_stream fails closed when the VERIFY_DONE sentinel is missing (truncated stream)" {
  run bash -c "source '$SCRIPT'; printf 'OK\ta\nOK\tb\n' | evaluate_stream"
  [ "$status" -ne 0 ]
  [[ "$output" == *"sentinel"* ]]
}
