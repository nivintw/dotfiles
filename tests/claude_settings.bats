#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Tests for the Claude Code settings merge helpers (scripts/claude_settings_merge.sh)
# that install.sh sources to generate ~/.claude/settings.json from the tracked
# claude_settings.json baseline plus an untracked machine-local overlay.
#
# The risk these guard: merge and diff are duals — diff must extract exactly the
# machine-local drift, and merge(baseline; that delta) must reproduce the live
# file (set-wise for arrays). A silent drift between the two would either drop a
# machine's accrued prefs or fail to apply them — the "works on my machine" class
# the suite exists to catch. Arrays must UNION (a machine adds one permission/hook
# without clobbering the baseline list), not replace — so that's pinned explicitly.
#
# Run:  bats tests/claude_settings.bats

setup() {
  LIB="$BATS_TEST_DIRNAME/../scripts/claude_settings_merge.sh"
  # shellcheck source=../scripts/claude_settings_merge.sh disable=SC1091
  . "$LIB"

  BASE='{
    "permissions": { "allow": ["Bash(git *)", "Read"], "deny": [] },
    "theme": "dark",
    "hooks": { "PreToolUse": [ { "matcher": "Bash", "hooks": [ { "type": "command", "command": "shared.sh" } ] } ] }
  }'
}

# Normalize for set-wise comparison: arrays are unioned in baseline-then-extras
# order, which need not match the live file's order, so sort every array before
# comparing. Object key order is already normalized by jq -S.
norm() {
  jq -S 'walk(if type == "array" then sort else . end)'
}

# assert_roundtrip CUR -- merge(BASE; diff(BASE; CUR)) reproduces CUR set-wise.
assert_roundtrip() {
  local cur="$1" delta merged a b
  delta="$(claude_settings_diff "$BASE" "$cur")"
  merged="$(claude_settings_merge "$BASE" "$delta")"
  a="$(printf '%s' "$merged" | norm)"
  b="$(printf '%s' "$cur" | norm)"
  [ "$a" = "$b" ]
}

@test "changed scalar round-trips" {
  assert_roundtrip '{
    "permissions": { "allow": ["Bash(git *)", "Read"], "deny": [] },
    "theme": "light",
    "hooks": { "PreToolUse": [ { "matcher": "Bash", "hooks": [ { "type": "command", "command": "shared.sh" } ] } ] }
  }'
}

@test "new top-level key round-trips" {
  assert_roundtrip '{
    "permissions": { "allow": ["Bash(git *)", "Read"], "deny": [] },
    "theme": "dark",
    "effortLevel": "high",
    "hooks": { "PreToolUse": [ { "matcher": "Bash", "hooks": [ { "type": "command", "command": "shared.sh" } ] } ] }
  }'
}

@test "new nested key round-trips" {
  assert_roundtrip '{
    "permissions": { "allow": ["Bash(git *)", "Read"], "deny": [], "defaultMode": "default" },
    "theme": "dark",
    "hooks": { "PreToolUse": [ { "matcher": "Bash", "hooks": [ { "type": "command", "command": "shared.sh" } ] } ] }
  }'
}

@test "an added permission UNIONS with the baseline, not replaces it" {
  local cur delta
  cur='{
    "permissions": { "allow": ["Bash(git *)", "Read", "Bash(kubectl *)"], "deny": [] },
    "theme": "dark",
    "hooks": { "PreToolUse": [ { "matcher": "Bash", "hooks": [ { "type": "command", "command": "shared.sh" } ] } ] }
  }'
  # The delta carries ONLY the machine-specific permission, not the whole array.
  delta="$(claude_settings_diff "$BASE" "$cur")"
  run jq -c '.permissions.allow' <<<"$delta"
  [ "$output" = '["Bash(kubectl *)"]' ]
  # ...and the merge reproduces the full unioned list.
  assert_roundtrip "$cur"
}

@test "an added hook block merges alongside the baseline hooks" {
  local cur delta
  cur='{
    "permissions": { "allow": ["Bash(git *)", "Read"], "deny": [] },
    "theme": "dark",
    "hooks": { "PreToolUse": [
      { "matcher": "Bash", "hooks": [ { "type": "command", "command": "shared.sh" } ] },
      { "matcher": "Write", "hooks": [ { "type": "command", "command": "local.sh" } ] }
    ] }
  }'
  delta="$(claude_settings_diff "$BASE" "$cur")"
  # Only the machine-local Write hook is extracted.
  run jq -c '.hooks.PreToolUse' <<<"$delta"
  [ "$output" = '[{"matcher":"Write","hooks":[{"type":"command","command":"local.sh"}]}]' ]
  assert_roundtrip "$cur"
}

@test "overlay is stable across runs (idempotent)" {
  # current = merge(baseline; overlay); next run's delta must equal the overlay.
  local overlay current delta a b
  overlay='{ "theme": "light", "permissions": { "allow": ["Bash(kubectl *)"] } }'
  current="$(claude_settings_merge "$BASE" "$overlay")"
  delta="$(claude_settings_diff "$BASE" "$current")"
  a="$(printf '%s' "$delta" | norm)"
  b="$(printf '%s' "$overlay" | norm)"
  [ "$a" = "$b" ]
}

@test "removing a baseline permission is NOT expressible via the overlay" {
  # Documented limitation: arrays union, they never delete. A live file missing a
  # baseline permission yields an empty delta, and the merge re-adds it.
  local cur delta merged
  cur='{
    "permissions": { "allow": ["Read"], "deny": [] },
    "theme": "dark",
    "hooks": { "PreToolUse": [ { "matcher": "Bash", "hooks": [ { "type": "command", "command": "shared.sh" } ] } ] }
  }'
  delta="$(claude_settings_diff "$BASE" "$cur")"
  run jq -c '.' <<<"$delta"
  [ "$output" = '{}' ]
  merged="$(claude_settings_merge "$BASE" "$delta")"
  run jq -c '.permissions.allow' <<<"$merged"
  [ "$output" = '["Bash(git *)","Read"]' ]
}

@test "an empty overlay reproduces the baseline exactly" {
  local merged a b
  merged="$(claude_settings_merge "$BASE" '{}')"
  a="$(printf '%s' "$merged" | norm)"
  b="$(printf '%s' "$BASE" | norm)"
  [ "$a" = "$b" ]
}
