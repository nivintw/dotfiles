#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Behavior tests for dock.sh — the declarative macOS Dock rebuild. dockutil and killall are
# macOS-only, so each test puts fakes for them on PATH and drives the Darwin-guarded logic on
# any host via DOCK_UNAME=Darwin. DOCK_APPS points the rebuild at fake .app dirs under a
# tmpdir (real /Applications/*.app can't be created on a Linux CI runner).
#
# Covers issue #155 (a mid-rebuild --add failure must still restart the Dock, never strand an
# empty one) and issue #156 (skip the rebuild when the Dock already matches; --check reports
# drift without changing anything; comparison robust to percent-encoding + cryptex prefixes).
#
# Run:  bats tests/dock.bats

setup() {
  SCRIPT="$BATS_TEST_DIRNAME/../dock.sh"
  WORK="$(mktemp -d)"
  BIN="$WORK/bin"
  mkdir -p "$BIN"
  # Where a fake dockutil records that a mutating call happened, and the killall sentinel.
  DOCK_LOG="$WORK/dockutil.log"
  KILLALL_LOG="$WORK/killall.log"
  # Two fake installed apps for the desired list.
  mkdir -p "$WORK/Apps/Safari.app" "$WORK/Apps/Mail.app"
}

teardown() {
  rm -rf "$WORK"
}

# Install a fake `dockutil` whose --list prints $1 (a here-string of lines) and whose
# mutating subcommands (--add/--remove) succeed, logging each call. $2, when "addfail", makes
# every --add exit non-zero (to simulate a transient dockutil error mid-rebuild).
make_dockutil() {
  local list_output="$1" add_mode="${2:-ok}"
  {
    echo '#!/usr/bin/env bash'
    echo "printf '%s ' \"\$@\" >>'$DOCK_LOG'; printf '\\n' >>'$DOCK_LOG'"
    echo 'case "$1" in'
    printf '  --list) cat <<'\''EOF'\''\n%s\nEOF\n  ;;\n' "$list_output"
    if [ "$add_mode" = addfail ]; then
      echo '  *) for a in "$@"; do [ "$a" = --add ] && exit 1; done; exit 0 ;;'
    else
      echo '  *) exit 0 ;;'
    fi
    echo 'esac'
  } >"$BIN/dockutil"
  chmod +x "$BIN/dockutil"
}

# Install a fake `killall` that records it fired.
make_killall() {
  {
    echo '#!/usr/bin/env bash'
    echo "echo \"\$@\" >>'$KILLALL_LOG'"
  } >"$BIN/killall"
  chmod +x "$BIN/killall"
}

# Run dock.sh with the fakes on PATH, Darwin forced, and the two fake apps as the desired set.
run_dock() {
  run env \
    PATH="$BIN:$PATH" \
    DOCK_UNAME=Darwin \
    DOCK_APPS="$WORK/Apps/Safari.app"$'\n'"$WORK/Apps/Mail.app" \
    bash "$SCRIPT" "$@"
}

@test "a dockutil --add failure still restarts the Dock (never strands an empty one)" {
  # Current Dock differs from desired (empty), so a rebuild is triggered; every --add fails.
  make_dockutil "" addfail
  make_killall
  run_dock
  # The run completes (does not abort under set -e mid-rebuild)...
  [ "$status" -eq 0 ]
  # ...and killall Dock fired despite the --add failures.
  [ -f "$KILLALL_LOG" ]
  grep -q Dock "$KILLALL_LOG"
  [[ "$output" == *"failed to add"* ]]
}

@test "a fully successful rebuild adds each app and restarts the Dock" {
  make_dockutil "" ok
  make_killall
  run_dock
  [ "$status" -eq 0 ]
  grep -q -- "--add" "$DOCK_LOG"
  grep -q -- "--remove all" "$DOCK_LOG"
  [ -f "$KILLALL_LOG" ]
  [[ "$output" == *"Dock rebuilt."* ]]
}

@test "already-matching Dock makes no changes and does not restart" {
  # --list reports exactly the two desired apps (as dockutil file URLs) → no drift.
  make_dockutil "Safari	file://$WORK/Apps/Safari.app/
Mail	file://$WORK/Apps/Mail.app/" ok
  make_killall
  run_dock
  [ "$status" -eq 0 ]
  # No mutating call and no restart happened — only the read-only --list.
  ! grep -q -- "--add" "$DOCK_LOG"
  ! grep -q -- "--remove" "$DOCK_LOG"
  [ ! -f "$KILLALL_LOG" ]
  [[ "$output" == *"already matches"* ]]
}

@test "comparison is robust to percent-encoding and cryptex path prefixes" {
  # Safari arrives via a macOS cryptex prefix; Mail's URL is percent-encoded. Both must still
  # reduce to the same keys as the desired apps → still a match, no rebuild.
  make_dockutil "Safari	file:///System/Cryptexes/App/System/Applications/Safari.app/
Mail	file://$WORK/Apps/Ma%69l.app/" ok
  make_killall
  run_dock
  [ "$status" -eq 0 ]
  ! grep -q -- "--add" "$DOCK_LOG"
  [ ! -f "$KILLALL_LOG" ]
  [[ "$output" == *"already matches"* ]]
}

@test "--check reports drift without modifying the Dock" {
  # Live Dock has an extra app not in the desired set → drift.
  make_dockutil "Safari	file://$WORK/Apps/Safari.app/
Mail	file://$WORK/Apps/Mail.app/
Discord	file:///Applications/Discord.app/" ok
  make_killall
  run_dock --check
  [ "$status" -eq 1 ]
  ! grep -q -- "--add" "$DOCK_LOG"
  ! grep -q -- "--remove" "$DOCK_LOG"
  [ ! -f "$KILLALL_LOG" ]
  [[ "$output" == *"drift detected"* ]]
}

@test "--check on a matching Dock reports no drift and exits 0" {
  make_dockutil "Safari	file://$WORK/Apps/Safari.app/
Mail	file://$WORK/Apps/Mail.app/" ok
  make_killall
  run_dock --check
  [ "$status" -eq 0 ]
  [ ! -f "$KILLALL_LOG" ]
  [[ "$output" == *"no drift"* ]]
}

@test "non-Darwin host skips with the reserved skip exit code" {
  make_dockutil "" ok
  make_killall
  run env PATH="$BIN:$PATH" DOCK_UNAME=Linux bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"macOS-only"* ]]
}
