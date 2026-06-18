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

# No argument, no agent identities, and no key files on disk: every discovery
# tier comes up empty, so it must report none found and return 1. An empty HOME
# (no ~/.ssh, no 1Password sockets) plus an empty SSH_AUTH_SOCK forces that state.
@test "pubkey with nothing to discover reports none found and returns 1" {
  empty="$(mktemp -d)"
  run env HOME="$empty" SSH_AUTH_SOCK="" fish -c "source '$FUNCDIR/pubkey.fish'; pubkey"
  rm -rf "$empty"
  [ "$status" -eq 1 ]
  [[ "$output" == *"No SSH keys found"* ]]
}

# An explicitly named but empty file must not copy its path in place of a key
# (the contents are passed as a single collected argument and guarded when empty).
@test "pubkey on an empty key file copies nothing and returns 1" {
  empty_file="$(mktemp)"
  fishrun pubkey "$empty_file"
  rm -f "$empty_file"
  [ "$status" -eq 1 ]
  [[ "$output" == *"no key to copy"* ]]
}

# A directory (or dangling symlink) named *.pub in ~/.ssh must be ignored by the
# disk fallback (-type f), not offered as a key.
@test "pubkey ignores a directory named *.pub and reports none found" {
  empty="$(mktemp -d)"
  mkdir -p "$empty/.ssh/decoy.pub"
  run env HOME="$empty" SSH_AUTH_SOCK="" fish -c "source '$FUNCDIR/pubkey.fish'; pubkey"
  rm -rf "$empty"
  [ "$status" -eq 1 ]
  [[ "$output" == *"No SSH keys found"* ]]
}

# Happy path: a single key in the agent is printed and copied with no picker.
# Needs a real agent + clipboard, so it skips where those are absent (e.g. the
# Linux CI box has no pbcopy). The multi-key picker path blocks on fzf and is
# verified manually, per this file's header.
@test "pubkey with one agent key prints and copies it" {
  command -v ssh-agent >/dev/null || skip "no ssh-agent"
  command -v ssh-keygen >/dev/null || skip "no ssh-keygen"
  command -v pbcopy >/dev/null || skip "no pbcopy"
  tmp="$(mktemp -d)"
  ssh-keygen -t ed25519 -N "" -C "Bats Test Key" -f "$tmp/k" >/dev/null
  eval "$(ssh-agent -s)" >/dev/null
  ssh-add "$tmp/k" 2>/dev/null
  run fish -c "source '$FUNCDIR/pubkey.fish'; pubkey"
  ssh-agent -k >/dev/null 2>&1
  rm -rf "$tmp"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Bats Test Key"* ]]
  [[ "$output" == *"copied to clipboard"* ]]
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

# The fuzzy git-checkout helpers all bail before touching fzf when run outside a
# git repo. Same guard, three functions — lock each one down.
@test "fco outside a git repo errors and returns 1" {
  cd "$NONREPO"
  fishrun fco
  [ "$status" -eq 1 ]
  [[ "$output" == *"Not a git repository"* ]]
}

@test "fcor outside a git repo errors and returns 1" {
  cd "$NONREPO"
  fishrun fcor
  [ "$status" -eq 1 ]
  [[ "$output" == *"Not a git repository"* ]]
}

@test "gcor outside a git repo errors and returns 1" {
  cd "$NONREPO"
  fishrun gcor
  [ "$status" -eq 1 ]
  [[ "$output" == *"Not a git repository"* ]]
}

@test "gccd with no args prints usage and returns 2" {
  fishrun gccd
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage: gccd"* ]]
}

@test "fkill with an invalid signal is rejected before touching fzf, returns 2" {
  fishrun fkill not-a-signal
  [ "$status" -eq 2 ]
  [[ "$output" == *"invalid signal"* ]]
}

@test "pyclean --dry-run lists caches without deleting them" {
  tmp="$(mktemp -d)"
  mkdir -p "$tmp/__pycache__"
  touch "$tmp/__pycache__/foo.cpython-314.pyc"
  cd "$tmp"
  fishrun pyclean -n
  [ "$status" -eq 0 ]
  [[ "$output" == *"dry run"* ]]
  [ -d "$tmp/__pycache__" ]  # the cache dir must survive a dry run
  rm -rf "$tmp"
}

# The real (non-dry-run) path must delete the caches and ONLY the caches.
@test "pyclean deletes caches but leaves real files intact" {
  tmp="$(mktemp -d)"
  mkdir -p "$tmp/__pycache__" "$tmp/.ruff_cache"
  touch "$tmp/__pycache__/foo.cpython-314.pyc" "$tmp/stray.pyc" "$tmp/keep.py"
  cd "$tmp"
  fishrun pyclean
  [ "$status" -eq 0 ]
  [[ "$output" == *"Python caches cleaned"* ]]
  [ ! -d "$tmp/__pycache__" ]
  [ ! -d "$tmp/.ruff_cache" ]
  [ ! -f "$tmp/stray.pyc" ]
  [ -f "$tmp/keep.py" ] # a real source file must survive
  rm -rf "$tmp"
}

# With no repo, no $DOTFILES, and no ~/dotfiles under an overridden HOME, the
# docs dir can't be resolved — it must report that rather than serve the wrong tree.
@test "launch-docs reports a missing docs dir when none can be resolved" {
  run env HOME="$NONREPO" DOTFILES="" fish -c "cd '$NONREPO'; source '$FUNCDIR/launch-docs.fish'; launch-docs"
  [ "$status" -eq 1 ]
  [[ "$output" == *"docs site not found"* ]]
}
