#!/usr/bin/env bats
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Template synced-files test: every file the copier template renders must be byte-identical
# to the repo's copy UNLESS the divergence is documented in tests/template-divergences.txt.
# This is the machine-checkable half of the template seam — without it, edits to
# template-owned files accumulate silently and every `copier update` becomes archaeology.
#
# The template is jinja-heavy, so raw-tree byte comparison would be meaningless: the test
# RENDERS it with copier at the pinned _commit, using this repo's own recorded answers
# (underscore-prefixed metadata keys stripped — copier rejects them as data), then walks the
# rendered tree. The candidate set is therefore derived, never hand-curated: a file the
# template stops shipping simply drops out, and a file it starts shipping is checked
# automatically on the first run after a `copier update` bumps _commit.
#
# Rendering needs the network (git clone of the template) and uvx (copier). When either is
# unavailable the test SKIPS rather than fails — offline development must not go red — but
# CI always has both, so drift cannot slip through the gate.

setup() {
  REPO_ROOT="$(cd "$BATS_TEST_DIRNAME/.." && pwd)"
  REGISTRY="$REPO_ROOT/tests/template-divergences.txt"
  ANSWERS="$REPO_ROOT/.copier-answers.yml"

  SRC="$(sed -n 's/^_src_path: *//p' "$ANSWERS")"
  COMMIT="$(sed -n 's/^_commit: *//p' "$ANSWERS")"
  [ -n "$SRC" ] && [ -n "$COMMIT" ] || {
    echo "cannot read _src_path/_commit from .copier-answers.yml" >&2
    return 1
  }

  # Copier's gh: shorthand -> a cloneable URL (for the reachability probe below).
  case "$SRC" in
  gh:*) CLONE_URL="https://github.com/${SRC#gh:}.git" ;;
  *) CLONE_URL="$SRC" ;;
  esac

  WORK="$(mktemp -d)"
}

teardown() {
  rm -rf "$WORK"
}

# True if $1 (repo-relative path) is listed in the registry. The path is matched literally
# against each line's first field — never as a regex (paths contain '.' etc.).
is_registered_divergence() {
  awk -v want="$1" '!/^[[:space:]]*#/ && NF && $1 == want { hit = 1 } END { exit hit ? 0 : 1 }' \
    "$REGISTRY" 2>/dev/null
}

@test "template-rendered files match the repo unless a divergence is registered" {
  command -v uvx >/dev/null 2>&1 || skip "uvx not available"
  git ls-remote --exit-code "$CLONE_URL" HEAD >/dev/null 2>&1 ||
    skip "template repo unreachable (offline?)"

  # Copier data = the recorded answers minus the underscore-prefixed metadata keys.
  sed '/^_/d' "$ANSWERS" >"$WORK/data.yml"

  # --skip-tasks: the render must not git-init/uv-sync the throwaway tree; --trust is
  # still required because the template declares tasks at all.
  run uvx copier copy --force --defaults --trust --skip-tasks \
    --vcs-ref "$COMMIT" --data-file "$WORK/data.yml" "$SRC" "$WORK/render"
  [ "$status" -eq 0 ] || {
    echo "copier render failed:" >&2
    echo "$output" >&2
    return 1
  }

  drift=()
  while IFS= read -r rel; do
    is_registered_divergence "$rel" && continue
    if [ ! -e "$REPO_ROOT/$rel" ]; then
      drift+=("$rel (absent from repo)")
    elif ! diff -q "$WORK/render/$rel" "$REPO_ROOT/$rel" >/dev/null 2>&1; then
      drift+=("$rel")
    fi
  done < <(cd "$WORK/render" && find . -type f ! -path './.git/*' | sed 's|^\./||' | sort)

  [ "${#drift[@]}" -eq 0 ] || {
    printf 'drifted from the template (re-sync, or register in tests/template-divergences.txt): %s\n' "${drift[@]}" >&2
    return 1
  }
}

@test "every registry entry still corresponds to a file the template renders or the repo tracks" {
  # A registry entry pointing at nothing is stale documentation: the divergence it
  # described no longer exists (file re-synced and forgotten, or renamed). Keep the
  # registry honest without needing the network: an entry passes if the path exists
  # in the repo OR is one of the documented deletions (present in the registry with
  # a 'deleted:' reason and absent from the repo by design).
  stale=()
  while IFS= read -r line; do
    case "$line" in \#* | '') continue ;; esac
    path="${line%%[[:space:]]*}"
    reason="${line#"$path"}"
    if [ ! -e "$REPO_ROOT/$path" ]; then
      case "$reason" in
      *deleted:*) ;; # documented deletion — absence is the point
      *) stale+=("$path") ;;
      esac
    fi
  done <"$REGISTRY"
  [ "${#stale[@]}" -eq 0 ] || {
    printf 'registry entry points at a missing file (stale? add a "deleted:" reason or remove it): %s\n' "${stale[@]}" >&2
    return 1
  }
}
