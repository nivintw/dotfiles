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

# Skip unless there are uncommitted Python changes (tracked or new).
git status --porcelain --untracked-files=all 2>/dev/null | grep -qE '\.py$' || exit 0

if ! output=$(uv run ty check . 2>&1); then
  printf 'ty type-check failed:\n\n%s' "$output" >&2
  exit 2
fi
exit 0
