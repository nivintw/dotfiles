# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Phases 12-13: register Claude Code MCP servers and write the user settings.

Phase 12 replays the declarative MCP source of truth into the machine-local ``~/.claude.json``
(idempotent remove-then-add): the tracked ``claude_mcp.json`` baseline is deep-merged with an
optional untracked overlay (overlay wins; objects recurse, else the overlay value replaces —
jq ``*`` semantics, NOT the array-unioning settings merge), then secrets are resolved (1Password
``op inject`` first, else a GitHub PAT from the environment). Any server still carrying an
unresolved ``op://`` reference is **skipped, never registered** — so a token never lands anywhere
but ``~/.claude.json`` (0600).

Phase 13 generates the real (non-stowed) ``~/.claude/settings.json`` by deep-merging the tracked
baseline with the machine-local overlay (arrays UNION here), folding live drift back into the
overlay so per-machine prefs accrue, and writing both files atomically.

Ported from ``install.sh`` phases 12-13.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

from dotfiles_install import commands
from dotfiles_install.claude_settings_merge import diff, is_object, merge
from dotfiles_install.layout import DOTFILES

if TYPE_CHECKING:
    from dotfiles_install.claude_settings_merge import JSONValue
    from dotfiles_install.context import InstallContext

_OP_REF = "op://"  # an unresolved 1Password secret reference marker


def _config_dir() -> Path:
    """Return the machine-private dotfiles config dir (``~/.config/dotfiles``)."""
    return Path.home() / ".config" / "dotfiles"


# --- Phase 12: MCP servers ---------------------------------------------------------------------


def register_mcp_servers(ctx: InstallContext) -> None:
    """Merge, resolve secrets for, and register the MCP servers into the user scope."""
    if commands.which("claude") is None:
        ctx.ui.warn(
            "skipping Claude Code MCP setup (claude CLI not installed — step 11's install "
            "likely failed; re-run install.sh)",
        )
        return
    merged = _merged_mcp(ctx)
    resolved = _resolve_secrets(ctx, merged)
    for name, server in resolved.items():
        _register_one(ctx, name, server)
    ctx.ui.ok("MCP servers registered")


def _merged_mcp(ctx: InstallContext) -> dict[str, JSONValue]:
    """Deep-merge the baseline ``claude_mcp.json`` with the optional machine-local overlay."""
    baseline: dict[str, JSONValue] = json.loads((DOTFILES / "claude_mcp.json").read_text())
    overlay_path = _config_dir() / "claude_mcp.local.json"
    if not overlay_path.is_file():
        return baseline
    overlay = _load_json_object(overlay_path)
    if overlay is None:
        # A malformed/non-object overlay must never wipe the tracked servers — warn and fall
        # back to the baseline only.
        ctx.ui.warn(
            f"ignoring {overlay_path} (not valid JSON) — registering baseline servers only; "
            "fix it and re-run",
        )
        return baseline
    # Top-level merge of two objects is itself an object; recurse per key with the jq-`*` helper.
    merged: dict[str, JSONValue] = dict(baseline)
    for key, value in overlay.items():
        merged[key] = _deep_merge(baseline[key], value) if key in baseline else value
    return merged


def _resolve_secrets(ctx: InstallContext, merged: dict[str, JSONValue]) -> dict[str, JSONValue]:
    """Resolve ``op://`` references: 1Password first, else a GitHub PAT from the environment."""
    if commands.which("op") is not None and commands.run_ok(["op", "whoami"], capture=True):
        injected = commands.run(["op", "inject"], input_text=json.dumps(merged), capture=True)
        if injected.returncode == 0:
            try:
                resolved = json.loads(injected.stdout)
            except json.JSONDecodeError:
                # op inject succeeded but emitted nothing parseable — degrade to the unresolved
                # doc so the per-server op:// guard skips secret servers (bash tolerates this too).
                ctx.ui.warn(
                    "1Password 'op inject' returned no parseable output — skipping "
                    "secret-backed servers; re-run after 'op signin'.",
                )
                return merged
            if isinstance(resolved, dict):
                return resolved
        return merged
    resolved = copy.deepcopy(merged)
    gh_pat = _github_pat()
    if gh_pat:
        # Only rewrite a github auth header that STILL holds an op:// placeholder — never
        # fabricate a server, nor clobber a real token an overlay already supplied.
        github = resolved.get("github")
        if isinstance(github, dict):
            headers = github.get("headers")
            if isinstance(headers, dict) and _OP_REF in str(headers.get("Authorization", "")):
                headers["Authorization"] = f"Bearer {gh_pat}"
                ctx.ui.detail("using a GitHub PAT from the environment for the github MCP server")
    if _OP_REF in json.dumps(resolved):
        ctx.ui.warn(
            "1Password not signed in — skipping secret-backed servers; re-run after "
            "'op signin' or export a GitHub PAT.",
        )
    return resolved


