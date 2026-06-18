# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

#
# Pure helpers for layering the tracked Claude Code settings baseline
# (claude_settings.json) with a machine-local overlay
# (~/.config/dotfiles/claude_settings.local.json). Sourced by install.sh (step
# 13) and unit-tested by tests/claude_settings.bats. Sourcing has NO side
# effects — it only defines a jq library and two thin shell wrappers. Kept bash
# 3.2-safe (install.sh runs under Apple's /bin/bash before brew installs bash 5):
# no associative arrays, no ${v^^}.
#
# Why a custom merge instead of jq's built-in `*`: `*` REPLACES arrays wholesale,
# which would make a machine that adds one entry to permissions.allow clobber the
# whole baseline list. Claude Code itself unions permissions across scopes, so we
# match that — `merge` unions arrays (baseline order first, machine extras
# appended, deep-equality dedup). The same union lets a machine append hook
# matcher blocks (hooks.<event> is an array) without dropping the baseline's.
#
# merge and diff are duals: merge(base; diff(base; cur)) reproduces cur (set-wise
# for arrays). The round-trip is what tests/claude_settings.bats pins, so the
# extractor and the merger can't silently drift apart.
#
# Known, deliberate limitations (callers/docs surface these):
#   - Arrays union but never delete: the overlay can ADD a permission/hook, never
#     REMOVE a baseline one. Drop it from the baseline instead.
#   - Keys are never deleted: a baseline key absent from the live file is re-added
#     by the merge. Remove it from the baseline to drop it.
#   - Reverting an overlaid scalar to its exact baseline value via the live file
#     does not auto-prune it from the overlay (the diff sees no change). Remove it
#     from the overlay (or change the baseline) to revert.
#   - A live value of JSON null reads as "no change" (null also serves as diff's
#     no-delta sentinel), so it can't override a baseline scalar.
#   - Emptying an array or sub-object in the live file (e.g. clearing a deny list)
#     reads as no change — the same add-only nature as the array-union rule.
#   - hooks.<event> blocks dedup by deep equality, so a block whose inner array is
#     reordered counts as new and could merge in twice. Claude Code serializes
#     hooks stably, so this is a latent edge, not an observed one.
#
# Inputs MUST be JSON objects. Callers validate with claude_settings_is_object
# before merge/diff — a non-object (array, scalar, null) would fall through the
# `else $over`/`$cur` branches and let merge() discard the baseline wholesale.

# jq library: merge($base; $over) and diff($base; $cur).
#   merge: both objects -> recurse; both arrays -> union ($base + ($over-$base));
#          else -> $over wins (scalar override).
#   diff:  minimal delta s.t. merge($base; delta) == $cur (set-wise). Objects
#          recurse (empty sub-deltas prune to null); arrays -> $cur-$base; scalars
#          -> $cur when changed else null.
# shellcheck disable=SC2016  # $base/$over/$cur are jq variables — must NOT expand in shell.
_CLAUDE_SETTINGS_JQ='
  def merge($base; $over):
    if   ($base|type)=="object" and ($over|type)=="object" then
      reduce (($base|keys_unsorted) + ($over|keys_unsorted) | unique)[] as $k ({};
        if   ($base|has($k)) and ($over|has($k)) then . + {($k): merge($base[$k]; $over[$k])}
        elif ($over|has($k))                     then . + {($k): $over[$k]}
        else                                          . + {($k): $base[$k]} end)
    elif ($base|type)=="array" and ($over|type)=="array" then
      $base + ($over - $base)
    else $over end;
  def diff($base; $cur):
    if   ($base|type)=="object" and ($cur|type)=="object" then
      (reduce ($cur|keys_unsorted[]) as $k ({};
         if ($base|has($k))
         then (diff($base[$k]; $cur[$k])) as $d | (if $d==null then . else . + {($k):$d} end)
         else . + {($k):$cur[$k]} end))
      | (if length==0 then null else . end)
    elif ($base|type)=="array" and ($cur|type)=="array" then
      ($cur - $base) | (if length==0 then null else . end)
    else (if $base==$cur then null else $cur end) end;'

# claude_settings_merge BASE_JSON OVER_JSON -> merged JSON on stdout.
#   Objects recurse, arrays union, scalars overlay-wins.
claude_settings_merge() {
  jq -n --argjson base "$1" --argjson over "$2" \
    "$_CLAUDE_SETTINGS_JQ"' merge($base; $over)'
}

# claude_settings_diff BASE_JSON CUR_JSON -> minimal delta JSON on stdout.
#   Always an object ({} when there is no difference), so it is safe to fold
#   straight into the overlay with claude_settings_merge.
claude_settings_diff() {
  jq -n --argjson base "$1" --argjson cur "$2" \
    "$_CLAUDE_SETTINGS_JQ"' diff($base; $cur) // {}'
}

# claude_settings_is_object JSON_STRING -> exit 0 iff the argument is a JSON
# object. Rejects empty/whitespace input, invalid JSON, and valid-but-non-object
# JSON (arrays, scalars, null) — the inputs that must NOT be trusted as a
# baseline/overlay/live settings document. `jq empty` is insufficient: it accepts
# all of those, after which merge()/diff() would discard the baseline or crash on
# `--argjson ""`.
claude_settings_is_object() {
  printf '%s' "$1" | jq -e 'type == "object"' >/dev/null 2>&1
}
