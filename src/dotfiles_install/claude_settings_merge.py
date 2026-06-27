# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Claude Code settings merge helpers.

Layer the tracked ``claude_settings.json`` baseline with a machine-local overlay to
generate ``~/.claude/settings.json``. ``merge`` and ``diff`` are duals: ``diff`` extracts
the machine-local drift and ``merge(baseline, that delta)`` reproduces the live settings.

Merge rules (matching Claude Code's cross-scope unioning, not jq's array-replace ``*``):

- objects recurse, keys are unioned and never deleted;
- arrays UNION (baseline order, then overlay items not already present), never replace;
- scalars (and any type mismatch) take the overlay value.

Documented limitations carried over from ``scripts/claude_settings_merge.sh``: arrays and
keys can only be added via the overlay, never removed; and a JSON ``null`` is indistinguishable
from "no change" (``None`` is also the diff's no-delta sentinel).

Ported from ``scripts/claude_settings_merge.sh`` (behavior pinned by
``tests/claude_settings.bats``).
"""

from __future__ import annotations

import json

type JSONValue = dict[str, JSONValue] | list[JSONValue] | str | int | float | bool | None


def merge(base: JSONValue, over: JSONValue) -> JSONValue:
    """Deep-merge ``over`` onto ``base``: recurse objects, union arrays, overlay scalars."""
    if isinstance(base, dict) and isinstance(over, dict):
        merged: dict[str, JSONValue] = dict(base)
        for key, value in over.items():
            merged[key] = merge(base[key], value) if key in base else value
        return merged
    if isinstance(base, list) and isinstance(over, list):
        return base + [item for item in over if not _contains(base, item)]
    return over


def diff(base: JSONValue, cur: JSONValue) -> JSONValue:
    """Return the minimal delta such that ``merge(base, delta)`` reproduces ``cur``.

    Always an object (``{}`` when there is no drift), so it is safe to fold into the overlay.
    """
    delta = _diff(base, cur)
    return delta if delta is not None else {}


def is_object(text: str) -> bool:
    """Report whether ``text`` parses as a JSON object.

    The gate the installer applies before trusting the baseline, overlay, or live settings:
    it rejects empty/whitespace and invalid JSON as well as valid-but-non-object JSON
    (arrays, scalars, ``null``) that would otherwise wipe the baseline.
    """
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return False
    return isinstance(value, dict)


def _diff(base: JSONValue, cur: JSONValue) -> JSONValue:
    """Recursive delta helper; returns ``None`` to signal "no change" at this node."""
    if isinstance(base, dict) and isinstance(cur, dict):
        return _diff_dict(base, cur)
    if isinstance(base, list) and isinstance(cur, list):
        extra = [item for item in cur if not _contains(base, item)]
        return extra or None
    return None if _json_equal(base, cur) else cur


def _diff_dict(base: dict[str, JSONValue], cur: dict[str, JSONValue]) -> JSONValue:
    """Delta between two objects: only added keys and changed sub-values; ``None`` if empty."""
    delta: dict[str, JSONValue] = {}
    for key, value in cur.items():
        if key not in base:
            delta[key] = value
            continue
        sub = _diff(base[key], value)
        if sub is not None:
            delta[key] = sub
    return delta or None


def _json_equal(left: JSONValue, right: JSONValue) -> bool:
    """JSON-value equality that distinguishes booleans from numbers (unlike Python ``==``).

    jq treats ``true``/``false`` as a type distinct from ``1``/``0``; plain Python ``==`` does
    not (``True == 1``). Recurse structurally so the distinction holds inside arrays/objects.
    """
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(
            _json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            _json_equal(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def _contains(items: list[JSONValue], needle: JSONValue) -> bool:
    """Membership test using JSON-value equality (so ``true`` is not a duplicate of ``1``)."""
    return any(_json_equal(needle, item) for item in items)
