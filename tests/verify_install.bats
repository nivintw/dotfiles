#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Tests for the pure predicates in scripts/verify_install.sh — the path/JSON checks
# the post-install summary is built from. The system probes (brew bundle check, the
# firewall state, the login shell, bioutil) read live machine state and aren't
# unit-testable in isolation, so they're exercised by running the script standalone
# rather than here. These tests pin the logic that's easy to get subtly wrong:
# resolving a symlink target into the repo, rejecting non-object JSON, matching an
# [include] path through ~ expansion, and abbreviating $HOME to ~ for display.
#
# Run:  bats tests/verify_install.bats

setup() {
  LIB="$BATS_TEST_DIRNAME/../scripts/verify_install.sh"
  # shellcheck source=../scripts/verify_install.sh disable=SC1091
  . "$LIB"
  TMP="$(mktemp -d)"
  REPO="$TMP/repo"
  mkdir -p "$REPO"
}

teardown() {
  rm -rf "$TMP"
}

# Install a fake executable named $1 on PATH whose body is $2 (used to stub bioutil).
_fakebin() {
  mkdir -p "$TMP/bin"
  printf '#!/usr/bin/env bash\n%s\n' "$2" > "$TMP/bin/$1"
  chmod +x "$TMP/bin/$1"
  PATH="$TMP/bin:$PATH"
}

# --- vi_symlink_into_repo ---------------------------------------------------

@test "vi_symlink_into_repo: absolute symlink pointing into the repo passes" {
  printf 'x\n' > "$REPO/file"
  ln -s "$REPO/file" "$TMP/link"
  run vi_symlink_into_repo "$TMP/link" "$REPO"
  [ "$status" -eq 0 ]
}

@test "vi_symlink_into_repo: relative symlink pointing into the repo passes" {
  printf 'x\n' > "$REPO/file"
  # Link sits next to the repo dir; target is relative.
  ln -s "repo/file" "$TMP/link"
  run vi_symlink_into_repo "$TMP/link" "$REPO"
  [ "$status" -eq 0 ]
}

@test "vi_symlink_into_repo: a real file (not a symlink) fails" {
  printf 'x\n' > "$TMP/realfile"
  run vi_symlink_into_repo "$TMP/realfile" "$REPO"
  [ "$status" -ne 0 ]
}

@test "vi_symlink_into_repo: a symlink pointing OUTSIDE the repo fails" {
  printf 'x\n' > "$TMP/elsewhere"
  ln -s "$TMP/elsewhere" "$TMP/link"
  run vi_symlink_into_repo "$TMP/link" "$REPO"
  [ "$status" -ne 0 ]
}

@test "vi_symlink_into_repo: a missing path fails" {
  run vi_symlink_into_repo "$TMP/nope" "$REPO"
  [ "$status" -ne 0 ]
}

# --- vi_is_json_object ------------------------------------------------------

@test "vi_is_json_object: a JSON object passes" {
  printf '{"a":1}\n' > "$TMP/o.json"
  run vi_is_json_object "$TMP/o.json"
  [ "$status" -eq 0 ]
}

@test "vi_is_json_object: a JSON array fails (must be an object)" {
  printf '[1,2,3]\n' > "$TMP/a.json"
  run vi_is_json_object "$TMP/a.json"
  [ "$status" -ne 0 ]
}

@test "vi_is_json_object: a non-object scalar fails" {
  printf '42\n' > "$TMP/n.json"
  run vi_is_json_object "$TMP/n.json"
  [ "$status" -ne 0 ]
}

@test "vi_is_json_object: invalid JSON fails" {
  printf '{not json\n' > "$TMP/bad.json"
  run vi_is_json_object "$TMP/bad.json"
  [ "$status" -ne 0 ]
}

@test "vi_is_json_object: a missing file fails" {
  run vi_is_json_object "$TMP/missing.json"
  [ "$status" -ne 0 ]
}

# --- vi_gitconfig_includes --------------------------------------------------

@test "vi_gitconfig_includes: matches an include.path equal to the wanted file" {
  cfg="$TMP/.gitconfig"
  git config -f "$cfg" --add include.path "$TMP/.gitconfig_local"
  run vi_gitconfig_includes "$cfg" "$TMP/.gitconfig_local"
  [ "$status" -eq 0 ]
}

