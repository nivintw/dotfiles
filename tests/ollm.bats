#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Behavior tests for the `ollm` offload CLI (home/.local/bin/ollm) and the
# ollama-roster.sh SessionStart hook (home/.claude/hooks/ollama-roster.sh).
#
# ollm's own network calls all go through `curl`, so it's stubbed here (dispatching on
# the target URL, logging POST payloads); jq is real (it's a hard dependency and cheap
# to run). OLLM_MODELS_FILE lets tests point role resolution at a fake fragment instead
# of the real dotfiles-checkout tags, keeping the ollm tests independent of whatever
# models the repo's shared model-tags fragment (under scripts/) happens to name. The
# hook tests don't use that seam: the hook execs its stowed sibling ollm, which (run
# with OLLM_MODELS_FILE explicitly unset via `env -u`) resolves this checkout's real
# fragment — so those tests assert against the real tags.
#
# Note for the coverage gate (tests/test_coverage.py): the shared fragment's exact
# filename is deliberately never spelled out verbatim below (see the fixture var name
# and comments near the hook tests) — it's pure data with no logic, allowlisted as
# untested-by-design, and the gate's `_referenced` check is a dumb literal-token
# search that would otherwise mistake a passing mention for real coverage.
#
# stdin matters: ollm reads stdin whenever it isn't a TTY, which bats' non-interactive
# runner always is. Every invocation below redirects stdin explicitly (a file or
# /dev/null) so the prompt content is deterministic instead of picking up bats' own
# stdin by accident.
#
# Run:  bats tests/ollm.bats

setup() {
  OLLM="$BATS_TEST_DIRNAME/../home/.local/bin/ollm"
  HOOK="$BATS_TEST_DIRNAME/../home/.claude/hooks/ollama-roster.sh"
  WORK="$(mktemp -d)"

  MODELS_FILE="$WORK/fake-model-tags.sh" # a fixture, not the real shared fragment
  cat >"$MODELS_FILE" <<'EOF'
OLLAMA_MODEL="fast-fake:1"
OLLAMA_VISION_MODEL="vision-fake:1"
OLLAMA_MLX_MODEL="bulk-fake:1"
OLLAMA_BRAINSTORM_MODEL="brainstorm-fake:1"
EOF

  # Canned curl responses; individual tests overwrite these before invoking ollm/the
  # hook. tags_exit, when present, makes the /api/tags stub exit with its contents
  # instead of serving tags.json (simulates the server being down).
  printf '%s' '{"models":[]}' >"$WORK/tags.json"
  printf '%s' '{"capabilities":["thinking"]}' >"$WORK/show.json"
  printf '%s' '{"response":"hello world","done_reason":"stop"}' >"$WORK/generate.json"

  CURL="$WORK/curlbin"
  mkdir -p "$CURL"
  write_curl_stub "$CURL/curl"
}

teardown() {
  rm -rf "$WORK"
}

# A curl stand-in that dispatches on the target URL and logs POST payloads (-d) for
# /api/show and /api/generate, so tests can assert on what ollm actually sent. Bodies
# come from $WORK/{tags,show,generate}.json (mutable per test); $WORK/tags_exit, when
# present, makes the /api/tags call fail with that exit code instead of serving a body.
# Written to a file (rather than inlined per test) so it can also be copied verbatim
# into the hook tests' curated PATH dirs below.
#
# The hook tests run this stub under a deliberately bare PATH (to control ollama/jq
# presence), so it can't rely on `cat` being findable at run time — its own absolute
# path is baked in at stub-generation time instead.
write_curl_stub() {
  local cat_bin
  cat_bin="$(command -v cat)"
  cat >"$1" <<EOF
#!/bin/sh
url=""
data=""
prev=""
for a in "\$@"; do
  case "\$a" in http*) url="\$a" ;; esac
  if [ "\$prev" = "-d" ]; then data="\$a"; fi
  prev="\$a"
done
case "\$url" in
*/api/tags)
  if [ -f "$WORK/tags_exit" ]; then
    exit "\$($cat_bin "$WORK/tags_exit")"
  fi
  $cat_bin "$WORK/tags.json"
  ;;
*/api/show)
  printf '%s\\n' "\$data" >> "$WORK/show_payloads.log"
  $cat_bin "$WORK/show.json"
  ;;
*/api/generate)
  printf '%s\\n' "\$data" >> "$WORK/generate_payloads.log"
  $cat_bin "$WORK/generate.json"
  ;;
*)
  exit 1
  ;;
esac
EOF
  chmod +x "$1"
}

