# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Behavior tests for the Claude Code settings merge helpers.

Ported from ``tests/claude_settings.bats``. ``merge`` and ``diff`` are duals: ``diff``
extracts exactly the machine-local drift and ``merge(baseline, that delta)`` reproduces
the live settings set-wise. Arrays UNION (a machine adds one permission/hook without
clobbering the baseline list); they never replace.
"""

from __future__ import annotations

import json

from dotfiles_install.claude_settings_merge import JSONValue, diff, is_object, merge

BASE: JSONValue = {
    "permissions": {"allow": ["Bash(git *)", "Read"], "deny": []},
    "theme": "dark",
    "hooks": {
        "PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "shared.sh"}]},
        ],
    },
}


def _norm(value: object) -> object:
    """Normalize for set-wise comparison: sort dict keys and array members."""
    if isinstance(value, dict):
        return {k: _norm(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return sorted((_norm(v) for v in value), key=lambda v: json.dumps(v, sort_keys=True))
    return value


def _assert_roundtrip(cur: JSONValue) -> None:
    """merge(BASE, diff(BASE, cur)) reproduces cur, set-wise."""
    merged = merge(BASE, diff(BASE, cur))
    assert _norm(merged) == _norm(cur)


def test_changed_scalar_round_trips() -> None:
    """A changed scalar (theme) round-trips."""
    _assert_roundtrip(
        {
            "permissions": {"allow": ["Bash(git *)", "Read"], "deny": []},
            "theme": "light",
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "shared.sh"}]},
                ],
            },
        },
    )


def test_new_top_level_key_round_trips() -> None:
    """A new top-level key round-trips."""
    _assert_roundtrip(
        {
            "permissions": {"allow": ["Bash(git *)", "Read"], "deny": []},
            "theme": "dark",
            "effortLevel": "high",
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "shared.sh"}]},
                ],
            },
        },
    )


def test_new_nested_key_round_trips() -> None:
    """A new nested key round-trips."""
    _assert_roundtrip(
        {
            "permissions": {"allow": ["Bash(git *)", "Read"], "deny": [], "defaultMode": "default"},
            "theme": "dark",
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Bash", "hooks": [{"type": "command", "command": "shared.sh"}]},
                ],
            },
        },
    )


def test_added_permission_unions_not_replaces() -> None:
    """The delta carries only the new permission; merge reproduces the unioned list."""
    cur: JSONValue = {
        "permissions": {"allow": ["Bash(git *)", "Read", "Bash(kubectl *)"], "deny": []},
        "theme": "dark",
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "shared.sh"}]},
            ],
        },
    }
    assert diff(BASE, cur) == {"permissions": {"allow": ["Bash(kubectl *)"]}}
    _assert_roundtrip(cur)


def test_added_hook_block_merges_alongside_baseline() -> None:
    """Only the machine-local hook block is extracted into the delta."""
    cur: JSONValue = {
        "permissions": {"allow": ["Bash(git *)", "Read"], "deny": []},
        "theme": "dark",
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "shared.sh"}]},
                {"matcher": "Write", "hooks": [{"type": "command", "command": "local.sh"}]},
            ],
        },
    }
    assert diff(BASE, cur) == {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Write", "hooks": [{"type": "command", "command": "local.sh"}]},
            ],
        },
    }
    _assert_roundtrip(cur)


def test_overlay_is_stable_across_runs() -> None:
    """Current = merge(BASE, overlay); the next run's diff equals the overlay."""
    overlay: JSONValue = {
        "theme": "light",
        "permissions": {"allow": ["Bash(kubectl *)"]},
    }
    current = merge(BASE, overlay)
    assert _norm(diff(BASE, current)) == _norm(overlay)


def test_removing_a_baseline_permission_is_not_expressible() -> None:
    """Documented limitation: arrays union, never delete — the delta is empty."""
    cur: JSONValue = {
        "permissions": {"allow": ["Read"], "deny": []},
        "theme": "dark",
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "shared.sh"}]},
            ],
        },
    }
    delta = diff(BASE, cur)
    assert delta == {}
    assert merge(BASE, delta) == BASE


def test_empty_overlay_reproduces_baseline() -> None:
    """An empty overlay reproduces the baseline exactly."""
    assert _norm(merge(BASE, {})) == _norm(BASE)


def test_is_object_accepts_json_objects() -> None:
    """The gate accepts JSON objects."""
    assert is_object("{}")
    assert is_object('{"a":1}')


def test_is_object_rejects_empty_whitespace_and_invalid() -> None:
    """The gate rejects empty, whitespace-only, and invalid JSON."""
    assert not is_object("")
    assert not is_object("   ")
    assert not is_object("{bad")


def test_is_object_rejects_valid_but_non_object_json() -> None:
    """The gate rejects valid JSON that isn't an object."""
    assert not is_object("[1,2,3]")
    assert not is_object("42")
    assert not is_object("null")
    assert not is_object('"hi"')


def test_merge_distinguishes_bool_from_int() -> None:
    """Array union does not treat JSON ``true`` as a duplicate of ``1`` (jq type semantics)."""
    base: JSONValue = {"flags": [1]}
    over: JSONValue = {"flags": [True]}
    assert merge(base, over) == {"flags": [1, True]}


def test_diff_distinguishes_bool_from_int() -> None:
    """A scalar changing from ``1`` to ``true`` is captured as a delta, not seen as equal."""
    base: JSONValue = {"flag": 1}
    cur: JSONValue = {"flag": True}
    assert diff(base, cur) == {"flag": True}
