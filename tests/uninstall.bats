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

# Tests set run-state globals (DRY_RUN, ASSUME_YES) that the sourced uninstall.sh functions
# read; shellcheck lints this file without following the source, so it can't see those uses.
# shellcheck disable=SC2034

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

@test "un_uv_tool_name: strips a PEP 508 direct-reference @url suffix" {
  run un_uv_tool_name "serena-agent@git+https://github.com/oraios/serena@abc123"
  [ "$output" = "serena-agent" ]
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

# --- do_or_echo / offer: the safety-contract control flow -------------------
# These pin the headline guarantees: dry-run mutates nothing, a failed reversal is
# recorded (not silently dropped), and offers default to no under --dry-run / --yes.
# Called directly (not via `run`) where a ledger mutation must persist in the test shell.

@test "do_or_echo: --dry-run announces and executes nothing" {
  DRY_RUN=1 REMOVED=() FAILED=()
  do_or_echo "create sentinel" touch "$TMP/sentinel" >/dev/null
  [ ! -e "$TMP/sentinel" ]
  [ "${#REMOVED[@]}" -eq 0 ]
  [ "${#FAILED[@]}" -eq 0 ]
}

@test "do_or_echo: real success records REMOVED, not FAILED" {
  DRY_RUN=0 REMOVED=() FAILED=()
  do_or_echo "noop" true >/dev/null
  [ "${#REMOVED[@]}" -eq 1 ]
  [ "${#FAILED[@]}" -eq 0 ]
}

@test "do_or_echo: real failure records FAILED, not REMOVED (never silently dropped)" {
  DRY_RUN=0 REMOVED=() FAILED=()
  do_or_echo "boom" false >/dev/null 2>&1
  [ "${#REMOVED[@]}" -eq 0 ]
  [ "${#FAILED[@]}" -eq 1 ]
}

@test "offer: returns no in --dry-run (announces, never prompts)" {
  DRY_RUN=1 ASSUME_YES=0
  run offer "do the thing?"
  [ "$status" -ne 0 ]
}

@test "offer: returns no under --yes (the safe default for offers)" {
  DRY_RUN=0 ASSUME_YES=1
  run offer "do the thing?"
  [ "$status" -ne 0 ]
}

# --- tier2_ollama_models ------------------------------------------------------------
# The one host-mutating tier that IS worth pinning: the ${VAR:-} guards around each role
# variable in the removal loop, and the unquoted OLLAMA_LEGACY_MODELS expansion that folds
# retired tags into the same offer. Each test runs tier2_ollama_models in a fresh `bash -c`
# subshell (not the shared setup()/test process) so `set -uo pipefail` can be turned on
# without risking bats' own harness code, which shares that process. `offer` is spied —
# redefined to record its question and decline — after sourcing, so each test can assert
# exactly which models were candidates for removal without needing an interactive y/N
# answer. `ollama`/`curl` are stubbed on a PATH prepended in front of the ambient one (only
# those two commands need faking; everything else resolves normally).

# fragment_path DIR — DIR/scripts/<the real shared model-tags fragment's filename>, for a
# throwaway fixture tree (tier2_ollama_models hardcodes that path under $DOTFILES, so the
# fixture file must sit there for `. "$DOTFILES/scripts/..."` to find it). The filename is
# built via concatenation rather than spelled out verbatim, so the coverage gate's
# literal-token scan (tests/test_coverage.py) can't mistake this fixture for real coverage
# of the fragment — the same gotcha tests/ollm.bats's header comment documents.
fragment_path() {
  printf '%s/scripts/%s\n' "$1" "ollama_model""s.sh"
}

# write_tier2_stubs BIN LIST_FILE — populate BIN with an `ollama` stub whose `list`
# subcommand cats LIST_FILE (a header line + one row per "installed" model) and whose `rm`
# always succeeds, plus a `curl` stub that always exits 0 (simulating a running server).
# The data file's path is baked in at stub-generation time, mirroring write_curl_stub in
# tests/ollm.bats.
write_tier2_stubs() {
  local bin="$1" list_file="$2"
  mkdir -p "$bin"
  cat >"$bin/ollama" <<EOF
#!/bin/sh
case "\$1" in
list) cat "$list_file" ;;
rm) exit 0 ;;
*) exit 1 ;;
esac
EOF
  chmod +x "$bin/ollama"
  printf '#!/bin/sh\nexit 0\n' >"$bin/curl"
  chmod +x "$bin/curl"
}