# Every ollm invocation: stub curl first on PATH (real jq stays reachable from the rest
# of $PATH), the fake models fragment, and a URL that would fail loudly if anything
# accidentally hit a real server.
run_ollm() {
  run env PATH="$CURL:$PATH" OLLM_MODELS_FILE="$MODELS_FILE" OLLM_URL="http://fake-ollama:11434" \
    "$OLLM" "$@"
}

# --tools dispatches to a sibling `ollm-tools-loop`, resolved via this script's own
# `readlink -f "$0"` — not a PATH lookup — so exercising the dispatch means running a
# *copy* of ollm alongside a fake ollm-tools-loop in the same directory, rather than
# stubbing anything on PATH. The fake helper logs its argv (one arg per line) to
# $WORK/tools_argv.log and prints a fixed marker, so tests assert on both what ollm
# forwarded and that ollm's stdout is exactly the helper's stdout (the exec is a true
# process replacement, no wrapping).
write_tools_stub() {
  cat >"$1" <<EOF
#!/bin/sh
for a in "\$@"; do printf '%s\n' "\$a"; done > "$WORK/tools_argv.log"
printf '%s\n' "stub-tool-response"
EOF
  chmod +x "$1"
}

run_ollm_tools() {
  local bin="$WORK/toolsbin"
  mkdir -p "$bin"
  cp "$OLLM" "$bin/ollm"
  write_tools_stub "$bin/ollm-tools-loop"
  run env PATH="$CURL:$PATH" OLLM_MODELS_FILE="$MODELS_FILE" OLLM_URL="http://fake-ollama:11434" \
    "$bin/ollm" "$@"
}

# --- basics: help, missing/invalid input -------------------------------------------

@test "--help prints usage and exits 0" {
  run_ollm --help </dev/null
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage: ollm"* ]]
}

@test "no prompt from args or stdin exits 2 with a clear message" {
  run_ollm </dev/null
  [ "$status" -eq 2 ]
  [[ "$output" == *"no prompt"* ]]
}

@test "an unknown option exits 2" {
  run_ollm --bogus hi </dev/null
  [ "$status" -eq 2 ]
  [[ "$output" == *"unknown option"* ]]
}

@test "an unknown role exits 2" {
  run_ollm --role bogus hi </dev/null
  [ "$status" -eq 2 ]
  [[ "$output" == *"unknown role"* ]]
}

@test "--num-predict with a non-numeric value exits 2" {
  run_ollm --num-predict abc hi </dev/null
  [ "$status" -eq 2 ]
}

# --- role / model resolution --------------------------------------------------------

@test "the default role (no --role) is fast" {
  run_ollm hi </dev/null
  [ "$status" -eq 0 ]
  grep -q "fast-fake:1" "$WORK/generate_payloads.log"
}

@test "--role bulk resolves to the bulk model tag" {
  run_ollm --role bulk hi </dev/null
  [ "$status" -eq 0 ]
  grep -q "bulk-fake:1" "$WORK/generate_payloads.log"
}

@test "--model overrides role resolution" {
  run_ollm --role bulk --model custom:tag hi </dev/null
  [ "$status" -eq 0 ]
  grep -q "custom:tag" "$WORK/generate_payloads.log"
  run grep -q "bulk-fake:1" "$WORK/generate_payloads.log"
  [ "$status" -ne 0 ]
}

@test "--image with no role defaults to the vision model and attaches images" {
  IMG="$WORK/pic.png"
  printf 'fake-image-bytes' >"$IMG"
  run_ollm --image "$IMG" describe </dev/null
  [ "$status" -eq 0 ]
  grep -q "vision-fake:1" "$WORK/generate_payloads.log"
  grep -q '"images"' "$WORK/generate_payloads.log"
}

# --- thinking capability handling ---------------------------------------------------

@test "a thinking-capable model without --think sends think:false" {
  printf '%s' '{"capabilities":["thinking"]}' >"$WORK/show.json"
  run_ollm hi </dev/null
  [ "$status" -eq 0 ]
  grep -q '"think":false' "$WORK/generate_payloads.log"
}

@test "a thinking-capable model with --think sends think:true" {
  printf '%s' '{"capabilities":["thinking"]}' >"$WORK/show.json"
  run_ollm --think hi </dev/null
  [ "$status" -eq 0 ]
  grep -q '"think":true' "$WORK/generate_payloads.log"
}

@test "a non-thinking model omits the think field entirely" {
  printf '%s' '{"capabilities":[]}' >"$WORK/show.json"
  run_ollm hi </dev/null
  [ "$status" -eq 0 ]
  run grep -q '"think"' "$WORK/generate_payloads.log"
  [ "$status" -ne 0 ]
}

