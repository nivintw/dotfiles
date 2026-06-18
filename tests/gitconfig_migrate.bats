#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Tests for scripts/gitconfig_migrate.sh, the helper the installer runs before stow
# to safely adopt a pre-existing ~/.gitconfig. The risks these guard: a fresh
# machine's real ~/.gitconfig must be BACKED UP (never clobbered) and its contents
# preserved in the overlay so the user's settings aren't lost; and the migrated
# text must never re-include the overlay itself (git would hit "exceeded maximum
# include depth"). A managed machine (symlink) must be a strict no-op so re-runs
# don't duplicate config.
#
# Run:  bats tests/gitconfig_migrate.bats

setup() {
  LIB="$BATS_TEST_DIRNAME/../scripts/gitconfig_migrate.sh"
  # shellcheck source=../scripts/gitconfig_migrate.sh disable=SC1091
  . "$LIB"
  TMP="$(mktemp -d)"
  TARGET="$TMP/.gitconfig"
  OVERLAY="$TMP/.gitconfig_local"
  BASELINE="$TMP/baseline"
  printf '[core]\n\tpager = delta\n[include]\n\tpath = ~/.gitconfig_local\n' > "$BASELINE"
}

teardown() {
  rm -rf "$TMP"
}

@test "a symlinked ~/.gitconfig is left untouched (managed machine, no-op)" {
  ln -s "$BASELINE" "$TARGET"
  run gitconfig_migrate "$TARGET" "$OVERLAY" "$BASELINE"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ -L "$TARGET" ]
  [ ! -e "$OVERLAY" ]
}

@test "an absent ~/.gitconfig is a no-op" {
  run gitconfig_migrate "$TARGET" "$OVERLAY" "$BASELINE"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
  [ ! -e "$OVERLAY" ]
}

@test "a real file identical to the baseline is removed, not backed up" {
  cp "$BASELINE" "$TARGET"
  run gitconfig_migrate "$TARGET" "$OVERLAY" "$BASELINE"
  [ "$status" -eq 0 ]
  [ ! -e "$TARGET" ]
  [ ! -e "$TARGET.pre-stow.bak" ]
  [ ! -e "$OVERLAY" ]
}

@test "a differing real file is backed up AND migrated into the overlay" {
  printf '[user]\n\temail = me@work.example\n[alias]\n\tco = checkout\n' > "$TARGET"
  run gitconfig_migrate "$TARGET" "$OVERLAY" "$BASELINE"
  [ "$status" -eq 0 ]
  # Original moved aside, path freed for stow.
  [ ! -e "$TARGET" ]
  [ -f "$TARGET.pre-stow.bak" ]
  # Contents preserved in the overlay.
  grep -q "me@work.example" "$OVERLAY"
  grep -q "co = checkout" "$OVERLAY"
}

@test "an existing backup is not clobbered — the next one is numbered" {
  printf 'old backup\n' > "$TARGET.pre-stow.bak"
  printf '[user]\n\temail = me@work.example\n' > "$TARGET"
  run gitconfig_migrate "$TARGET" "$OVERLAY" "$BASELINE"
  [ "$status" -eq 0 ]
  # The pre-existing backup is intact...
  grep -q "old backup" "$TARGET.pre-stow.bak"
  # ...and the new one landed beside it, numbered.
  [ -f "$TARGET.pre-stow.bak.1" ]
  grep -q "me@work.example" "$TARGET.pre-stow.bak.1"
}

@test "a migrated [include] of the overlay itself is stripped (no include loop)" {
  printf '[user]\n\temail = me@work.example\n[include]\n\tpath = ~/.gitconfig_local\n' > "$TARGET"
  run gitconfig_migrate "$TARGET" "$OVERLAY" "$BASELINE"
  [ "$status" -eq 0 ]
  # The user's content survives...
  grep -q "me@work.example" "$OVERLAY"
  # ...but the self-referential include is gone.
  run grep -c "gitconfig_local" "$OVERLAY"
  [ "$output" -eq 0 ]
}

@test "a self-include is stripped regardless of section-name casing" {
  printf '[user]\n\temail = me@work.example\n[Include]\n\tPath = ~/.gitconfig_local\n' > "$TARGET"
  run gitconfig_migrate "$TARGET" "$OVERLAY" "$BASELINE"
  [ "$status" -eq 0 ]
  grep -q "me@work.example" "$OVERLAY"
  run grep -ic "gitconfig_local" "$OVERLAY"
  [ "$output" -eq 0 ]
}

@test "a self-include with a quoted path is stripped (no include loop)" {
  printf '[user]\n\temail = me@work.example\n[include]\n\tpath = "~/.gitconfig_local"\n' > "$TARGET"
  run gitconfig_migrate "$TARGET" "$OVERLAY" "$BASELINE"
  [ "$status" -eq 0 ]
  grep -q "me@work.example" "$OVERLAY"
  run grep -c "gitconfig_local" "$OVERLAY"
  [ "$output" -eq 0 ]
}

@test "a self-include with an inline comment on the path is stripped (no include loop)" {
  printf '[user]\n\temail = me@work.example\n[include]\n\tpath = ~/.gitconfig_local # local\n' > "$TARGET"
  run gitconfig_migrate "$TARGET" "$OVERLAY" "$BASELINE"
  [ "$status" -eq 0 ]
  grep -q "me@work.example" "$OVERLAY"
  run grep -c "gitconfig_local" "$OVERLAY"
  [ "$output" -eq 0 ]
}

@test "a foreign includeIf pointing elsewhere is preserved" {
  printf '[includeIf "gitdir:~/work/"]\n\tpath = ~/.gitconfig.work\n' > "$TARGET"
  run gitconfig_migrate "$TARGET" "$OVERLAY" "$BASELINE"
  [ "$status" -eq 0 ]
  grep -q 'gitdir:~/work/' "$OVERLAY"
  grep -q "gitconfig.work" "$OVERLAY"
}

@test "migration appends to an existing overlay without dropping its content" {
  printf '# seeded\n[commit]\n\tgpgsign = false\n' > "$OVERLAY"
  printf '[user]\n\temail = me@work.example\n' > "$TARGET"
  run gitconfig_migrate "$TARGET" "$OVERLAY" "$BASELINE"
  [ "$status" -eq 0 ]
  grep -q "gpgsign = false" "$OVERLAY"
  grep -q "me@work.example" "$OVERLAY"
}

@test "an unwritable overlay fails loudly and leaves the original in place (no data loss)" {
  # The fold happens BEFORE the original is moved aside, so a write failure must
  # abort with the user's ~/.gitconfig untouched — never destroyed-and-unmigrated.
  if [ "$(id -u)" -eq 0 ]; then skip "root bypasses file permissions"; fi
  printf '[user]\n\temail = me@work.example\n' > "$TARGET"
  : > "$OVERLAY"
  chmod 000 "$OVERLAY"
  run gitconfig_migrate "$TARGET" "$OVERLAY" "$BASELINE"
  chmod 644 "$OVERLAY"
  [ "$status" -ne 0 ]                    # aborted, didn't report success
  [ -f "$TARGET" ]                       # original still there
  grep -q "me@work.example" "$TARGET"
  [ ! -e "$TARGET.pre-stow.bak" ]        # nothing moved aside
}
