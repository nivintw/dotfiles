# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Pure helpers for the opt-in Brewfile bundle selection file
# (~/.config/dotfiles/bundles). Sourced by install.sh; unit-tested by
# tests/bundle_select.bats. Sourcing this file has NO side effects — it only
# defines functions. Kept bash 3.2-safe (Apple's /bin/bash runs install.sh
# before brew installs bash 5): no associative arrays, no ${v^^}.
#
# The two functions are inverses: parse_bundles reads back exactly the names
# write_bundles wrote, ignoring the self-documenting header. The round-trip test
# guards that invariant so the writer and reader can't silently drift apart (e.g.
# a change to the comment prefix that the parser no longer skips).

# write_bundles SEL_FILE [AVAIL...] -- [CHOSEN...]
#   Write the self-documenting selection file at SEL_FILE: a header, the available
#   bundle names as commented hints, then the chosen names (bare, one per line).
#   The `--` separates the two variable-length lists so names with spaces survive.
write_bundles() {
  local sel_file="$1"; shift
  local avail=()
  while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do
    avail=(${avail[@]+"${avail[@]}"} "$1"); shift
  done
  [ "${1:-}" = "--" ] && shift   # drop the separator; remaining "$@" = chosen names
  {
    echo '# Opt-in Brewfile bundles for this machine, one name per line. Each maps'
    echo '# to <repo>/Brewfile.d/<name>.brewfile. Lines starting with # are ignored.'
    echo '# Edit and re-run install.sh to change what gets installed.'
    echo '#'
    echo '# Available bundles:'
    local b
    for b in ${avail[@]+"${avail[@]}"}; do echo "#   $b"; done
    echo
    local n
    for n in "$@"; do echo "$n"; done
  } > "$sel_file"
}

# parse_bundles SEL_FILE
#   Emit the chosen bundle names from a selection file, one per line: every line
#   that is neither blank nor a comment. The inverse of write_bundles.
parse_bundles() {
  local line
  while IFS= read -r line; do
    case "$line" in '' | \#*) continue ;; esac
    printf '%s\n' "$line"
  done < "$1"
}

# fzf_preselect_bind AVAIL... -- CHOSEN...
#   Emit an fzf `--bind` expression that pre-selects the CHOSEN names, given the
#   AVAIL names are fed to fzf in this order (positions are 1-based). Prints
#   nothing when there is nothing to pre-select. CHOSEN names absent from AVAIL
#   are skipped, so a stale selection can never wedge the picker. Unit-tested
#   alongside write/parse: the position math is derived from the same menu order
#   install.sh feeds fzf, and the test pins it so the two can't drift apart.
fzf_preselect_bind() {
  local avail=()
  while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do
    avail=(${avail[@]+"${avail[@]}"} "$1"); shift
  done
  [ "${1:-}" = "--" ] && shift   # drop the separator; remaining "$@" = chosen names
  local actions='' name a idx
  for name in "$@"; do
    idx=1
    for a in ${avail[@]+"${avail[@]}"}; do
      if [ "$a" = "$name" ]; then
        actions="${actions}pos($idx)+select+"
        break
      fi
      idx=$((idx + 1))
    done
  done
  # Always return 0: an empty result is the normal "nothing to pre-select" case,
  # and the caller assigns this in a command substitution under `set -e`.
  [ -n "$actions" ] && printf 'start:%s' "${actions%+}"
  return 0
}
