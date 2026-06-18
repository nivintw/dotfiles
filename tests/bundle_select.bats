#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Tests for the opt-in Brewfile bundle selection helpers (scripts/bundle_select.sh)
# that the bootstrap script sources. The risk these guard: write_bundles and parse_bundles
# are inverses — the parser must read back exactly the names the writer wrote,
# ignoring the self-documenting header. A silent drift (e.g. changing the comment
# prefix the parser skips) would mean a selection that round-trips fine on the
# author's machine installs the wrong set elsewhere — the "works on my machine"
# class the suite exists to catch.
#
# Run:  bats tests/bundle_select.bats

setup() {
  LIB="$BATS_TEST_DIRNAME/../scripts/bundle_select.sh"
  # SC1091: the lib is resolved at runtime via $BATS_TEST_DIRNAME; shellcheck runs
  # without -x so it can't follow it statically. source= keeps editors/`-x` happy.
  # shellcheck source=../scripts/bundle_select.sh disable=SC1091
  . "$LIB"
  TMP="$(mktemp -d)"
  SEL="$TMP/bundles"
}

teardown() {
  rm -rf "$TMP"
}

@test "write_bundles then parse_bundles round-trips the chosen names" {
  write_bundles "$SEL" personal homelab work -- personal work
  run parse_bundles "$SEL"
  [ "$status" -eq 0 ]
  [ "${lines[0]}" = "personal" ]
  [ "${lines[1]}" = "work" ]
  [ "${#lines[@]}" -eq 2 ]
}

@test "an empty selection (baseline only) parses to nothing" {
  write_bundles "$SEL" personal homelab --
  run parse_bundles "$SEL"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "the written file documents the available bundles as comments" {
  write_bundles "$SEL" personal homelab -- personal
  # Every available bundle appears as a commented hint...
  grep -q '^#   personal$' "$SEL"
  grep -q '^#   homelab$' "$SEL"
  # ...and the lone bare (non-comment) line is the one chosen name.
  run grep -vE '^(#|$)' "$SEL"
  [ "${#lines[@]}" -eq 1 ]
  [ "${lines[0]}" = "personal" ]
}

@test "parse_bundles ignores comments and blank lines in a hand-edited file" {
  cat > "$SEL" <<'EOF'
# a comment
#   personal

homelab
EOF
  run parse_bundles "$SEL"
  [ "$status" -eq 0 ]
  [ "${#lines[@]}" -eq 1 ]
  [ "${lines[0]}" = "homelab" ]
}

@test "a bundle name with a space survives the round-trip" {
  write_bundles "$SEL" "my bundle" other -- "my bundle"
  run parse_bundles "$SEL"
  [ "$status" -eq 0 ]
  [ "${#lines[@]}" -eq 1 ]
  [ "${lines[0]}" = "my bundle" ]
}

@test "fzf_preselect_bind maps chosen names to 1-based menu positions" {
  run fzf_preselect_bind personal homelab work -- personal work
  [ "$status" -eq 0 ]
  [ "$output" = "start:pos(1)+select+pos(3)+select" ]
}

@test "fzf_preselect_bind emits nothing when nothing is chosen" {
  run fzf_preselect_bind personal homelab --
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "fzf_preselect_bind skips chosen names absent from the menu" {
  run fzf_preselect_bind personal homelab -- ghost personal
  [ "$status" -eq 0 ]
  [ "$output" = "start:pos(1)+select" ]
}
