#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Unit tests for scripts/brewfile_core.sh — the pure filter that yields a Brewfile's CLI-only
# "core" subset (taps + formulae, casks stripped) for the --core install profile. No brew, no
# network: text in, filtered text out.
#
# Run:  bats tests/brewfile_core.bats

setup() {
  LIB="$BATS_TEST_DIRNAME/../scripts/brewfile_core.sh"
  # shellcheck source=../scripts/brewfile_core.sh disable=SC1091
  source "$LIB"
  BREWFILE="$BATS_TEST_TMPDIR/Brewfile"
}

@test "keeps tap and brew lines, drops cask lines" {
  printf 'tap "owner/name"\nbrew "git"\ncask "firefox"\nbrew "fish"\ncask "obsidian"\n' >"$BREWFILE"
  run brewfile_core "$BREWFILE"
  [ "$status" -eq 0 ]
  [[ "$output" == *'tap "owner/name"'* ]]
  [[ "$output" == *'brew "git"'* ]]
  [[ "$output" == *'brew "fish"'* ]]
  [[ "$output" != *"firefox"* ]]
  [[ "$output" != *"obsidian"* ]]
}

@test "preserves comments and trailing inline comments on kept lines" {
  printf '# Formulae\nbrew "jq"   # json tool\ncask "iterm2"  # terminal\n' >"$BREWFILE"
  run brewfile_core "$BREWFILE"
  [ "$status" -eq 0 ]
  [[ "$output" == *"# Formulae"* ]]
  [[ "$output" == *'brew "jq"   # json tool'* ]]
  [[ "$output" != *"iterm2"* ]]
}

@test "drops an indented cask line too" {
  printf '  cask "rancher"\nbrew "btop"\n' >"$BREWFILE"
  run brewfile_core "$BREWFILE"
  [ "$status" -eq 0 ]
  [[ "$output" != *"rancher"* ]]
  [[ "$output" == *'brew "btop"'* ]]
}

@test "a Brewfile with no casks is returned unchanged" {
  printf 'tap "a/b"\nbrew "git"\nbrew "fish"\n' >"$BREWFILE"
  run brewfile_core "$BREWFILE"
  [ "$status" -eq 0 ]
  [ "${lines[0]}" = 'tap "a/b"' ]
  [ "${lines[1]}" = 'brew "git"' ]
  [ "${lines[2]}" = 'brew "fish"' ]
}

@test "a missing Brewfile is not an error (no output, exit 0)" {
  run brewfile_core "$BATS_TEST_TMPDIR/nope"
  [ "$status" -eq 0 ]
  [ "$output" = "" ]
}
