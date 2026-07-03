#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT
#
# SessionStart hook: inject the live local-model roster into Claude's context so the
# offload guidance never goes stale — Claude sees what is actually installed, not what
# some prose file remembered. Wired via the `hooks` block in claude_settings.json.
#
# Fail-open by design: on machines without Ollama (or with the server down, or missing
# jq) it prints little or nothing and always exits 0 — a session start must never break
# on an optional integration.
set -u

command -v ollama >/dev/null 2>&1 || exit 0
command -v jq >/dev/null 2>&1 || exit 0
command -v curl >/dev/null 2>&1 || exit 0

installed="$(curl -fsS -m 2 http://localhost:11434/api/tags 2>/dev/null | jq -r '.models[].name' 2>/dev/null)" || installed=""
if [ -z "$installed" ]; then
  echo "Local Ollama: installed but the server is not responding — offload via ollm is unavailable until it starts (open -a Ollama)."
  exit 0
fi

# Resolve the role table from the dotfiles checkout via this script's own stow symlink;
# if that fails (unstowed copy), fall back to listing the raw inventory.
fragment=""
self="$(readlink -f "$0" 2>/dev/null)" || self=""
dir="${self%/*}"
case "$dir" in
*/home/.claude/hooks) fragment="${dir%/home/.claude/hooks}/scripts/ollama_models.sh" ;;
esac

echo "Local Ollama roster (live at session start; offload bulk/mechanical sub-steps via \`ollm\`):"
if [ -n "$fragment" ] && [ -r "$fragment" ]; then
  # shellcheck source=../../../scripts/ollama_models.sh disable=SC1091
  . "$fragment" 2>/dev/null || true
  for pair in \
    "fast ${OLLAMA_MODEL:-}" \
    "bulk ${OLLAMA_MLX_MODEL:-}" \
    "brainstorm ${OLLAMA_BRAINSTORM_MODEL:-}" \
    "vision ${OLLAMA_VISION_MODEL:-}"; do
    role="${pair%% *}"
    model="${pair#* }"
    [ -n "$model" ] || continue
    state="MISSING (pull via install)"
    if printf '%s\n' "$installed" | grep -qxF "$model"; then
      state="installed"
    fi
    printf '  ollm --role %-11s %-38s %s\n' "$role" "$model" "$state"
  done
else
  printf '%s\n' "$installed" | while IFS= read -r line; do printf '  %s\n' "$line"; done
fi
exit 0
