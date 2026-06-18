#!/usr/bin/env bash
# Whole-project type check at turn end, only when Python changed this session.
#
# Stop hook. `ty` is fast (Rust) but cross-file, so running it once after edits
# settle avoids the transient type errors a per-edit run would surface mid
# multi-file change. Exits 2 (errors on stderr) so Claude addresses them.
set -uo pipefail

input=$(cat)

# Don't re-block on a turn that this hook itself triggered (avoids loops).
if [ "$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null)" = "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# Detect Python changes via git. Test for non-empty output rather than parsing
# names, which sidesteps porcelain's quoting of unusual paths; and surface a git
# failure (exit 1) instead of silently treating it as "nothing changed".
if ! tracked=$(git diff --name-only HEAD -- '*.py' 2>/dev/null) ||
  ! untracked=$(git ls-files --others --exclude-standard -- '*.py' 2>/dev/null); then
  echo "typecheck-touched: git query failed; skipping type check" >&2
  exit 1
fi

# Skip unless a Python file was changed (tracked) or added (untracked).
[ -n "$tracked$untracked" ] || exit 0

if ! output=$(uv run ty check . 2>&1); then
  printf 'ty type-check failed:\n\n%s' "$output" >&2
  exit 2
fi
exit 0
