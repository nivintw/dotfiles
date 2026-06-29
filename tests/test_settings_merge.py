# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Behavior tests for the generic settings-merge engine.

``merge`` and ``diff`` are duals: ``diff`` extracts exactly the machine-local drift and
``merge(baseline, that delta)`` reproduces the live settings set-wise. The default UNION array
policy lets a machine add one permission/hook without clobbering the baseline list; the REPLACE
policy (MCP / jq ``*``) takes the overlay array wholesale. ``generate_settings`` orchestrates a
baseline ⊕ overlay → output write for any consumer.

The UNION round-trip cases were ported from ``tests/claude_settings.bats`` (the bash twin).
"""

from __future__ import annotations

import io
import json
from typing import TYPE_CHECKING

from rich.console import Console

from dotfiles_install.context import InstallContext
from dotfiles_install.settings_merge import (
    ArrayMerge,
    JSONValue,
    SettingsSpec,
    diff,
    generate_settings,
    is_object,
    merge,
)
from dotfiles_install.ui import UI

if TYPE_CHECKING:
    from pathlib import Path

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


# ── Array policy: UNION vs REPLACE ──────────────────────────────────────────────────────────────


def _ctx() -> InstallContext:
    """An install context over an in-memory console (wide so lines don't wrap)."""
    ui = UI(
        stdout=Console(file=io.StringIO(), width=200),
        stderr=Console(file=io.StringIO(), width=200),
    )
    return InstallContext(ui=ui)


def test_merge_default_policy_is_union() -> None:
    """Omitting ``arrays`` defaults to UNION (the settings consumer's policy)."""
    assert merge({"a": [1]}, {"a": [2]}) == {"a": [1, 2]}


def test_merge_union_vs_replace_arrays() -> None:
    """Policy is the only difference: UNION appends new items, REPLACE takes the overlay array."""
    base: JSONValue = {"a": [1, 2]}
    over: JSONValue = {"a": [2, 3]}
    assert merge(base, over, arrays=ArrayMerge.UNION) == {"a": [1, 2, 3]}
    assert merge(base, over, arrays=ArrayMerge.REPLACE) == {"a": [2, 3]}


def test_merge_replace_recurses_objects_and_overlays_scalars() -> None:
    """REPLACE changes only array handling: objects still recurse, scalars still overlay-win."""
    base: JSONValue = {"srv": {"command": "old", "args": ["--a"], "env": {"X": "1"}}}
    over: JSONValue = {"srv": {"command": "new", "args": ["--b"]}}
    assert merge(base, over, arrays=ArrayMerge.REPLACE) == {
        "srv": {"command": "new", "args": ["--b"], "env": {"X": "1"}},
    }


def test_diff_returns_only_extra_array_items() -> None:
    """Diff carries only the items added to a grown array (UNION)."""
    base: JSONValue = {"args": ["--a", "--b"]}
    cur: JSONValue = {"args": ["--a", "--b", "--c"]}
    assert diff(base, cur) == {"args": ["--c"]}


# ── generate_settings orchestration (consumer-agnostic) ─────────────────────────────────────────


def test_generate_settings_writes_baseline_for_any_consumer(tmp_path: Path) -> None:
    """A non-Claude consumer: baseline + no overlay/live → output == baseline, overlay == {}."""
    baseline = tmp_path / "base.json"
    baseline.write_text(json.dumps({"editor.tabSize": 2}), encoding="utf-8")
    overlay = tmp_path / "over.json"
    output = tmp_path / "out" / "settings.json"

    generate_settings(
        _ctx(),
        SettingsSpec(
            baseline_path=baseline,
            overlay_path=overlay,
            output_path=output,
            label="VS Code settings",
        ),
    )

    assert json.loads(output.read_text()) == {"editor.tabSize": 2}
    assert json.loads(overlay.read_text()) == {}


def test_generate_settings_folds_live_drift_into_overlay(tmp_path: Path) -> None:
    """Live drift beyond the baseline folds into the overlay (prefs accrue) and into the output."""
    baseline = tmp_path / "base.json"
    baseline.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
    overlay = tmp_path / "over.json"
    overlay.write_text(json.dumps({"a": 1}), encoding="utf-8")
    output = tmp_path / "settings.json"
    output.write_text(json.dumps({"theme": "dark", "b": 2}), encoding="utf-8")

    generate_settings(
        _ctx(),
        SettingsSpec(
            baseline_path=baseline,
            overlay_path=overlay,
            output_path=output,
            label="settings",
        ),
    )

    assert json.loads(overlay.read_text()) == {"a": 1, "b": 2}
    assert json.loads(output.read_text()) == {"theme": "dark", "a": 1, "b": 2}
