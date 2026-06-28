# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Pure parser: print the third-party taps DECLARED in a Brewfile, one per line.
#
# Homebrew refuses to load formulae/casks from an untrusted tap, which aborts
# `brew bundle` on a clean machine. install.sh trusts a Brewfile's taps before
# bundling from it (see _trust_brewfile_taps there); this is the static text parse
# that finds them. No brew, no network, no side effects — sourcing only defines the
# function — so it's unit-tested by tests/brewfile_taps.bats and kept bash 3.2-safe.
#
# A Brewfile tap line looks like:
#     tap "owner/name"                       # a comment
#     tap "owner/name", "https://host/url"   # explicit clone URL
# Only the FIRST quoted argument (the tap name) is emitted; the optional second arg
# (clone URL) and any trailing comment are ignored, and commented-out lines (the first
# non-blank character is #) are skipped.

brewfile_taps() {
  file="${1:?usage: brewfile_taps <brewfile>}"
  [ -f "$file" ] || return 0
  # ^[space]* tap [space]+ "(...)"  — anchoring on `tap` as the first token excludes
  # commented-out lines (which start with #) and `untap`/other directives; the capture
  # stops at the first closing quote, so a trailing ", \"url\"" or comment is dropped.
  sed -nE 's/^[[:space:]]*tap[[:space:]]+"([^"]+)".*/\1/p' "$file"
}

# --- standalone entrypoint --------------------------------------------------
# Only runs when executed directly (bash scripts/brewfile_taps.sh <brewfile>), not when
# sourced by install.sh. Sourcing has NO side effects — it only defines the function.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  set -euo pipefail
  brewfile_taps "$@" # the function's own ${1:?} prints the usage error when no arg is given
fi
