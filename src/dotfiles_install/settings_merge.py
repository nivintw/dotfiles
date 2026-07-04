# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Baseline ⊕ overlay settings-merge engine.

A tracked baseline JSON file is layered with a machine-local overlay to generate a real
(non-stowed) settings file; live drift beyond the baseline is folded back into the overlay so
per-machine prefs accrue across runs. ``merge`` and ``diff`` are duals: ``diff`` extracts the
machine-local drift and ``merge(baseline, that delta)`` reproduces the live settings.

``merge`` takes an :class:`ArrayMerge` policy so two kinds of consumer can share one core:

- **User settings** (Claude Code, VS Code) merge with :data:`ArrayMerge.UNION` — a machine
  adds one permission/hook without clobbering the baseline list (Claude Code's cross-scope
  unioning, *not* jq's array-replace ``*``). This is the orchestration's only policy, so
  ``diff`` and ``generate_settings`` are UNION-only.
- **MCP server registration** calls ``merge`` directly with :data:`ArrayMerge.REPLACE` — jq
  ``*`` semantics, where a per-server overlay fully redefines a server (its ``args``/``env``
  arrays replace, never union). It does not use ``diff``/``generate_settings``.

Object keys always recurse and union (never deleted); scalars and any type mismatch take the
overlay value, under either policy.

Documented limitations of the merge: arrays and keys can only be added via the overlay, never
removed; and a JSON ``null`` is indistinguishable from "no change" (``None`` is also the diff's
no-delta sentinel).
"""

from __future__ import annotations

import dataclasses
import enum
import json
import os
from typing import TYPE_CHECKING

from dotfiles_install import commands
from dotfiles_install.verify_install import tilde

if TYPE_CHECKING:
    from pathlib import Path

    from dotfiles_install.context import InstallContext

type JSONValue = dict[str, JSONValue] | list[JSONValue] | str | int | float | bool | None


class ArrayMerge(enum.Enum):
    """How two arrays combine when merging an overlay onto a baseline."""

    UNION = "union"  # baseline order, then overlay items not already present (settings)
    REPLACE = "replace"  # the overlay array wins wholesale (MCP / jq `*` semantics)


@dataclasses.dataclass(frozen=True)
class SettingsSpec:
    """A file-backed settings consumer: where its baseline, overlay, and output live.

    Each generated-settings consumer (Claude Code, VS Code) declares one of these and
    ``generate_settings`` does the rest. ``label`` names the consumer in UI messages. Settings
    consumers always UNION arrays, so there is no array-policy field.
    """

    baseline_path: Path
    overlay_path: Path
    output_path: Path
    label: str


# --- Pure merge / diff core --------------------------------------------------------------------


def merge(base: JSONValue, over: JSONValue, *, arrays: ArrayMerge = ArrayMerge.UNION) -> JSONValue:
    """Deep-merge ``over`` onto ``base``: recurse objects, combine arrays per ``arrays``."""
    if isinstance(base, dict) and isinstance(over, dict):
        merged: dict[str, JSONValue] = dict(base)
        for key, value in over.items():
            merged[key] = merge(base[key], value, arrays=arrays) if key in base else value
        return merged
    # UNION appends overlay items not already present; REPLACE falls through to ``return over``.
    if isinstance(base, list) and isinstance(over, list) and arrays is ArrayMerge.UNION:
        return base + [item for item in over if not _contains(base, item)]
    return over


def diff(base: JSONValue, cur: JSONValue) -> JSONValue:
    """Return the minimal delta such that ``merge(base, delta)`` reproduces ``cur`` (UNION).

    For the object roots it is called with, the delta is an object (``{}`` when there is no
    drift), so it is safe to fold into the overlay.
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
    """Recursive UNION delta helper; returns ``None`` to signal "no change" at this node."""
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


# --- Reusable generate orchestration -----------------------------------------------------------


def generate_settings(
    ctx: InstallContext,
    spec: SettingsSpec,
    *,
    extra_overlay: dict[str, JSONValue] | None = None,
) -> None:
    """Generate ``spec.output_path`` from baseline ⊕ overlay (UNION), folding in live drift.

    Consumer-agnostic: ``spec`` declares the paths and ``label`` (named in UI messages).
    ``extra_overlay``, when given, **seeds** any of its keys the overlay doesn't already carry —
    a caller-computed per-machine default (e.g. a resolved tool path) that should persist into
    the machine-local overlay file once, without the caller reading or writing that file
    itself. Seed, not overwrite: a key already present (from a prior seed, or a hand-edit) is
    left alone, so a later run re-deriving a different value never silently reverts it.
    Warn-and-continue throughout so one consumer's failure never aborts the run.
    """
    # Read via the degrade-to-empty helper so a missing/unreadable tracked baseline routes to the
    # same warn-skip path as a non-object one, rather than crashing the phase with an OSError.
    baseline_text = commands.read_text_or_empty(spec.baseline_path)
    if not is_object(baseline_text):
        ctx.ui.warn(
            f"{spec.baseline_path.name} is missing or not a JSON object — skipping {spec.label} "
            "generation (fix it and re-run)",
        )
        return
    baseline_json = json.loads(baseline_text)

    current_json = _read_live(ctx, spec.output_path)

    # Compute BOTH outputs before writing either, so a mid-step failure can't desync them. The
    # delta is the live drift beyond the baseline; fold it into the overlay so prefs accrue.
    delta_json = diff(baseline_json, current_json)
    overlay_json = _fold_overlay(ctx, spec.overlay_path, delta_json)
    if extra_overlay and isinstance(overlay_json, dict):
        additions = {key: value for key, value in extra_overlay.items() if key not in overlay_json}
        if additions:
            ctx.ui.detail(f"seeding {spec.label} overlay: {', '.join(sorted(additions))}")
            overlay_json = merge(overlay_json, additions)
    merged_json = merge(baseline_json, overlay_json)

    spec.overlay_path.parent.mkdir(parents=True, exist_ok=True)
    spec.output_path.parent.mkdir(parents=True, exist_ok=True)
    # A write failure (disk full, perms, read-only FS) must not crash the final phase with a
    # traceback that skips the run summary — warn and continue, per the warn-and-continue design.
    try:
        _atomic_write(spec.overlay_path, overlay_json)
    except OSError as exc:
        ctx.ui.warn(f"couldn't write the {spec.label} overlay {tilde(spec.overlay_path)}: {exc}")
        return
    if spec.output_path.is_dir():
        ctx.ui.warn(
            f"refusing to write: {tilde(spec.output_path)} is a directory (remove it and re-run)",
        )
        return
    try:
        _atomic_write(spec.output_path, merged_json)
    except OSError as exc:
        ctx.ui.warn(f"couldn't write {tilde(spec.output_path)}: {exc}")
        return
    ctx.ui.ok(f"{spec.label} written (baseline + machine-local overlay)")


def _read_live(ctx: InstallContext, output_path: Path) -> JSONValue:
    """Return the live output file as a JSON object, or ``{}`` if missing/corrupt/non-object."""
    # output_path.exists() follows the link, so a dangling migration symlink reads as absent.
    if not output_path.exists():
        return {}
    raw = commands.read_text_or_empty(output_path)
    if is_object(raw):
        return json.loads(raw)
    ctx.ui.warn(
        f"existing {tilde(output_path)} isn't a JSON object — ignoring it "
        "(regenerating from baseline + overlay)",
    )
    return {}


def _fold_overlay(ctx: InstallContext, overlay_path: Path, delta_json: JSONValue) -> JSONValue:
    """Fold the live delta into the existing overlay; rebuild from the delta if it's non-object."""
    if not overlay_path.exists():
        return delta_json
    raw = commands.read_text_or_empty(overlay_path)
    if is_object(raw):
        return merge(json.loads(raw), delta_json)
    ctx.ui.warn(
        f"ignoring {tilde(overlay_path)} (not a JSON object) — rebuilding it from the live delta; "
        "fix it and re-run",
    )
    return delta_json


def _atomic_write(path: Path, value: JSONValue) -> None:
    """Write ``value`` as pretty JSON to ``path`` via a temp file + atomic replace.

    Raises ``OSError`` on a write/replace failure after removing the partial temp file, so the
    caller can warn-and-continue without leaving an orphaned ``.tmp.<pid>`` behind.
    """
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    try:
        tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)  # atomic; replaces a leftover real file or dangling symlink
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
