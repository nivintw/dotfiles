#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Smoke tests for the ported zsh helper functions (see tests/fish_functions.bats for
# the fish originals). Same philosophy: these wrap interactive tools (fzf, git, rg) so
# their happy paths aren't worth driving headless — but their guard rails (usage
# messages, "not a git repo", missing-arg handling, OS dispatch) are pure logic and
# cheap to lock down.
#
# Run:  bats tests/zsh_functions.bats

FUNCDIR_REL="../home/.config/zsh/functions"

setup() {
  FUNCDIR="$BATS_TEST_DIRNAME/$FUNCDIR_REL"
  NONREPO="$(mktemp -d)"
}

teardown() {
  rm -rf "$NONREPO"
}

# Run a snippet with every ported function autoloadable (fpath + autoload -Uz, mirroring
# .zshrc), capturing stdout+stderr+status. Args are interpolated as plain words (fine for
# the simple, space-free tokens these tests pass).
zshrun() {
  local func="$1"; shift
  run zsh -c "fpath=('$FUNCDIR' \$fpath); autoload -Uz '$FUNCDIR'/*(N:t); $func $*"
}

# Run a zsh snippet with the functions autoloadable and `uname` reporting $1, so the OS
# helpers (is_macos/is_linux/is_wsl) take a deterministic branch on any host. A test that
# wants to control which tool a helper dispatches to sets $STUBDIR (a dir of fake
# binaries); it is prepended to PATH so its stubs win over the real ones. -f skips every
# startup file so unrelated rc state can't perturb the result.
run_zsh_os() {
  local os="$1"; shift
  UNAMESHIM="$(mktemp -d)"
  printf '#!/bin/sh\necho %s\n' "$os" > "$UNAMESHIM/uname"
  chmod +x "$UNAMESHIM/uname"
  run env PATH="${STUBDIR:+$STUBDIR:}$UNAMESHIM:/usr/bin:/bin" zsh -f -c \
    "fpath=('$FUNCDIR' \$fpath); autoload -Uz '$FUNCDIR'/*(N:t); $*"
  rm -rf "$UNAMESHIM"
}

@test "git_prune_local --help prints usage and returns 0" {
  zshrun git_prune_local --help
  [ "$status" -eq 0 ]
  [[ "$output" == *"Usage: git_prune_local"* ]]
}

@test "git_prune_local outside a git repo errors and returns 1" {
  cd "$NONREPO"
  zshrun git_prune_local
  [ "$status" -eq 1 ]
  [[ "$output" == *"Not a git repository"* ]]
}

@test "git_prune_local rejects an unexpected argument and returns 1" {
  zshrun git_prune_local --bogus
  [ "$status" -eq 1 ]
  [[ "$output" == *"unexpected argument"* ]]
}

@test "pyclean --dry-run lists caches without deleting them" {
  mkdir -p "$NONREPO/__pycache__" "$NONREPO/.pytest_cache"
  touch "$NONREPO/leftover.pyc"
  cd "$NONREPO"
  zshrun pyclean --dry-run
  [ "$status" -eq 0 ]
  [[ "$output" == *"dry run"* ]]
  [ -d "$NONREPO/__pycache__" ]
  [ -f "$NONREPO/leftover.pyc" ]
}

@test "pyclean deletes caches but leaves real files intact" {
  mkdir -p "$NONREPO/__pycache__" "$NONREPO/.mypy_cache"
  touch "$NONREPO/leftover.pyc" "$NONREPO/keep.py"
  cd "$NONREPO"
  zshrun pyclean
  [ "$status" -eq 0 ]
  [ ! -d "$NONREPO/__pycache__" ]
  [ ! -d "$NONREPO/.mypy_cache" ]
  [ ! -f "$NONREPO/leftover.pyc" ]
  [ -f "$NONREPO/keep.py" ]
}

@test "pyclean rejects an unexpected argument and returns 2" {
  zshrun pyclean bogus
  [ "$status" -eq 2 ]
  [[ "$output" == *"unexpected argument"* ]]
}

