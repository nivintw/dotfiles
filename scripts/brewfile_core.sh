# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Pure filter: print a Brewfile's CORE subset — taps + CLI formulae, with the GUI app and
# font casks stripped out. The --core install profile (install.sh) bundles this instead of
# the full Brewfile, and verify_install checks against it, so a headless/minimal install can
# skip the heavy GUI cask downloads (and, with them, the Ollama app + its multi-GB model
# pull, which is gated on the ollama CLI a cask provides).
#
# No brew, no network, no side effects — sourcing only defines the function — so it is
# unit-tested by tests/brewfile_core.bats and kept bash 3.2-safe.
#
# "Core" == everything EXCEPT `cask "..."` declarations. tap and brew lines (and comments)
# are kept verbatim; only cask lines are dropped. A commented-out cask line already starts
# with # and is left as-is (brew bundle ignores it either way).

brewfile_core() {
  file="${1:?usage: brewfile_core <brewfile>}"
  [ -f "$file" ] || return 0
  # Delete lines whose first non-space token is `cask`. sed always exits 0 (unlike grep -v,
  # which would exit 1 for an all-cask file), so this is safe under the caller's set -e.
  sed -E '/^[[:space:]]*cask[[:space:]]/d' "$file"
}

# --- standalone entrypoint --------------------------------------------------
# Only runs when executed directly (bash scripts/brewfile_core.sh <brewfile>), not when
# sourced. Sourcing has NO side effects — it only defines the function.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  set -euo pipefail
  brewfile_core "${1:?usage: brewfile_core.sh <brewfile>}"
fi
