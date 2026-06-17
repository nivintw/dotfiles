#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Behavior tests for scripts/check-ssh-config.sh — the pre-commit guard that keeps
# the *tracked* ~/.ssh/config generic (the docs' "tested both ways" claim). The
# script reads the relative path home/.ssh/config, so each test builds a throwaway
# tree, writes a config into it, and runs the guard from that tree's root.
#
# Run:  bats tests/check_ssh_config.bats

setup() {
  SCRIPT="$BATS_TEST_DIRNAME/../scripts/check-ssh-config.sh"
  WORK="$(mktemp -d)"
  mkdir -p "$WORK/home/.ssh"
}

teardown() {
  rm -rf "$WORK"
}

# Write $1 as the config, then run the guard from the throwaway tree root.
check() {
  printf '%s\n' "$1" > "$WORK/home/.ssh/config"
  run bash -c "cd '$WORK' && '$SCRIPT'"
}

@test "generic config (Host *, Include, github.com, globals) passes" {
  check 'Host *
    AddKeysToAgent yes
    IdentityAgent "~/.1password/agent.sock"

Include ~/.ssh/config.local

Host github.com'
  [ "$status" -eq 0 ]
}

@test "missing config is a no-op (exit 0)" {
  rm -rf "$WORK/home/.ssh/config"
  run bash -c "cd '$WORK' && '$SCRIPT'"
  [ "$status" -eq 0 ]
}

@test "a concrete Host pattern fails the commit" {
  check 'Host myserver
    HostName box.internal'
  [ "$status" -eq 1 ]
  [[ "$output" == *"concrete Host pattern"* ]]
}

@test "a HostName directive fails the commit" {
  check 'Host *
    HostName prod.example.com'
  [ "$status" -eq 1 ]
  [[ "$output" == *"machine-specific directive"* ]]
}

@test "a User directive fails the commit" {
  check 'Host *
    User alice'
  [ "$status" -eq 1 ]
  [[ "$output" == *"machine-specific directive"* ]]
}

@test "a bare IP literal fails the commit" {
  check 'Host *
    ProxyJump 10.0.0.1'
  [ "$status" -eq 1 ]
  [[ "$output" == *"IP literal"* ]]
}
