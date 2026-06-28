#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Tests for the pure helpers in uninstall.sh — the parsing/matching logic the
# reversal decisions hang on. The host-mutating tiers (stow -D, claude mcp remove,
# uv tool uninstall, chsh, sudo rm) read and change live machine state and aren't
# unit-testable in isolation; they ride on shellcheck + the closing summary's
# transparency. These tests pin the bits that are easy to get subtly wrong: deriving
# a uv tool name (extras stripped), deciding whether a sudo_local PAM file is one we
# wrote (so we never delete someone else's), and enumerating merged MCP server names.
#
# Run:  bats tests/uninstall.bats

setup() {
  LIB="$BATS_TEST_DIRNAME/../uninstall.sh"
  # shellcheck source=../uninstall.sh disable=SC1091
  . "$LIB"
  TMP="$(mktemp -d)"
}

teardown() {
  rm -rf "$TMP"
}

# --- un_uv_tool_name --------------------------------------------------------

@test "un_uv_tool_name: plain name passes through" {
  run un_uv_tool_name "rumdl"
  [ "$status" -eq 0 ]
  [ "$output" = "rumdl" ]
}

@test "un_uv_tool_name: strips trailing [extras]" {
  run un_uv_tool_name "reuse[charset-normalizer]"
  [ "$output" = "reuse" ]
}

@test "un_uv_tool_name: keeps only the first token when there are --with args" {
  run un_uv_tool_name "ansible --with passlib --with jc --with jmespath"
  [ "$output" = "ansible" ]
}

@test "un_uv_tool_name: blank line yields nothing" {
  run un_uv_tool_name ""
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "un_uv_tool_name: comment line yields nothing" {
  run un_uv_tool_name "# a comment"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# --- un_pam_is_ours ---------------------------------------------------------

@test "un_pam_is_ours: the bare pam_tid form is ours" {
  run un_pam_is_ours "auth       sufficient     pam_tid.so"
  [ "$status" -eq 0 ]
}

@test "un_pam_is_ours: the pam_reattach + pam_tid form is ours (any brew prefix)" {
  content=$'auth       optional       /opt/homebrew/lib/pam/pam_reattach.so\nauth       sufficient     pam_tid.so'
  run un_pam_is_ours "$content"
  [ "$status" -eq 0 ]
}

@test "un_pam_is_ours: an Intel-prefix pam_reattach path is still ours" {
  content=$'auth       optional       /usr/local/lib/pam/pam_reattach.so\nauth       sufficient     pam_tid.so'
  run un_pam_is_ours "$content"
  [ "$status" -eq 0 ]
}

@test "un_pam_is_ours: a file with an extra unknown line is NOT ours" {
  content=$'auth       sufficient     pam_tid.so\nauth       required       pam_deny.so'
  run un_pam_is_ours "$content"
  [ "$status" -ne 0 ]
}

@test "un_pam_is_ours: pam_reattach alone (no pam_tid) is NOT ours" {
  run un_pam_is_ours "auth       optional       /opt/homebrew/lib/pam/pam_reattach.so"
  [ "$status" -ne 0 ]
}

@test "un_pam_is_ours: an unrelated MDM-style file is NOT ours" {
  run un_pam_is_ours "auth       sufficient     pam_some_mdm.so"
  [ "$status" -ne 0 ]
}

# --- un_mcp_names -----------------------------------------------------------

@test "un_mcp_names: lists baseline server names when no overlay" {
  printf '%s\n' '{"github":{},"serena":{}}' >"$TMP/base.json"
  run un_mcp_names "$TMP/base.json"
  [ "$status" -eq 0 ]
  [[ "$output" == *github* ]]
  [[ "$output" == *serena* ]]
}

@test "un_mcp_names: merges overlay-added servers" {
  printf '%s\n' '{"github":{}}' >"$TMP/base.json"
  printf '%s\n' '{"extra":{}}' >"$TMP/overlay.json"
  run un_mcp_names "$TMP/base.json" "$TMP/overlay.json"
  [[ "$output" == *github* ]]
  [[ "$output" == *extra* ]]
}

@test "un_mcp_names: ignores an invalid-JSON overlay (baseline only)" {
  printf '%s\n' '{"github":{}}' >"$TMP/base.json"
  printf '%s\n' 'not json' >"$TMP/overlay.json"
  run un_mcp_names "$TMP/base.json" "$TMP/overlay.json"
  [ "$status" -eq 0 ]
  [[ "$output" == *github* ]]
}

# --- un_is_yes --------------------------------------------------------------

@test "un_is_yes: accepts y / Y / yes / YES" {
  for a in y Y yes YES Yes; do
    run un_is_yes "$a"
    [ "$status" -eq 0 ]
  done
}

@test "un_is_yes: rejects empty, n, and anything else" {
  for a in "" n N no nope maybe q; do
    run un_is_yes "$a"
    [ "$status" -ne 0 ]
  done
}
