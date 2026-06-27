# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Pure helper for safely adopting an existing ~/.gitconfig when this repo's
# baseline (home/.gitconfig) is about to be stowed over it. Sourced by install.sh
# (step 3, before the stow preflight) and unit-tested by tests/gitconfig_migrate.bats.
# Sourcing has NO side effects — it only defines functions. Kept bash 3.2-safe
# (install.sh runs under Apple's /bin/bash before brew installs bash 5).
#
# Unlike Claude Code's settings.json (no native include → a generated jq merge),
# git layers config natively: the tracked baseline Include-s ~/.gitconfig_local
# last, so the overlay wins per key. The only gap is a FRESH machine that already
# has a real ~/.gitconfig — stow would abort on the conflict (or stomp it). This
# helper closes that gap: it backs the existing file up and folds its contents
# into the overlay, so the user's settings survive AND override the baseline, then
# frees the path for stow to symlink. It's a one-time migration: on later runs (and
# on a machine already managed by this repo) ~/.gitconfig is our symlink, so it's a
# no-op.

# gitconfig_migrate TARGET OVERLAY BASELINE
#   TARGET   = the live ~/.gitconfig path
#   OVERLAY  = the machine-local include, ~/.gitconfig_local
#   BASELINE = this repo's tracked home/.gitconfig
# Behavior:
#   - TARGET is our symlink, or absent       -> nothing to do.
#   - TARGET is a real file == BASELINE       -> remove it (stow will symlink it back).
#   - TARGET is a real file that differs      -> back it up to TARGET.pre-stow.bak[.N]
#                                                (never clobbering an earlier backup),
#                                                then append its contents to OVERLAY.
# Prints one human line describing what it did (caller wraps it for the UI).
gitconfig_migrate() {
  target="$1"
  overlay="$2"
  baseline="$3"

  # Already managed by this repo (symlink) or nothing there: leave it alone.
  if [ -L "$target" ] || [ ! -e "$target" ]; then
    return 0
  fi
  # Only ordinary files are migratable; anything else (dir, socket) is the user's
  # to resolve — let the stow preflight surface it loudly rather than touch it.
  if [ ! -f "$target" ]; then
    return 0
  fi

  # Byte-identical to the baseline: nothing to preserve, just clear the path.
  if cmp -s "$target" "$baseline"; then
    if ! rm -f "$target"; then
      printf 'gitconfig_migrate: could not remove %s\n' "$target" >&2
      return 1
    fi
    printf 'removed %s (identical to the repo baseline)\n' "$target"
    return 0
  fi

  # Differs: preserve it. Pick a backup name without clobbering an earlier run's.
  backup="$target.pre-stow.bak"
  n=1
  while [ -e "$backup" ]; do
    backup="$target.pre-stow.bak.$n"
    n=$((n + 1))
  done

  # Order matters for safety: fold the contents into the overlay BEFORE moving the
  # original aside, so a failed/partial write can never leave the user with the
  # source already gone and nothing migrated. Each mutating step is guarded and
  # reports to stderr (stdout is the result channel) + returns non-zero, so the
  # caller aborts rather than trusting a success line. Drop any [include]/[includeIf]
  # section pointing back at the overlay itself, or git would hit "exceeded maximum
  # include depth" reading the overlay recursively.
  overlay_dir="$(dirname "$overlay")"
  if ! mkdir -p "$overlay_dir"; then
    printf 'gitconfig_migrate: could not create %s (left %s in place)\n' "$overlay_dir" "$target" >&2
    return 1
  fi
  # Build the migrated text first, then append it with a SINGLE simple command:
  # bash reports a redirect-open failure as a simple command's non-zero status, but
  # SWALLOWS it (status 0) for a `{ …; } >> file` group — so a group here would hide
  # an unwritable overlay and silently lose config. The simple `printf … >> overlay`
  # form is what makes the guard real.
  overlay_base="$(basename "$overlay")"
  migrated="$(_gitconfig_strip_self_include "$target" "$overlay_base")"
  if ! printf '\n# --- migrated from %s by install.sh (see %s) ---\n%s\n' \
    "$target" "$backup" "$migrated" >>"$overlay"; then
    printf 'gitconfig_migrate: could not write %s (left %s in place)\n' "$overlay" "$target" >&2
    return 1
  fi
  if ! mv "$target" "$backup"; then
    printf 'gitconfig_migrate: could not back up %s -> %s (its contents are already in %s; original left in place)\n' \
      "$target" "$backup" "$overlay" >&2
    return 1
  fi

  printf 'backed up %s -> %s and migrated its contents into %s\n' \
    "$target" "$backup" "$overlay"
}

# _gitconfig_strip_self_include FILE OVERLAY_BASENAME
#   Emit FILE to stdout, dropping any [include]/[includeIf "..."] section whose
#   `path = ...` resolves to OVERLAY_BASENAME. The path is compared by basename
#   after normalizing the spellings git honors: leading/trailing whitespace, an
#   inline `#`/`;` comment, surrounding double quotes, and ~/$HOME/absolute forms.
#   Sections pointing elsewhere (e.g. a work includeIf) and all non-include content
#   pass through untouched. A section is buffered until the next header (or EOF) so
#   the path can be inspected before we commit to printing the header. (This is a
#   pragmatic normalizer, not a full git-config value parser — the source is the
#   user's own config and the only thing we must catch is a path that resolves to
#   the overlay; anything fancier simply fails safe by being kept.)
_gitconfig_strip_self_include() {
  awk -v ovl="$2" '
    # git section names and keys are case-insensitive, so match on a lowercased
    # copy of each line (and a lowercased overlay basename) — this also keeps the
    # literal pattern made of real words, not a char-class fragment.
    BEGIN { ovl = tolower(ovl) }
    function flush() {
      if (n > 0 && !drop) for (i = 0; i < n; i++) print buf[i]
      n = 0; drop = 0; in_inc = 0
    }
    /^[[:space:]]*\[/ {
      flush()
      if (tolower($0) ~ /^[[:space:]]*\[[[:space:]]*include([[:space:]]|\]|if)/) {
        in_inc = 1; buf[n++] = $0; next
      }
      print; next
    }
    in_inc {
      buf[n++] = $0
      low = tolower($0)
      if (low ~ /^[[:space:]]*path[[:space:]]*=/) {
        sub(/^[[:space:]]*path[[:space:]]*=[[:space:]]*/, "", low)
        sub(/[[:space:]]*[#;].*$/, "", low)   # drop an inline comment
        sub(/[[:space:]]+$/, "", low)         # drop trailing whitespace
        gsub(/^"|"$/, "", low)                # drop surrounding quotes git honors
        sub(/.*\//, "", low)                  # reduce to basename
        if (low == ovl) drop = 1
      }
      next
    }
    { print }
    END { flush() }
  ' "$1"
}
