# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Pure filter: print a Brewfile's CORE subset — taps + CLI formulae only, with the GUI-bound
# entries stripped out (app/font casks, VS Code extensions, Mac App Store apps). The --core
# install profile (install.sh) bundles this instead of the full Brewfile, and verify_install
# checks against it, so a headless/minimal install can skip the heavy GUI cask downloads
# (and, with them, the Ollama app + its multi-GB model pull, gated on the ollama CLI a cask
# provides) and the VS Code extensions (which need the VS Code app + `code` CLI to install).
#
# No brew, no network, no side effects — sourcing only defines the function — so it is
# unit-tested by tests/brewfile_core.bats and kept bash 3.2-safe.
#
# "Core" keeps tap and brew lines (and comments) verbatim and drops every other install
# directive: cask, vscode, mas, whalebrew. A commented-out line already starts with # and is
# left as-is (brew bundle ignores it either way).

brewfile_core() {
  file="${1:?usage: brewfile_core <brewfile>}"
  [ -f "$file" ] || return 0
  # Delete lines whose first non-space token is a GUI-bound directive. sed always exits 0
  # (unlike grep -v, which exits 1 for an all-stripped file), so this is safe under set -e.
  sed -E '/^[[:space:]]*(cask|vscode|mas|whalebrew)[[:space:]]/d' "$file"
}

# --- standalone entrypoint --------------------------------------------------
# Only runs when executed directly (bash scripts/brewfile_core.sh <brewfile>), not when
# sourced. Sourcing has NO side effects — it only defines the function.
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  set -euo pipefail
  brewfile_core "${1:?usage: brewfile_core.sh <brewfile>}"
fi