def _register_one(ctx: InstallContext, name: str, server: JSONValue) -> None:
    """Register a single MCP server (remove-then-add), skipping unresolvable/missing ones."""
    server_json = json.dumps(server)
    if _OP_REF in server_json:
        ctx.ui.warn(f"skipping '{name}' (unresolved 1Password reference)")
        return
    # Skip a stdio server whose absolute command path isn't executable here (e.g. the 1password
    # MCP server when the 1Password app isn't installed). http / PATH-resolved servers have no
    # leading '/', so they pass through.
    command = server.get("command") if isinstance(server, dict) else None
    if isinstance(command, str) and command.startswith("/") and not os.access(command, os.X_OK):
        ctx.ui.warn(f"skipping '{name}' (command not found: {command})")
        return
    commands.run(["claude", "mcp", "remove", name, "--scope", "user"], capture=True)
    if not commands.run_ok(
        ["claude", "mcp", "add-json", name, server_json, "--scope", "user"],
        capture=True,
    ):
        ctx.ui.warn(f"failed to register MCP server '{name}' (re-run install.sh to retry)")


def _github_pat() -> str:
    """Return the first non-empty GitHub PAT from the conventional environment variables."""
    for var in ("GITHUB_PERSONAL_ACCESS_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(var)
        if value:
            return value
    return ""


def _deep_merge(base: JSONValue, over: JSONValue) -> JSONValue:
    """Merge ``over`` onto ``base`` with jq ``*`` semantics: recurse objects, else overlay wins.

    Unlike :func:`claude_settings_merge.merge`, arrays are **replaced** (not unioned) — matching
    how ``jq -s '.[0] * .[1]'`` merges the MCP overlay.
    """
    if isinstance(base, dict) and isinstance(over, dict):
        result: dict[str, JSONValue] = dict(base)
        for key, value in over.items():
            result[key] = _deep_merge(base[key], value) if key in base else value
        return result
    return over


# --- Phase 13: user settings -------------------------------------------------------------------


def write_user_settings(ctx: InstallContext) -> None:
    """Generate ``~/.claude/settings.json`` from baseline ⊕ overlay, folding in live drift."""
    baseline_path = DOTFILES / "claude_settings.json"
    if not is_object(baseline_path.read_text()):
        ctx.ui.warn(
            "claude_settings.json is not a JSON object — skipping settings generation "
            "(fix it and re-run)",
        )
        return
    baseline_json = json.loads(baseline_path.read_text())

    overlay_path = _config_dir() / "claude_settings.local.json"
    settings_path = Path.home() / ".claude" / "settings.json"

    current_json = _read_live_settings(ctx, settings_path)

    # Compute BOTH outputs before writing either, so a mid-step failure can't desync them. The
    # delta is the live drift beyond the baseline; fold it into the overlay so prefs accrue.
    delta_json = diff(baseline_json, current_json)
    overlay_json = _fold_overlay(ctx, overlay_path, delta_json)
    merged_json = merge(baseline_json, overlay_json)

    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(overlay_path, overlay_json)
    if settings_path.is_dir():
        ctx.ui.warn(
            "refusing to write: ~/.claude/settings.json is a directory (remove it and re-run)",
        )
        return
    _atomic_write(settings_path, merged_json)
    ctx.ui.ok("Claude settings written (baseline + machine-local overlay)")


def _read_live_settings(ctx: InstallContext, settings_path: Path) -> JSONValue:
    """Return the live settings as a JSON object, or ``{}`` if missing/corrupt/non-object."""
    # settings_path.exists() follows the link, so a dangling migration symlink reads as absent.
    if not settings_path.exists():
        return {}
    raw = _read_text(settings_path)
    if is_object(raw):
        return json.loads(raw)
    ctx.ui.warn(
        "existing ~/.claude/settings.json isn't a JSON object — ignoring it "
        "(regenerating from baseline + overlay)",
    )
    return {}


def _fold_overlay(ctx: InstallContext, overlay_path: Path, delta_json: JSONValue) -> JSONValue:
    """Fold the live delta into the existing overlay; rebuild from the delta if it's non-object."""
    if not overlay_path.exists():
        return delta_json
    raw = _read_text(overlay_path)
    if is_object(raw):
        return merge(json.loads(raw), delta_json)
    ctx.ui.warn(
        f"ignoring {overlay_path} (not a JSON object) — rebuilding it from the live delta; "
        "fix it and re-run",
    )
    return delta_json


def _atomic_write(path: Path, value: JSONValue) -> None:
    """Write ``value`` as pretty JSON to ``path`` via a temp file + atomic replace."""
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)  # atomic; replaces a leftover real file or dangling symlink


def _load_json_object(path: Path) -> dict[str, JSONValue] | None:
    """Parse ``path`` and return it only if it is a JSON object, else ``None``."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _read_text(path: Path) -> str:
    """Read ``path`` as text, returning '' on any read error (bash ``cat ... 2>/dev/null``)."""
    try:
        return path.read_text(encoding="utf-8", errors="surrogateescape")
    except OSError:
        return ""
