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

# Source one function file and run the function, capturing stdout+stderr+status. The
# functions dir is also put on $fish_function_path so any shared helper the function calls
# (is_macos/is_linux/is_wsl, __clipboard_copy, __os_open) autoloads instead of being an
# "unknown command".
fishrun() {
  local func="$1"; shift
  run fish -c "set -p fish_function_path '$FUNCDIR'; source '$FUNCDIR/$func.fish'; $func $*"
}

# Run a fish snippet with the functions dir autoloadable and `uname` reporting $1, so the
# OS helpers (is_macos/is_linux/is_wsl) take a deterministic branch on any host. A test that
# wants to control which tool a helper dispatches to sets $STUBDIR (a dir of fake binaries);
# it is prepended to PATH so its stubs win over the real ones. coreutils (/usr/bin:/bin) stay
# on PATH so is_wsl's `cat` and the stubs' own `cat`/`exec` resolve. --no-config skips conf.d
# so unrelated startup files can't perturb the result.
run_fish_os() {
  local os="$1"; shift
  UNAMESHIM="$(mktemp -d)"
  printf '#!/bin/sh\necho %s\n' "$os" > "$UNAMESHIM/uname"
  chmod +x "$UNAMESHIM/uname"
  local fishbin; fishbin="$(dirname "$(command -v fish)")"
  run env PATH="${STUBDIR:+$STUBDIR:}$UNAMESHIM:$fishbin:/usr/bin:/bin" fish --no-config -c \
    "set -p fish_function_path '$FUNCDIR'; $*"
  rm -rf "$UNAMESHIM"
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
  # Function path set so the emit helper's __clipboard_copy (a separate autoload file) resolves.
  run fish -c "set -p fish_function_path '$FUNCDIR'; source '$FUNCDIR/pubkey.fish'; pubkey"
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

# With no repo, no $DOTFILES, and no ~/dotfiles under an overridden HOME, the dotfiles repo
# can't be resolved — dotfiles-doctor must report that rather than silently run nothing.
@test "dotfiles-doctor reports a missing repo when none can be resolved" {
  run env HOME="$NONREPO" DOTFILES="" fish -c "cd '$NONREPO'; source '$FUNCDIR/dotfiles-doctor.fish'; dotfiles-doctor"
  [ "$status" -eq 1 ]
  [[ "$output" == *"dotfiles repo not found"* ]]
}

# launch-docs opens the browser from a backgrounded readiness poll, gated on the
# port actually accepting connections. Stubs drive that branch without a real server,
# browser, or TTY: `nc` decides readiness, `open` records that it was invoked, `python3`
# stands in for the foreground http.server — it "serves" until we kill it (recording its
# pid first), exactly like the real server runs until Ctrl-C — and `sleep` is a no-op so
# the poll loop never stalls. We launch fish in the background, wait for the poll to act,
# then stop the "server" and the shell ourselves. Run from the repo root so the docs dir
# resolves via `git rev-parse --show-toplevel`.
launchdocs_shims() {
  SHIM="$(mktemp -d)"
  OPENLOG="$SHIM/open.log"
  # launch-docs opens via __os_open, which dispatches to open (macOS), xdg-open (Linux), or
  # wslview (WSL). Shim all three to the same log so the test asserts "the browser was opened"
  # regardless of which host runs it (macOS dev box vs. the ubuntu CI runner).
  for opener in open xdg-open wslview; do
    printf '#!/bin/sh\nprintf "OPENED %%s\\n" "$*" >> "%s"\n' "$OPENLOG" > "$SHIM/$opener"
    chmod +x "$SHIM/$opener"
  done
  printf '#!/bin/sh\necho $$ > "%s/server.pid"\nexec /bin/sleep 30\n' "$SHIM" > "$SHIM/python3"
  printf '#!/bin/sh\nexit 0\n' > "$SHIM/sleep"
  chmod +x "$SHIM/python3" "$SHIM/sleep"
}

# Start the stubbed function in the background and return once `open` has fired or the
# grace period (~3s) elapses, then stop the foreground "server" and the shell.
run_launchdocs_stubbed() {
  cd "$BATS_TEST_DIRNAME/.." || return 1
  # Close fd 3 (bats' trace fd): a backgrounded process that inherits it makes bats
  # hang at end-of-test waiting for the fd to close.
  env PATH="$SHIM:$PATH" fish -c "set -p fish_function_path '$FUNCDIR'; source '$FUNCDIR/launch-docs.fish'; launch-docs" >/dev/null 2>&1 3>&- &
  LD_PID=$!
  for _ in $(seq 30); do
    if [ -f "$OPENLOG" ]; then break; fi
    sleep 0.1
  done
  # The foreground "server" always runs and records its pid (open may fire before it
  # does, so wait for the pid file too); kill it and the shell so nothing is orphaned.
  for _ in $(seq 20); do
    if [ -f "$SHIM/server.pid" ]; then break; fi
    sleep 0.1
  done
  if [ -f "$SHIM/server.pid" ]; then kill "$(cat "$SHIM/server.pid")" 2>/dev/null || true; fi
  kill "$LD_PID" 2>/dev/null || true
  wait "$LD_PID" 2>/dev/null || true
}

@test "launch-docs opens the browser once the port accepts connections" {
  launchdocs_shims
  # First nc call is the preflight (must report the port FREE → non-zero so we proceed);
  # every later call is the readiness poll (READY → zero), so `open` fires on attempt 1.
  # shellcheck disable=SC2016  # $-expressions are the generated script's, not ours to expand
  printf '#!/bin/sh\nc="%s/nc.n"\nn=$(cat "$c" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$c"\n[ "$n" -ge 2 ]\n' "$SHIM" > "$SHIM/nc"
  chmod +x "$SHIM/nc"
  run_launchdocs_stubbed
  [ -f "$OPENLOG" ]
  [[ "$(cat "$OPENLOG")" == *"http://localhost:8000"* ]]
  rm -rf "$SHIM"
}

@test "launch-docs never opens the browser if the port never accepts connections" {
  launchdocs_shims
  printf '#!/bin/sh\nexit 1\n' > "$SHIM/nc"   # preflight passes (port free); poll never ready
  chmod +x "$SHIM/nc"
  run_launchdocs_stubbed
  [ ! -f "$OPENLOG" ]   # `open` was never invoked — no browser at a dead port
  rm -rf "$SHIM"
}

# --- OS-detection helpers (is_macos / is_linux / is_wsl) -----------------------------------
# These mirror src/dotfiles_install/os_detect.py and gate the cross-platform bridges below.
# `uname` is shimmed (via run_fish_os) so each branch is deterministic on any host. The
# positive WSL case needs a real Microsoft/WSL kernel marker and is verified manually.

@test "is_macos is true on Darwin, false on Linux" {
  run_fish_os Darwin "is_macos"
  [ "$status" -eq 0 ]
  run_fish_os Linux "is_macos"
  [ "$status" -eq 1 ]
}

@test "is_linux is true on a (non-WSL) Linux kernel, false on Darwin" {
  run_fish_os Linux "is_linux"
  [ "$status" -eq 0 ]
  run_fish_os Darwin "is_linux"
  [ "$status" -eq 1 ]
}

@test "is_linux is false under WSL (WSL is reported separately)" {
  osrel="$(mktemp)"; printf '5.15.0-microsoft-standard-WSL2\n' > "$osrel"
  run_fish_os Linux "set -gx __dotfiles_osrelease '$osrel'; is_linux"
  [ "$status" -eq 1 ]
  rm -f "$osrel"
}

@test "is_wsl is false on a non-Linux kernel" {
  run_fish_os Darwin "is_wsl"
  [ "$status" -eq 1 ]
}

# The detection heart — the osrelease marker match — is exercised via the $__dotfiles_osrelease
# seam (fixture file), so it's covered on any host instead of needing a real WSL kernel.
@test "is_wsl detects a Microsoft/WSL kernel marker" {
  osrel="$(mktemp)"; printf '5.15.167.4-microsoft-standard-WSL2\n' > "$osrel"
  run_fish_os Linux "set -gx __dotfiles_osrelease '$osrel'; is_wsl"
  [ "$status" -eq 0 ]
  rm -f "$osrel"
}

@test "is_wsl rejects a bare-metal Linux kernel" {
  osrel="$(mktemp)"; printf '6.8.0-generic\n' > "$osrel"
  run_fish_os Linux "set -gx __dotfiles_osrelease '$osrel'; is_wsl"
  [ "$status" -eq 1 ]
  rm -f "$osrel"
}

# --- __clipboard_copy: pbcopy / clip.exe / wl-copy / xclip dispatch ------------------------

@test "__clipboard_copy pipes stdin to pbcopy on macOS" {
  STUBDIR="$(mktemp -d)"
  printf '#!/bin/sh\ncat > "%s/clip"\n' "$STUBDIR" > "$STUBDIR/pbcopy"
  chmod +x "$STUBDIR/pbcopy"
  run_fish_os Darwin "printf hello-mac | __clipboard_copy"
  [ "$status" -eq 0 ]
  [ "$(cat "$STUBDIR/clip")" = "hello-mac" ]
  rm -rf "$STUBDIR"; unset STUBDIR
}

@test "__clipboard_copy pipes stdin to a Linux clipboard tool" {
  STUBDIR="$(mktemp -d)"
  # Shim every Linux clipboard tool to one sink, so the test asserts "stdin reached the
  # clipboard" without depending on which (wl-copy vs xclip vs xsel) the helper picks.
  for tool in wl-copy xclip xsel; do
    printf '#!/bin/sh\ncat > "%s/clip"\n' "$STUBDIR" > "$STUBDIR/$tool"
    chmod +x "$STUBDIR/$tool"
  done
  run_fish_os Linux "printf hello-linux | __clipboard_copy"
  [ "$status" -eq 0 ]
  [ "$(cat "$STUBDIR/clip")" = "hello-linux" ]
  rm -rf "$STUBDIR"; unset STUBDIR
}

@test "__clipboard_copy reports failure when no clipboard tool exists" {
  # Empty STUBDIR → no pbcopy/clip.exe/wl-copy/xclip/xsel on PATH; the else branch must drain
  # the piped stdin and return non-zero (the contract pubkey relies on for its honest report).
  STUBDIR="$(mktemp -d)"
  run_fish_os Linux "printf x | __clipboard_copy"
  [ "$status" -ne 0 ]
  rm -rf "$STUBDIR"; unset STUBDIR
}

# --- __os_open: open / xdg-open / wslview dispatch ----------------------------------------

@test "__os_open opens a URL via open on macOS" {
  STUBDIR="$(mktemp -d)"
  printf '#!/bin/sh\nprintf "%%s" "$*" > "%s/opened"\n' "$STUBDIR" > "$STUBDIR/open"
  chmod +x "$STUBDIR/open"
  run_fish_os Darwin "__os_open http://localhost:8000"
  [ "$status" -eq 0 ]
  [ "$(cat "$STUBDIR/opened")" = "http://localhost:8000" ]
  rm -rf "$STUBDIR"; unset STUBDIR
}

@test "__os_open opens a URL via xdg-open on Linux" {
  STUBDIR="$(mktemp -d)"
  printf '#!/bin/sh\nprintf "%%s" "$*" > "%s/opened"\n' "$STUBDIR" > "$STUBDIR/xdg-open"
  chmod +x "$STUBDIR/xdg-open"
  run_fish_os Linux "__os_open http://localhost:8000"
  [ "$status" -eq 0 ]
  [ "$(cat "$STUBDIR/opened")" = "http://localhost:8000" ]
  rm -rf "$STUBDIR"; unset STUBDIR
}

@test "__os_open reports failure when no opener exists" {
  # Empty STUBDIR + a non-WSL osrelease → no open/xdg-open/wslview; the no-handler branch must
  # return non-zero so callers (launch-docs, the editor fallback) can react instead of hanging.
  STUBDIR="$(mktemp -d)"
  osrel="$STUBDIR/osrelease"; printf '6.8.0-generic\n' > "$osrel"
  run_fish_os Linux "set -gx __dotfiles_osrelease '$osrel'; __os_open http://localhost:8000"
  [ "$status" -ne 0 ]
  rm -rf "$STUBDIR"; unset STUBDIR
}

# --- dnsflush: macOS dscacheutil vs Linux systemd-resolved --------------------------------

@test "dnsflush flushes via resolvectl on a (non-WSL) Linux box that has it" {
  STUBDIR="$(mktemp -d)"
  osrel="$STUBDIR/osrelease"; printf '6.8.0-generic\n' > "$osrel"   # bare-metal, not WSL
  printf '#!/bin/sh\nexec "$@"\n' > "$STUBDIR/sudo"                 # run the wrapped command directly
  printf '#!/bin/sh\necho ran > "%s/ran"\n' "$STUBDIR" > "$STUBDIR/resolvectl"
  chmod +x "$STUBDIR/sudo" "$STUBDIR/resolvectl"
  run_fish_os Linux "set -gx __dotfiles_osrelease '$osrel'; dnsflush"
  [ "$status" -eq 0 ]
  [[ "$output" == *"systemd-resolved"* ]]
  [ -f "$STUBDIR/ran" ]   # resolvectl was actually invoked, not merely claimed (non-vacuous)
  rm -rf "$STUBDIR"; unset STUBDIR
}

@test "dnsflush defers to the Windows host on WSL, without touching resolvectl" {
  STUBDIR="$(mktemp -d)"
  osrel="$STUBDIR/osrelease"; printf '5.15.0-microsoft-standard-WSL2\n' > "$osrel"
  # resolvectl present, yet WSL must NOT flush it — DNS is the Windows host's job.
  printf '#!/bin/sh\nexec "$@"\n' > "$STUBDIR/sudo"
  printf '#!/bin/sh\necho ran > "%s/ran"\n' "$STUBDIR" > "$STUBDIR/resolvectl"
  chmod +x "$STUBDIR/sudo" "$STUBDIR/resolvectl"
  run_fish_os Linux "set -gx __dotfiles_osrelease '$osrel'; dnsflush"
  [ "$status" -eq 1 ]
  [[ "$output" == *"Windows host"* ]]
  [ ! -f "$STUBDIR/ran" ]   # resolvectl must not have run
  rm -rf "$STUBDIR"; unset STUBDIR
}