@test "fkill with an invalid signal is rejected before touching fzf, returns 2" {
  zshrun fkill BOGUSSIG
  [ "$status" -eq 2 ]
  [[ "$output" == *"invalid signal"* ]]
}

@test "fkill with an out-of-range numeric signal is rejected, returns 2" {
  zshrun fkill 999
  [ "$status" -eq 2 ]
  [[ "$output" == *"out of range"* ]]
}

@test "launch-docs with a non-numeric port prints usage and returns 2" {
  zshrun launch-docs abc
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage: launch-docs"* ]]
}

@test "launch-docs with an out-of-range port prints usage and returns 2" {
  zshrun launch-docs 99999
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage: launch-docs"* ]]
}

@test "launch-docs reports a missing docs dir when none can be resolved" {
  cd "$NONREPO"
  run env DOTFILES="$NONREPO/nope" HOME="$NONREPO" zsh -c \
    "fpath=('$FUNCDIR' \$fpath); autoload -Uz '$FUNCDIR'/*(N:t); launch-docs"
  [ "$status" -eq 1 ]
  [[ "$output" == *"docs site not found"* ]]
}

@test "dotfiles-doctor reports a missing repo when none can be resolved" {
  cd "$NONREPO"
  run env DOTFILES="$NONREPO/nope" HOME="$NONREPO" zsh -c \
    "fpath=('$FUNCDIR' \$fpath); autoload -Uz '$FUNCDIR'/*(N:t); dotfiles-doctor"
  [ "$status" -eq 1 ]
  [[ "$output" == *"dotfiles repo not found"* ]]
}

@test "pubkey on a missing explicit key path reports it and returns 1" {
  zshrun pubkey "$NONREPO/no-such-key.pub"
  [ "$status" -eq 1 ]
  [[ "$output" == *"No such key"* ]]
}

@test "pubkey with an empty key file copies nothing and returns 1" {
  : > "$NONREPO/empty.pub"
  zshrun pubkey "$NONREPO/empty.pub"
  [ "$status" -eq 1 ]
  [[ "$output" == *"no key to copy"* ]]
}

# `uname` is shimmed (via run_zsh_os) so each branch is deterministic on any host.

@test "is_macos is true on Darwin, false on Linux" {
  run_zsh_os Darwin "is_macos"
  [ "$status" -eq 0 ]
  run_zsh_os Linux "is_macos"
  [ "$status" -ne 0 ]
}

@test "is_linux is true on a (non-WSL) Linux kernel, false on Darwin" {
  run_zsh_os Linux "is_linux"
  [ "$status" -eq 0 ]
  run_zsh_os Darwin "is_linux"
  [ "$status" -ne 0 ]
}

@test "is_linux is false under WSL (WSL is reported separately)" {
  local osrel="$NONREPO/osrelease-wsl"
  printf '5.15.0-microsoft-standard-WSL2\n' > "$osrel"
  run_zsh_os Linux "__dotfiles_osrelease='$osrel' is_linux"
  [ "$status" -ne 0 ]
}

@test "is_wsl is false on a non-Linux kernel" {
  run_zsh_os Darwin "is_wsl"
  [ "$status" -ne 0 ]
}

@test "is_wsl detects a Microsoft/WSL kernel marker" {
  local osrel="$NONREPO/osrelease-wsl"
  printf '5.15.0-microsoft-standard-WSL2\n' > "$osrel"
  run_zsh_os Linux "__dotfiles_osrelease='$osrel' is_wsl"
  [ "$status" -eq 0 ]
}

@test "is_wsl rejects a bare-metal Linux kernel" {
  local osrel="$NONREPO/osrelease-plain"
  printf '5.15.0-generic\n' > "$osrel"
  run_zsh_os Linux "__dotfiles_osrelease='$osrel' is_wsl"
  [ "$status" -ne 0 ]
}

