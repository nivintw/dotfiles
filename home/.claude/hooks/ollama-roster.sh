#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT
#
# SessionStart hook: inject the live local-model roster into Claude's context so the
# offload guidance never goes stale — Claude sees what is actually installed, not what
# some prose file remembered. Wired via the `hooks` block in claude_settings.json.
#
# The roster rendering is delegated to `ollm --list` (the single owner of the
# role→model mapping); this script only locates its stowed sibling and stays
# fail-open: on machines without Ollama (or with the server down) it prints little
# or nothing and always exits 0 — a session start must never break on an optional
# integration.
set -u

command -v ollama >/dev/null 2>&1 || exit 0

# Resolve the sibling ollm from this script's own stow symlink; fall back to PATH.
self="$(readlink -f "$0" 2>/dev/null)" || self=""
dir="${self%/*}"
ollm=""
case "$dir" in
*/home/.claude/hooks) ollm="${dir%/home/.claude/hooks}/home/.local/bin/ollm" ;;
esac
if [ ! -x "$ollm" ]; then
  ollm="$(command -v ollm 2>/dev/null)" || ollm=""
fi
[ -n "$ollm" ] || exit 0

if roster="$("$ollm" --list 2>/dev/null)"; then
  echo "Local Ollama roster (live at session start; offload bulk/mechanical sub-steps via \`ollm\` — see the local-offload skill):"
  printf '%s\n' "$roster" | while IFS= read -r line; do printf '  %s\n' "$line"; done
else
  echo "Local Ollama: installed but not usable for offload right now (server down or fleet unprovisioned) — 'open -a Ollama' to start it, 'ollm --list' for details."
fi
exit 0