@test "tier2_ollama_models: a fragment missing the three newer vars doesn't abort under set -u; only the defined model is considered" {
  mkdir -p "$TMP/dotfiles/scripts"
  printf 'OLLAMA_MODEL="fast-fake:1"\n' >"$(fragment_path "$TMP/dotfiles")"
  BIN="$TMP/bin"
  LIST_FILE="$TMP/list.txt"
  printf 'NAME  ID  SIZE  MODIFIED\nfast-fake:1  x  1B  now\n' >"$LIST_FILE"
  write_tier2_stubs "$BIN" "$LIST_FILE"

  # shellcheck disable=SC2016  # $TEST_LIB/$TEST_DOTFILES/etc must expand in the inner bash, not here
  run env PATH="$BIN:$PATH" TEST_LIB="$LIB" TEST_DOTFILES="$TMP/dotfiles" bash -c '
    set -uo pipefail
    . "$TEST_LIB"
    DOTFILES="$TEST_DOTFILES"
    DRY_RUN=0 ASSUME_YES=0 REMOVED=() DECLINED=() LEFT=() MANUAL=() FAILED=()
    OFFERED=()
    offer() { OFFERED+=("$1"); return 1; }
    tier2_ollama_models
    [ "${#OFFERED[@]}" -eq 0 ] || printf "OFFERED:%s\n" "${OFFERED[@]}"
  '
  [ "$status" -eq 0 ]
  count="$(printf '%s\n' "$output" | grep -c '^OFFERED:' || true)"
  [ "$count" -eq 1 ]
  [[ "$output" == *"OFFERED:Remove Ollama model fast-fake:1?"* ]]
}

@test "tier2_ollama_models: a model absent from 'ollama list' is skipped (no offer)" {
  mkdir -p "$TMP/dotfiles/scripts"
  cat >"$(fragment_path "$TMP/dotfiles")" <<'EOF'
OLLAMA_MODEL="fast-fake:1"
OLLAMA_VISION_MODEL="vision-fake:1"
OLLAMA_MLX_MODEL="bulk-fake:1"
OLLAMA_BRAINSTORM_MODEL="brainstorm-fake:1"
EOF
  BIN="$TMP/bin"
  LIST_FILE="$TMP/list.txt"
  printf 'NAME  ID  SIZE  MODIFIED\nsome-other-model:1  x  1B  now\n' >"$LIST_FILE"
  write_tier2_stubs "$BIN" "$LIST_FILE"

  # shellcheck disable=SC2016  # $TEST_LIB/$TEST_DOTFILES/etc must expand in the inner bash, not here
  run env PATH="$BIN:$PATH" TEST_LIB="$LIB" TEST_DOTFILES="$TMP/dotfiles" bash -c '
    set -uo pipefail
    . "$TEST_LIB"
    DOTFILES="$TEST_DOTFILES"
    DRY_RUN=0 ASSUME_YES=0 REMOVED=() DECLINED=() LEFT=() MANUAL=() FAILED=()
    OFFERED=()
    offer() { OFFERED+=("$1"); return 1; }
    tier2_ollama_models
    [ "${#OFFERED[@]}" -eq 0 ] || printf "OFFERED:%s\n" "${OFFERED[@]}"
  '
  [ "$status" -eq 0 ]
  count="$(printf '%s\n' "$output" | grep -c '^OFFERED:' || true)"
  [ "$count" -eq 0 ]
}

@test "tier2_ollama_models: a legacy model present in 'ollama list' is offered too" {
  mkdir -p "$TMP/dotfiles/scripts"
  cat >"$(fragment_path "$TMP/dotfiles")" <<'EOF'
OLLAMA_MODEL="fast-fake:1"
OLLAMA_VISION_MODEL="vision-fake:1"
OLLAMA_MLX_MODEL="bulk-fake:1"
OLLAMA_BRAINSTORM_MODEL="brainstorm-fake:1"
OLLAMA_LEGACY_MODELS="qwen2.5-coder:7b"
EOF
  BIN="$TMP/bin"
  LIST_FILE="$TMP/list.txt"
  printf 'NAME  ID  SIZE  MODIFIED\nqwen2.5-coder:7b  x  1B  now\n' >"$LIST_FILE"
  write_tier2_stubs "$BIN" "$LIST_FILE"

  # shellcheck disable=SC2016  # $TEST_LIB/$TEST_DOTFILES/etc must expand in the inner bash, not here
  run env PATH="$BIN:$PATH" TEST_LIB="$LIB" TEST_DOTFILES="$TMP/dotfiles" bash -c '
    set -uo pipefail
    . "$TEST_LIB"
    DOTFILES="$TEST_DOTFILES"
    DRY_RUN=0 ASSUME_YES=0 REMOVED=() DECLINED=() LEFT=() MANUAL=() FAILED=()
    OFFERED=()
    offer() { OFFERED+=("$1"); return 1; }
    tier2_ollama_models
    [ "${#OFFERED[@]}" -eq 0 ] || printf "OFFERED:%s\n" "${OFFERED[@]}"
  '
  [ "$status" -eq 0 ]
  [[ "$output" == *"OFFERED:Remove Ollama model qwen2.5-coder:7b?"* ]]
}