@test "__clipboard_copy pipes stdin to pbcopy on macOS" {
  STUBDIR="$(mktemp -d)"
  printf '#!/bin/sh\ncat > "%s/clip"\n' "$STUBDIR" > "$STUBDIR/pbcopy"
  chmod +x "$STUBDIR/pbcopy"
  run_zsh_os Darwin "printf hello-mac | __clipboard_copy"
  [ "$status" -eq 0 ]
  [ "$(cat "$STUBDIR/clip")" = "hello-mac" ]
  rm -rf "$STUBDIR"; unset STUBDIR
}

@test "__clipboard_copy pipes stdin to a Linux clipboard tool" {
  STUBDIR="$(mktemp -d)"
  printf '#!/bin/sh\ncat > "%s/clip"\n' "$STUBDIR" > "$STUBDIR/xclip"
  chmod +x "$STUBDIR/xclip"
  run_zsh_os Linux "printf hello-linux | __clipboard_copy"
  [ "$status" -eq 0 ]
  [ "$(cat "$STUBDIR/clip")" = "hello-linux" ]
  rm -rf "$STUBDIR"; unset STUBDIR
}

@test "__clipboard_copy reports failure when no clipboard tool exists" {
  # Empty STUBDIR → no pbcopy/clip.exe/wl-copy/xclip/xsel on PATH; the else branch must
  # drain a piped stdin and report failure.
  STUBDIR="$(mktemp -d)"
  run_zsh_os Linux "printf x | __clipboard_copy"
  [ "$status" -ne 0 ]
  rm -rf "$STUBDIR"; unset STUBDIR
}

@test "__os_open opens a URL via open on macOS" {
  STUBDIR="$(mktemp -d)"
  printf '#!/bin/sh\nprintf "%%s" "$*" > "%s/opened"\n' "$STUBDIR" > "$STUBDIR/open"
  chmod +x "$STUBDIR/open"
  run_zsh_os Darwin "__os_open http://localhost:8000"
  [ "$status" -eq 0 ]
  [ "$(cat "$STUBDIR/opened")" = "http://localhost:8000" ]
  rm -rf "$STUBDIR"; unset STUBDIR
}

@test "__os_open opens a URL via xdg-open on Linux" {
  STUBDIR="$(mktemp -d)"
  printf '#!/bin/sh\nprintf "%%s" "$*" > "%s/opened"\n' "$STUBDIR" > "$STUBDIR/xdg-open"
  chmod +x "$STUBDIR/xdg-open"
  run_zsh_os Linux "__os_open http://localhost:8000"
  [ "$status" -eq 0 ]
  [ "$(cat "$STUBDIR/opened")" = "http://localhost:8000" ]
  rm -rf "$STUBDIR"; unset STUBDIR
}

@test "__os_open reports failure when no opener exists" {
  STUBDIR="$(mktemp -d)"
  run_zsh_os Linux "__os_open http://localhost:8000"
  [ "$status" -ne 0 ]
  rm -rf "$STUBDIR"; unset STUBDIR
}

@test "dnsflush flushes via dscacheutil+killall on macOS" {
  STUBDIR="$(mktemp -d)"
  printf '#!/bin/sh\n"$@"\n' > "$STUBDIR/sudo"
  chmod +x "$STUBDIR/sudo"
  printf '#!/bin/sh\nexit 0\n' > "$STUBDIR/dscacheutil"
  chmod +x "$STUBDIR/dscacheutil"
  printf '#!/bin/sh\nexit 0\n' > "$STUBDIR/killall"
  chmod +x "$STUBDIR/killall"
  run_zsh_os Darwin "dnsflush"
  [ "$status" -eq 0 ]
  [[ "$output" == *"DNS cache flushed"* ]]
  rm -rf "$STUBDIR"; unset STUBDIR
}

@test "dnsflush on WSL points at the Windows host and returns 1" {
  local osrel="$NONREPO/osrelease-wsl"
  printf '5.15.0-microsoft-standard-WSL2\n' > "$osrel"
  run_zsh_os Linux "__dotfiles_osrelease='$osrel' dnsflush"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Windows host"* ]]
}