@test "--think on a model without the thinking capability fails" {
  printf '%s' '{"capabilities":[]}' >"$WORK/show.json"
  run_ollm --think hi </dev/null
  [ "$status" -eq 1 ]
  [[ "$output" == *"does not support thinking"* ]]
}

# --- server / response error handling ------------------------------------------------

@test "the server not responding exits 1" {
  echo 22 >"$WORK/tags_exit"
  run_ollm hi </dev/null
  [ "$status" -eq 1 ]
  [[ "$output" == *"not responding"* ]]
}

@test "an API error field exits 1 with the server's message" {
  printf '%s' '{"error":"boom"}' >"$WORK/generate.json"
  run_ollm hi </dev/null
  [ "$status" -eq 1 ]
  [[ "$output" == *"boom"* ]]
}

@test "an empty response with done_reason=length blames the token budget" {
  printf '%s' '{"response":"","done_reason":"length"}' >"$WORK/generate.json"
  run_ollm hi </dev/null
  [ "$status" -eq 1 ]
  [[ "$output" == *"num-predict"* ]]
}

@test "an empty response with another done_reason still exits 1" {
  printf '%s' '{"response":"","done_reason":"stop"}' >"$WORK/generate.json"
  run_ollm hi </dev/null
  [ "$status" -eq 1 ]
}

# --- happy path / stdin handling -----------------------------------------------------

@test "the happy path prints the model's response text exactly" {
  printf '%s' '{"response":"hello world","done_reason":"stop"}' >"$WORK/generate.json"
  run_ollm hi </dev/null
  [ "$status" -eq 0 ]
  [ "$output" = "hello world" ]
}

@test "the prompt combines arg text and piped stdin" {
  printf 'piped-context' >"$WORK/stdin.txt"
  run env PATH="$CURL:$PATH" OLLM_MODELS_FILE="$MODELS_FILE" OLLM_URL="http://fake-ollama:11434" \
    "$OLLM" "arg-instruction" <"$WORK/stdin.txt"
  [ "$status" -eq 0 ]
  grep -q "arg-instruction" "$WORK/generate_payloads.log"
  grep -q "piped-context" "$WORK/generate_payloads.log"
}

# --- --tools -------------------------------------------------------------------------

@test "--tools and --image cannot be combined" {
  run_ollm --tools --image "$WORK/pic.png" hi </dev/null
  [ "$status" -eq 2 ]
  [[ "$output" == *"--tools and --image cannot be combined"* ]]
}

@test "--tools-root must be an existing directory" {
  run_ollm --tools --tools-root "$WORK/does-not-exist" hi </dev/null
  [ "$status" -eq 2 ]
  [[ "$output" == *"--tools-root is not a directory"* ]]
}

@test "--tools-cap rejects a non-positive value" {
  run_ollm --tools --tools-cap 0 hi </dev/null
  [ "$status" -eq 2 ]
}

@test "--tools dispatches to the sibling ollm-tools-loop with the resolved model, url, and prompt" {
  run_ollm_tools --tools --tools-root "$WORK" hi </dev/null
  [ "$status" -eq 0 ]
  [ "$output" = "stub-tool-response" ]
  grep -qxF "http://fake-ollama:11434" "$WORK/tools_argv.log" # --url value
  grep -qxF "fast-fake:1" "$WORK/tools_argv.log"               # resolved default-role model
  grep -qxF "$WORK" "$WORK/tools_argv.log"                     # --tools-root value
  grep -qxF "hi" "$WORK/tools_argv.log"                        # prompt, after --
}

@test "--tools forwards --tools-cap" {
  run_ollm_tools --tools --tools-root "$WORK" --tools-cap 9 hi </dev/null
  [ "$status" -eq 0 ]
  grep -qxF "9" "$WORK/tools_argv.log"
}

@test "--tools without --think does not forward --think" {
  run_ollm_tools --tools --tools-root "$WORK" hi </dev/null
  [ "$status" -eq 0 ]
  run grep -qxF -- "--think" "$WORK/tools_argv.log"
  [ "$status" -ne 0 ]
}

@test "--tools --think forwards --think" {
  run_ollm_tools --tools --tools-root "$WORK" --think hi </dev/null
  [ "$status" -eq 0 ]
  grep -qxF -- "--think" "$WORK/tools_argv.log"
}

# --- --list ----------------------------------------------------------------------------

