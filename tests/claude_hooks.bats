#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Behavior tests for the repo-local Claude Code hook scripts under .claude/hooks/.
# Each hook reads a tool-call JSON object on stdin and signals via exit code
# (0 = allow / clean, 2 = block / findings). These tests cover each script's own
# guard logic; the slow ty-invocation path of typecheck-touched.sh is delegation
# to `uv run ty check .` (the same command the prek `ty` hook runs) and is
# exercised by a manual run rather than re-tested here.
#
# Run:  bats tests/claude_hooks.bats

setup() {
  HOOKS="$BATS_TEST_DIRNAME/../.claude/hooks"
  GUARD="$HOOKS/guard-managed-files.sh"
  LINT="$HOOKS/lint-edited-file.sh"
  TYPECHECK="$HOOKS/typecheck-touched.sh"
  WORK="$(mktemp -d)"
}

teardown() {
  rm -rf "$WORK"
}

# Feed a JSON payload on stdin to a hook; populates $status and $output.
feed() { # $1 = script path, $2 = JSON payload
  run bash -c "printf '%s' '$2' | '$1'"
}

# --- guard-managed-files.sh: blocks tool-owned files -----------------------

@test "guard blocks uv.lock" {
  feed "$GUARD" '{"tool_input":{"file_path":"/repo/uv.lock"}}'
  [ "$status" -eq 2 ]
  [[ "$output" == *"lockfile"* ]]
}

@test "guard blocks CHANGELOG.md" {
  feed "$GUARD" '{"tool_input":{"file_path":"/repo/CHANGELOG.md"}}'
  [ "$status" -eq 2 ]
  [[ "$output" == *"commitizen"* ]]
}

@test "guard blocks files under LICENSES/" {
  feed "$GUARD" '{"tool_input":{"file_path":"/repo/LICENSES/MIT.txt"}}'
  [ "$status" -eq 2 ]
  [[ "$output" == *"REUSE"* ]]
}

@test "guard blocks the iterm2 plist" {
  feed "$GUARD" '{"tool_input":{"file_path":"/repo/iterm2/com.googlecode.iterm2.plist"}}'
  [ "$status" -eq 2 ]
  [[ "$output" == *"iTerm2"* ]]
}

@test "guard allows a normal file" {
  feed "$GUARD" '{"tool_input":{"file_path":"/repo/README.md"}}'
  [ "$status" -eq 0 ]
}

@test "guard is a no-op when no file_path is present" {
  feed "$GUARD" '{}'
  [ "$status" -eq 0 ]
}

# --- lint-edited-file.sh: lints the touched file by extension --------------
# CLAUDE_PROJECT_DIR points at a config-free temp dir so ruff uses its defaults
# (E + F), keeping these assertions independent of the repo's strict ruleset.

@test "lint flags a Python file with a violation (exit 2)" {
  printf 'import os\n' > "$WORK/bad.py" # F401 unused import
  run bash -c "printf '%s' '{\"tool_input\":{\"file_path\":\"$WORK/bad.py\"}}' | CLAUDE_PROJECT_DIR='$WORK' '$LINT'"
  [ "$status" -eq 2 ]
  [[ "$output" == *"Lint findings"* ]]
}

@test "lint passes a clean Python file (exit 0)" {
  printf 'x = 1\n' > "$WORK/clean.py"
  run bash -c "printf '%s' '{\"tool_input\":{\"file_path\":\"$WORK/clean.py\"}}' | CLAUDE_PROJECT_DIR='$WORK' '$LINT'"
  [ "$status" -eq 0 ]
}

@test "lint ignores an unhandled extension (exit 0)" {
  printf 'hello\n' > "$WORK/notes.txt"
  feed "$LINT" "{\"tool_input\":{\"file_path\":\"$WORK/notes.txt\"}}"
  [ "$status" -eq 0 ]
}

@test "lint is a no-op for a nonexistent file" {
  feed "$LINT" "{\"tool_input\":{\"file_path\":\"$WORK/missing.py\"}}"
  [ "$status" -eq 0 ]
}

@test "lint skips a check whose tool is missing (no phantom finding)" {
  # Restrict PATH to just the essentials (bash/cat/jq) so the linters are absent:
  # a missing ruff must be skipped with a warning, not reported as a lint finding.
  mkdir "$WORK/bin"
  ln -s "$(command -v bash)" "$WORK/bin/bash"
  ln -s "$(command -v cat)" "$WORK/bin/cat"
  ln -s "$(command -v jq)" "$WORK/bin/jq"
  printf 'import os\n' > "$WORK/x.py"
  run bash -c "printf '%s' '{\"tool_input\":{\"file_path\":\"$WORK/x.py\"}}' | PATH='$WORK/bin' CLAUDE_PROJECT_DIR='$WORK' '$LINT'"
  [ "$status" -eq 0 ]
}

# --- typecheck-touched.sh: whole-project ty at Stop, guarded ---------------

@test "typecheck skips a turn it triggered itself (stop_hook_active)" {
  feed "$TYPECHECK" '{"stop_hook_active":true}'
  [ "$status" -eq 0 ]
}

@test "typecheck skips when there are no Python changes" {
  git -C "$WORK" init -q
  git -C "$WORK" -c user.email=t@e.st -c user.name=t commit -q --allow-empty -m init
  printf 'notes\n' > "$WORK/readme.txt" # a non-Python change
  run bash -c "printf '%s' '{}' | CLAUDE_PROJECT_DIR='$WORK' '$TYPECHECK'"
  [ "$status" -eq 0 ]
}

@test "typecheck surfaces a git failure instead of silently skipping" {
  # $WORK is not a git repo, so the git query fails — exit 1, not a silent 0.
  run bash -c "printf '%s' '{}' | CLAUDE_PROJECT_DIR='$WORK' '$TYPECHECK'"
  [ "$status" -eq 1 ]
}
