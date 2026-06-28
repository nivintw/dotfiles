#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Unit tests for scripts/brewfile_taps.sh — the pure Brewfile tap parser install.sh uses to
# trust third-party taps before bundling. No brew, no network: just text in, tap names out.
#
# Run:  bats tests/brewfile_taps.bats

setup() {
  LIB="$BATS_TEST_DIRNAME/../scripts/brewfile_taps.sh"
  # shellcheck source=../scripts/brewfile_taps.sh disable=SC1091
  source "$LIB"
  BREWFILE="$BATS_TEST_TMPDIR/Brewfile"
}

@test "emits the first quoted arg of each tap line" {
  printf 'tap "owner/one"\ntap "owner/two"\n' >"$BREWFILE"
  run brewfile_taps "$BREWFILE"
  [ "$status" -eq 0 ]
  [ "${lines[0]}" = "owner/one" ]
  [ "${lines[1]}" = "owner/two" ]
}

@test "ignores a trailing comment" {
  printf 'tap "owner/name"   # source for some cask\n' >"$BREWFILE"
  run brewfile_taps "$BREWFILE"
  [ "$status" -eq 0 ]
  [ "$output" = "owner/name" ]
}

@test "takes only the tap name, not an explicit clone URL second arg" {
  printf 'tap "owner/name", "https://example.com/owner/homebrew-name.git"\n' >"$BREWFILE"
  run brewfile_taps "$BREWFILE"
  [ "$status" -eq 0 ]
  [ "$output" = "owner/name" ]
}

@test "skips commented-out tap lines" {
  printf '# tap "owner/disabled"\ntap "owner/active"\n' >"$BREWFILE"
  run brewfile_taps "$BREWFILE"
  [ "$status" -eq 0 ]
  [ "$output" = "owner/active" ]
}

@test "ignores brew/cask lines and other directives" {
  printf 'brew "git"\ncask "firefox"\ntap "owner/name"\n' >"$BREWFILE"
  run brewfile_taps "$BREWFILE"
  [ "$status" -eq 0 ]
  [ "$output" = "owner/name" ]
}

@test "emits nothing for a Brewfile with no taps" {
  printf 'brew "git"\nbrew "fish"\n' >"$BREWFILE"
  run brewfile_taps "$BREWFILE"
  [ "$status" -eq 0 ]
  [ "$output" = "" ]
}

@test "a missing Brewfile is not an error (no output, exit 0)" {
  run brewfile_taps "$BATS_TEST_TMPDIR/does-not-exist"
  [ "$status" -eq 0 ]
  [ "$output" = "" ]
}