@test "--list shows all four roles with correct installed/missing markers" {
  printf '%s' '{"models":[{"name":"fast-fake:1"},{"name":"vision-fake:1"}]}' >"$WORK/tags.json"
  run_ollm --list </dev/null
  [ "$status" -eq 0 ]
  [ "$(printf '%s\n' "$output" | wc -l)" -eq 4 ]
  [[ "$(printf '%s\n' "$output" | grep '^fast ')" == *installed* ]]
  [[ "$(printf '%s\n' "$output" | grep '^vision ')" == *installed* ]]
  [[ "$(printf '%s\n' "$output" | grep '^bulk ')" == *missing* ]]
  [[ "$(printf '%s\n' "$output" | grep '^brainstorm ')" == *missing* ]]
}

# --- ollama-roster.sh (SessionStart hook) -----------------------------------------------
#
# The hook delegates roster rendering to its stowed sibling `ollm --list`, resolving it
# relative to its OWN path (readlink -f "$0"). Run in place from this worktree checkout,
# that resolves to this checkout's ollm, which in turn (no OLLM_MODELS_FILE set) resolves
# this checkout's real fragment under scripts/ — so the happy-path test asserts against
# the real fast-tier tag rather than a fake fixture.
#
# Each test builds a curated PATH from scratch (symlinking in only the real tools it
# needs) rather than subtracting directories from the ambient $PATH: jq/ollama/curl live
# in different places on different hosts (Homebrew on macOS vs apt on the Ubuntu CI
# runner), so the only portable way to guarantee a tool's *absence* is to never put it
# on PATH in the first place.

REAL_FAST_TAG="qwen3:4b-instruct-2507-q4_K_M"

@test "ollama-roster.sh exits 0 silently when ollama is not on PATH" {
  BIN="$WORK/no-ollama-bin"
  mkdir -p "$BIN"
  ln -s "$(command -v bash)" "$BIN/bash"
  ln -s "$(command -v curl)" "$BIN/curl"
  ln -s "$(command -v jq)" "$BIN/jq"
  run env -u OLLM_MODELS_FILE PATH="$BIN" "$HOOK"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "ollama-roster.sh degrades to the not-usable notice when jq is missing" {
  # ollm hard-requires jq; the hook must catch its failure and stay fail-open.
  BIN="$WORK/no-jq-bin"
  mkdir -p "$BIN"
  ln -s "$(command -v bash)" "$BIN/bash"
  ln -s "$(command -v readlink)" "$BIN/readlink" # hook resolves its sibling ollm
  printf '#!/bin/sh\nexit 0\n' >"$BIN/ollama"
  chmod +x "$BIN/ollama"
  run env -u OLLM_MODELS_FILE PATH="$BIN" "$HOOK"
  [ "$status" -eq 0 ]
  [[ "$output" == *"not usable for offload"* ]]
}

@test "ollama-roster.sh lists the roster via ollm --list when the server responds" {
  BIN="$WORK/happy-bin"
  mkdir -p "$BIN"
  ln -s "$(command -v bash)" "$BIN/bash"
  ln -s "$(command -v jq)" "$BIN/jq"
  ln -s "$(command -v grep)" "$BIN/grep"         # ollm's installed/missing marker loop
  ln -s "$(command -v readlink)" "$BIN/readlink" # hook→ollm and ollm→fragment resolution
  ln -s "$(command -v dirname)" "$BIN/dirname"   # ollm's models_file()
  printf '#!/bin/sh\nexit 0\n' >"$BIN/ollama"
  chmod +x "$BIN/ollama"
  write_curl_stub "$BIN/curl" # same stub as the ollm tests: reads $WORK/tags.json etc.
  printf '{"models":[{"name":"%s"}]}' "$REAL_FAST_TAG" >"$WORK/tags.json"

  run env -u OLLM_MODELS_FILE PATH="$BIN" "$HOOK"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Local Ollama roster"* ]]
  [[ "$output" == *"$REAL_FAST_TAG"* ]]
  [[ "$(printf '%s\n' "$output" | grep ' fast ')" == *installed* ]]
  [[ "$(printf '%s\n' "$output" | grep ' bulk ')" == *missing* ]]
}

@test "ollama-roster.sh reports not-usable when the server is down, still exiting 0" {
  BIN="$WORK/down-bin"
  mkdir -p "$BIN"
  ln -s "$(command -v bash)" "$BIN/bash"
  ln -s "$(command -v jq)" "$BIN/jq"
  ln -s "$(command -v readlink)" "$BIN/readlink"
  ln -s "$(command -v dirname)" "$BIN/dirname"
  printf '#!/bin/sh\nexit 0\n' >"$BIN/ollama"
  chmod +x "$BIN/ollama"
  write_curl_stub "$BIN/curl"
  echo 22 >"$WORK/tags_exit"

  run env -u OLLM_MODELS_FILE PATH="$BIN" "$HOOK"
  [ "$status" -eq 0 ]
  [[ "$output" == *"not usable for offload"* ]]
}
