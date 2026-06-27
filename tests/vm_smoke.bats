#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Unit tests for scripts/vm-smoke.sh — the arg-parsing and preflight contract that runs
# before any VM boots. The actual end-to-end VM run (boot, install, verify) is exercised by
# the opt-in pytest integration test (tests/test_vm_smoke.py), not here, since it needs a
# real Tart host and many minutes.
#
# Run:  bats tests/vm_smoke.bats

setup() {
  SCRIPT="$BATS_TEST_DIRNAME/../scripts/vm-smoke.sh"
}

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
