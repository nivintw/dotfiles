#!/usr/bin/env bash
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Pre-commit guard: keep the *tracked* SSH config generic and portable.
#
# Concrete hosts (homelab IPs, bastions, work boxes, per-host users) belong in
# the untracked ~/.ssh/config.local, not in the repo. This fails the commit if a
# real host entry sneaks back into home/.ssh/config.
#
# Allowed in the tracked file: comments, blanks, `Include`, global options,
# `Host *`, and `Host github.com` (universal, non-sensitive). Anything else —
# another `Host` pattern; a `HostName`/`User`; a proxy/forward/`Match` directive
# (`ProxyJump`, `ProxyCommand`, `Match`, `LocalForward`, `RemoteForward`,
# `DynamicForward`, `RemoteCommand`); or an IPv4/IPv6 literal — is a finding.
set -euo pipefail

config="home/.ssh/config"
[ -f "$config" ] || exit 0 # nothing to check

violations=()

while IFS= read -r line; do
  # Strip leading whitespace and inline trailing whitespace for matching.
  trimmed="$(printf '%s' "$line" | sed -E 's/^[[:space:]]+//')"

  case "$trimmed" in
  '' | '#'*) continue ;; # blank or comment
  esac

  # Host lines: only `Host *` and `Host github.com` are portable/non-sensitive.
  if printf '%s' "$trimmed" | grep -qiE '^Host[[:space:]]'; then
    if ! printf '%s' "$trimmed" | grep -qiE '^Host[[:space:]]+(\*|github\.com)[[:space:]]*$'; then
      violations+=("concrete Host pattern: $trimmed")
    fi
    continue
  fi

  # Bare IP literals (IPv4 or IPv6). Host lines are handled above; among the
  # remaining (non-Host) lines this runs before the directive match, so an IP in
  # e.g. `ProxyJump 10.0.0.1` is reported as an IP literal, not just a directive.
  if printf '%s' "$trimmed" | grep -qE '(([0-9]{1,3}\.){3}[0-9]{1,3})|(([0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F]{0,4})'; then
    violations+=("IP literal: $trimmed")
    continue
  fi

  # Directives that name — or conditionally select — a concrete machine. Covers
  # jump/proxy hosts and port forwards (whose arg is a concrete host even when it's
  # a hostname, not an IP) plus `Match` blocks (host/user gated).
  if printf '%s' "$trimmed" | grep -qiE '^(HostName|User|ProxyJump|ProxyCommand|Match|LocalForward|RemoteForward|DynamicForward|RemoteCommand)[[:space:]]'; then
    violations+=("machine-specific directive: $trimmed")
    continue
  fi
done <"$config"

if [ "${#violations[@]}" -gt 0 ]; then
  echo "ERROR: $config must stay generic — move concrete hosts to ~/.ssh/config.local" >&2
  printf '  - %s\n' "${violations[@]}" >&2
  exit 1
fi
