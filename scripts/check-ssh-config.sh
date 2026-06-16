#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Pre-commit guard: keep the *tracked* SSH config generic and portable.
#
# Concrete hosts (homelab IPs, bastions, work boxes, per-host users) belong in
# the untracked ~/.ssh/config.local, not in the repo. This fails the commit if a
# real host entry sneaks back into home/.ssh/config. See docs/repo-review-*.md S2.
#
# Allowed in the tracked file: comments, blanks, `Include`, global options,
# `Host *`, and `Host github.com` (universal, non-sensitive). Anything else —
# another `Host` pattern, a `HostName`/`Hostname`, a `User`, or an IP literal —
# is a finding.
set -euo pipefail

config="home/.ssh/config"
[ -f "$config" ] || exit 0  # nothing to check

violations=()

while IFS= read -r line; do
  # Strip leading whitespace and inline trailing whitespace for matching.
  trimmed="$(printf '%s' "$line" | sed -E 's/^[[:space:]]+//')"

  case "$trimmed" in
    '' | '#'*) continue ;;  # blank or comment
  esac

  # Host lines: only `Host *` and `Host github.com` are portable/non-sensitive.
  if printf '%s' "$trimmed" | grep -qiE '^Host[[:space:]]'; then
    if ! printf '%s' "$trimmed" | grep -qiE '^Host[[:space:]]+(\*|github\.com)[[:space:]]*$'; then
      violations+=("concrete Host pattern: $trimmed")
    fi
    continue
  fi

  # Per-host specifics that imply a concrete machine.
  if printf '%s' "$trimmed" | grep -qiE '^(HostName|User)[[:space:]]'; then
    violations+=("machine-specific directive: $trimmed")
    continue
  fi

  # Bare IP literals anywhere.
  if printf '%s' "$trimmed" | grep -qE '([0-9]{1,3}\.){3}[0-9]{1,3}'; then
    violations+=("IP literal: $trimmed")
    continue
  fi
done < "$config"

if [ "${#violations[@]}" -gt 0 ]; then
  echo "ERROR: $config must stay generic — move concrete hosts to ~/.ssh/config.local" >&2
  printf '  - %s\n' "${violations[@]}" >&2
  exit 1
fi