@test "vi_gitconfig_includes: matches through ~ expansion on both sides" {
  cfg="$TMP/.gitconfig"
  # Stored as a literal ~ path, queried as a literal ~ path: both expand to \$HOME.
  # The literal tilde is the whole point of this test, so SC2088 doesn't apply.
  # shellcheck disable=SC2088
  git config -f "$cfg" --add include.path '~/.gitconfig_local'
  # shellcheck disable=SC2088
  run vi_gitconfig_includes "$cfg" '~/.gitconfig_local'
  [ "$status" -eq 0 ]
}

@test "vi_gitconfig_includes: no matching include fails" {
  cfg="$TMP/.gitconfig"
  git config -f "$cfg" --add include.path "$TMP/.some_other_file"
  run vi_gitconfig_includes "$cfg" "$TMP/.gitconfig_local"
  [ "$status" -ne 0 ]
}

@test "vi_gitconfig_includes: a config with no includes at all fails" {
  cfg="$TMP/.gitconfig"
  git config -f "$cfg" --add core.pager delta
  run vi_gitconfig_includes "$cfg" "$TMP/.gitconfig_local"
  [ "$status" -ne 0 ]
}

@test "vi_gitconfig_includes: a missing config file fails" {
  run vi_gitconfig_includes "$TMP/nope" "$TMP/.gitconfig_local"
  [ "$status" -ne 0 ]
}

# --- vi_tilde ---------------------------------------------------------------

@test "vi_tilde: abbreviates a leading \$HOME to ~" {
  run vi_tilde "$HOME/.gitconfig"
  [ "$status" -eq 0 ]
  # The abbreviated literal ~ is exactly what we're asserting; SC2088 doesn't apply.
  # shellcheck disable=SC2088
  [ "$output" = '~/.gitconfig' ]
}

@test "vi_tilde: leaves a path outside \$HOME unchanged" {
  run vi_tilde "/etc/pam.d/sudo_local"
  [ "$output" = "/etc/pam.d/sudo_local" ]
}

# --- vi_touchid_enrolled_count ----------------------------------------------

@test "vi_touchid_enrolled_count: sums enrolled templates from bioutil output" {
  _fakebin bioutil 'printf "User 501:\t2 biometric template(s)\nOperation performed successfully.\n"'
  run vi_touchid_enrolled_count
  [ "$status" -eq 0 ]
  [ "$output" = "2" ]
}

@test "vi_touchid_enrolled_count: reports 0 for an enrolled count of zero" {
  _fakebin bioutil 'printf "User 501:\t0 biometric template(s)\n"'
  run vi_touchid_enrolled_count
  [ "$status" -eq 0 ]
  [ "$output" = "0" ]
}

@test "vi_touchid_enrolled_count: 0 (no abort) when bioutil output does not match — under set -euo pipefail" {
  # The regression: a non-matching first grep exits 1, which under the caller's
  # pipefail would propagate and abort. Reproduce the exact caller context.
  _fakebin bioutil 'printf "no biometric data on this Mac\n"'
  run bash -c "set -euo pipefail; . '$LIB'; printf '%s' \"\$(vi_touchid_enrolled_count)\""
  [ "$status" -eq 0 ]
  [ "$output" = "0" ]
}

@test "vi_touchid_enrolled_count: 0 when bioutil is absent" {
  # Point PATH at an empty dir so bioutil can't be found.
  mkdir -p "$TMP/empty"
  PATH="$TMP/empty" run vi_touchid_enrolled_count
  [ "$status" -eq 0 ]
  [ "$output" = "0" ]
}

# --- verify_install record format -------------------------------------------

@test "verify_install: emits tab-separated OK/BAD records" {
  # Run against the real repo; we don't assert pass/fail of system probes, only
  # that every line is a well-formed OK<TAB>… or BAD<TAB>… record.
  run verify_install "$BATS_TEST_DIRNAME/.."
  [ "$status" -eq 0 ]
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    printf '%s\n' "$line" | grep -qE '^(OK|BAD)'$'\t''.+'
  done <<< "$output"
}
