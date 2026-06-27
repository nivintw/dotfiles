#!/usr/bin/env bash
# Report lint/format issues for the single file just edited, dispatched by
# extension using fast per-file tools — the "lint on save" loop.
#
# PostToolUse hook on Edit|Write|MultiEdit. Report-only: it never mutates the file
# (auto-fixing here would desync Claude's view of it); findings go to stderr with
# exit 2 so Claude fixes them. Whole-project `ty` is deferred to the Stop hook.
set -uo pipefail

input=$(cat)
f=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
{ [ -n "$f" ] && [ -f "$f" ]; } || exit 0

# Lint-on-save is project-scoped: only act on files inside the repo. Files edited
# elsewhere (e.g. Claude's auto-memory under ~/.claude/projects/.../memory) aren't
# project content, and the linters resolve their config from the file's own tree —
# not this repo's .rumdl.toml — so checking them just surfaces rules the project
# has turned off (MD013, etc.). Skip anything not under the project root. Only
# enforce this when CLAUDE_PROJECT_DIR is known; if it's unset (a bare harness)
# fall through to the original behavior rather than hard-failing.
if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
  case "$f" in
  "$CLAUDE_PROJECT_DIR"/*) ;;
  *) exit 0 ;;
  esac
fi

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

findings=""
check() {
  if ! command -v "$1" >/dev/null 2>&1; then
    # A missing tool is a setup gap, not a lint finding — warn, don't fail the
    # file (otherwise "ruff: command not found" gets fed back as something to fix).
    printf '%s not found on PATH; skipping its check (install it to enable)\n' "$1" >&2
    return
  fi
  local output
  if ! output=$("$@" 2>&1); then
    findings+="\$ $*"$'\n'"$output"$'\n\n'
  fi
}

case "$f" in
*.py)
  check ruff check "$f"
  check ruff format --check "$f"
  ;;
*.toml) check taplo format --check "$f" ;;
*.md) check rumdl check "$f" ;;
*.fish)
  check fish -n "$f"
  check fish_indent --check "$f"
  ;;
*.sh) check shellcheck -s bash -x "$f" ;;
*) exit 0 ;;
esac

if [ -n "$findings" ]; then
  printf 'Lint findings for %s (fix before continuing):\n\n%s' "$f" "$findings" >&2
  exit 2
fi
exit 0
