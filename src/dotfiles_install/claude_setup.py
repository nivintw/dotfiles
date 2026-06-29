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
from typing import TYPE_CHECKING, cast

from dotfiles_install import commands
from dotfiles_install.layout import DOTFILES
from dotfiles_install.settings_merge import ArrayMerge, SettingsSpec, generate_settings, merge

if TYPE_CHECKING:
    from dotfiles_install.context import InstallContext
    from dotfiles_install.settings_merge import JSONValue

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
            f"ignoring {overlay_path} (not a JSON object) — registering baseline servers only; "
            "fix it and re-run",
        )
        return baseline
    # MCP merges with REPLACE (jq `*`) array semantics, NOT the settings consumer's UNION: a
    # per-server overlay must fully redefine that server (its args/env arrays replace, not union).
    merged = merge(baseline, overlay, arrays=ArrayMerge.REPLACE)
    # both inputs are objects, so the merge yields an object (cast for the type checker)
    return cast("dict[str, JSONValue]", merged)


def _resolve_secrets(ctx: InstallContext, merged: dict[str, JSONValue]) -> dict[str, JSONValue]:
    """Resolve ``op://`` references: 1Password first, else a GitHub PAT from the environment."""
    if commands.which("op") is not None and commands.run_ok(["op", "whoami"], capture=True):
        injected = commands.run(["op", "inject"], input_text=json.dumps(merged), capture=True)
        if injected.returncode != 0:
            # op inject failed mid-resolution (locked vault, deleted item, …). Surface why,
            # then degrade to the unresolved doc so the per-server op:// guard skips secrets —
            # without the misleading "unresolved reference" message implying op isn't signed in.
            ctx.ui.warn(
                "1Password 'op inject' failed — skipping secret-backed servers; "
                "re-run after 'op signin'.",
            )
            if injected.stderr.strip():
                ctx.ui.detail(injected.stderr.strip())
            return merged
        try:
            resolved = json.loads(injected.stdout)
        except json.JSONDecodeError:
            # op inject succeeded but emitted nothing parseable — degrade to the unresolved doc
            # so the per-server op:// guard skips secret servers (bash tolerates this too).
            ctx.ui.warn(
                "1Password 'op inject' returned no parseable output — skipping "
                "secret-backed servers; re-run after 'op signin'.",
            )
            return merged
        return resolved if isinstance(resolved, dict) else merged
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
    added = commands.run(
        ["claude", "mcp", "add-json", name, server_json, "--scope", "user"],
        capture=True,
    )
    if added.returncode != 0:
        ctx.ui.warn(f"failed to register MCP server '{name}' (re-run install.sh to retry)")
        if added.stderr.strip():
            ctx.ui.detail(added.stderr.strip())


def _github_pat() -> str:
    """Return the first non-empty GitHub PAT from the conventional environment variables."""
    for var in ("GITHUB_PERSONAL_ACCESS_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(var)
        if value:
            return value
    return ""


# --- Phase 13: user settings -------------------------------------------------------------------


def write_user_settings(ctx: InstallContext) -> None:
    """Generate ``~/.claude/settings.json`` from the Claude baseline ⊕ machine-local overlay."""
    generate_settings(
        ctx,
        SettingsSpec(
            baseline_path=DOTFILES / "claude_settings.json",
            overlay_path=_config_dir() / "claude_settings.local.json",
            output_path=Path.home() / ".claude" / "settings.json",
            label="Claude settings",
        ),
    )


def _load_json_object(path: Path) -> dict[str, JSONValue] | None:
    """Parse ``path`` and return it only if it is a JSON object, else ``None``.

    Reads via ``read_text_or_empty`` (surrogateescape, "" on a missing/unreadable file) so a
    non-UTF-8 overlay degrades to a parse failure (→ ``None`` → warn) instead of crashing the
    MCP phase with an uncaught ``UnicodeDecodeError`` — the same robust read the settings engine
    uses, rather than a second, stricter loader.
    """
    try:
        value = json.loads(commands.read_text_or_empty(path))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None
