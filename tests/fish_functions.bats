#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Smoke tests for the small fish helper functions. These wrap interactive tools
# (fzf, git, rg) so their happy paths aren't worth driving headless — but their
# guard rails (usage messages, "not a git repo", missing-arg handling) are pure
# logic and cheap to lock down. Each function is sourced into a fresh fish process.
#
# Run:  bats tests/fish_functions.bats

FUNCDIR_REL="../home/.config/fish/functions"

setup() {
  FUNCDIR="$BATS_TEST_DIRNAME/$FUNCDIR_REL"
  NONREPO="$(mktemp -d)"   # a directory that is definitely not a git repo
}

teardown() {
  rm -rf "$NONREPO"
}

# Source one function file and run the function, capturing stdout+stderr+status.
fishrun() {
  local func="$1"; shift
  run fish -c "source '$FUNCDIR/$func.fish'; $func $*"
}

@test "eachdir with no args prints usage and returns 2" {
  fishrun eachdir
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage: eachdir"* ]]
}

@test "forrepos with no args prints usage and returns 2" {
  fishrun forrepos
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage: forrepos"* ]]
}

@test "fsearch with no args prints usage and returns 2" {
  fishrun fsearch
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage: fsearch"* ]]
}

@test "wtfis with no args prints usage and returns 2" {
  fishrun wtfis
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage: wtfis"* ]]
}

@test "pset with no args prints usage and returns 2" {
  fishrun pset
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage: pset"* ]]
}

@test "git_prune_local --help prints usage and returns 0" {
  fishrun git_prune_local --help
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage: git_prune_local"* ]]
}

@test "git_prune_local outside a git repo errors and returns 1" {
  cd "$NONREPO"
  fishrun git_prune_local
  [ "$status" -eq 1 ]
  [[ "$output" == *"Not a git repository"* ]]
}

@test "pubkey on a missing key reports it and returns 1" {
  fishrun pubkey /nonexistent/key.pub
  [ "$status" -eq 1 ]
  [[ "$output" == *"No such key"* ]]
}

@test "launch-docs with a non-numeric port prints usage and returns 2" {
  fishrun launch-docs not-a-port
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage: launch-docs"* ]]
}

@test "launch-docs with an out-of-range port prints usage and returns 2" {
  fishrun launch-docs 99999
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage: launch-docs"* ]]
}
