# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for phases 12-13: MCP server registration and Claude user-settings merge.

Behaviors under test:
  Phase 12 (register_mcp_servers / MCP servers):
    1.  claude CLI absent → warn + return, nothing registered.
    2.  Overlay merge: overlay server added; overlay wins per key; arrays REPLACED (not
        unioned). A malformed overlay → warn "registering baseline servers only", baseline only.
    3.  SECRET LEAK GUARD: server still carrying op:// after resolution is SKIPPED — add-json
        never called; warns "unresolved 1Password reference" AND
        "1Password not signed in — skipping secret-backed servers".
    4.  GitHub PAT fallback: GITHUB_PERSONAL_ACCESS_TOKEN rewrites the github server's
        Authorization to "Bearer <pat>"; that server IS registered; PAT env var precedence.
    5.  op signed in: op inject called with the merged JSON; servers register with resolved
        values; no leftover op:// in any add-json call.
    6.  stdio command existence: non-executable absolute command → skipped + warn "command not
        found"; http server (no command) and executable absolute command → both registered.
    7.  Remove-then-add sequence per server; failed add-json → warn "failed to register MCP".
    8.  Happy path emits ok("MCP servers registered").
  Phase 13 (write_user_settings / Claude settings):
    9.  Baseline not a JSON object → warn + return, nothing written.
    10. Happy path: baseline + no overlay + no live → settings.json == baseline, overlay == {},
        ok("Claude settings written ...").
    11. Live-drift fold: a key in live settings beyond baseline folds into overlay + merged output.
    12. Non-object live settings → warn + regenerate from baseline. Non-object overlay → warn +
        rebuild from live delta.
    13. settings.json is a DIRECTORY → warn "refusing to write … is a directory"; overlay still
        written; the directory itself is untouched.
    14. Atomic write: trailing newline, valid JSON, no leftover .tmp.<pid> files.
"""

from __future__ import annotations

import io
import json
import subprocess
from types import SimpleNamespace
from typing import TYPE_CHECKING

from rich.console import Console

from dotfiles_install import claude_setup, commands
from dotfiles_install.context import InstallContext
from dotfiles_install.ui import UI

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import pytest


# ── shared helpers ────────────────────────────────────────────────────────────────────────────


def _ctx() -> tuple[InstallContext, io.StringIO]:
    """Build an install context over a wide in-memory console (wide so lines don't wrap)."""
    out = io.StringIO()
    ui = UI(
        stdout=Console(file=out, width=200),
        stderr=Console(file=io.StringIO(), width=200),
    )
    return InstallContext(ui=ui), out


# An MCP baseline with the real github server shape (op:// in Authorization).
_GITHUB_MCP: dict = {
    "github": {
        "type": "http",
        "url": "https://api.githubcopilot.com/mcp/",
        "headers": {"Authorization": "Bearer op://MCP/github-claude-pat/credential"},
    }
}

_OP_REF = "op://"
_CLAUDE_MCP_ADD = ["claude", "mcp", "add-json"]
_CLAUDE_MCP_REMOVE = ["claude", "mcp", "remove"]


def _fake_run(
    calls: list[SimpleNamespace],
    *,
    op_whoami_ok: bool = False,
    op_inject_json: str | None = None,
    add_json_ok: bool = True,
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Build a commands.run replacement that records calls and answers by argv shape."""

    def run(
        argv: list[str],
        *,
        input_text: str | None = None,
        **_: object,
    ) -> subprocess.CompletedProcess[str]:
        argv = list(argv)
        calls.append(SimpleNamespace(argv=argv, input_text=input_text))
        if argv[:2] == ["op", "whoami"]:
            rc = 0 if op_whoami_ok else 1
            return subprocess.CompletedProcess(argv, rc, stdout="", stderr="")
        if argv[:2] == ["op", "inject"]:
            if op_inject_json is not None:
                return subprocess.CompletedProcess(argv, 0, stdout=op_inject_json, stderr="")
            return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")
        if argv[:3] == _CLAUDE_MCP_ADD:
            rc = 0 if add_json_ok else 1
            return subprocess.CompletedProcess(argv, rc, stdout="", stderr="")
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    return run


def _add_json_calls(calls: list[SimpleNamespace]) -> list[SimpleNamespace]:
    """Return the recorded ``claude mcp add-json`` calls."""
    return [c for c in calls if c.argv[:3] == _CLAUDE_MCP_ADD]


def _remove_calls(calls: list[SimpleNamespace]) -> list[SimpleNamespace]:
    """Return the recorded ``claude mcp remove`` calls."""
    return [c for c in calls if c.argv[:3] == _CLAUDE_MCP_REMOVE]


def _setup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    mcp_json: dict | None = None,
    settings_json: dict | None = None,
) -> Path:
    """Wire DOTFILES, HOME, commands.which, and PAT env vars; return the fake repo root.

    Creates ``tmp_path/repo`` with the given MCP and settings baselines. Sets HOME to
    ``tmp_path/home``. Default ``commands.which`` returns a path for "claude" and None for
    everything else — override it after this call when a test needs different behaviour.
    Clears all three GitHub PAT env vars so tests start clean.
    """
    tmp_repo = tmp_path / "repo"
    tmp_repo.mkdir()
    mcp_data = mcp_json if mcp_json is not None else {}
    (tmp_repo / "claude_mcp.json").write_text(json.dumps(mcp_data), encoding="utf-8")
    settings_data = settings_json if settings_json is not None else {}
    (tmp_repo / "claude_settings.json").write_text(json.dumps(settings_data), encoding="utf-8")
    monkeypatch.setattr(claude_setup, "DOTFILES", tmp_repo)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    def _default_which(name: str) -> str | None:
        return "/usr/local/bin/claude" if name == "claude" else None

    monkeypatch.setattr(commands, "which", _default_which)
    for var in ("GITHUB_PERSONAL_ACCESS_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    return tmp_repo


# ── Phase 12: register_mcp_servers ────────────────────────────────────────────────────────────


def test_mcp_skips_when_claude_cli_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 1: claude CLI absent → warn + return, nothing registered."""
    _setup(monkeypatch, tmp_path, mcp_json=_GITHUB_MCP)
    monkeypatch.setattr(commands, "which", lambda _name: None)  # nothing on PATH
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls))
    ctx, _ = _ctx()

    claude_setup.register_mcp_servers(ctx)

    assert _add_json_calls(calls) == []
    assert any("skipping Claude Code MCP setup" in w for w in ctx.ui.warnings)


def test_mcp_overlay_adds_server_and_replaces_arrays(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 2: overlay server added; array keys REPLACED (not unioned); objects recurse."""
    baseline = {
        "context7": {
            "type": "stdio",
            "command": "npx",
            "args": ["-y", "@upstash/context7-mcp"],  # array → REPLACED by overlay
            "env": {"LEVEL": "base"},  # object → recursed / merged with overlay
        }
    }
    overlay = {
        "context7": {"args": ["new-arg"], "env": {"EXTRA": "x"}},
        "extra": {"type": "http", "url": "https://example.com"},
    }
    _setup(monkeypatch, tmp_path, mcp_json=baseline)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls))

    cfg_dir = tmp_path / "home" / ".config" / "dotfiles"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "claude_mcp.local.json").write_text(json.dumps(overlay), encoding="utf-8")
    ctx, _ = _ctx()

    claude_setup.register_mcp_servers(ctx)

    registered = {c.argv[3]: json.loads(c.argv[4]) for c in _add_json_calls(calls)}
    assert "extra" in registered, "overlay-only server must be registered"
    c7 = registered["context7"]
    assert c7["args"] == ["new-arg"], "array must be REPLACED not unioned"
    assert c7["env"] == {"LEVEL": "base", "EXTRA": "x"}, "nested objects must be recursed"
    assert ctx.ui.warnings == []


def test_mcp_malformed_overlay_falls_back_to_baseline_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 2 (malformed): non-JSON overlay → warn + register only baseline servers."""
    baseline = {"http_only": {"type": "http", "url": "https://example.com"}}
    _setup(monkeypatch, tmp_path, mcp_json=baseline)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls))

    cfg_dir = tmp_path / "home" / ".config" / "dotfiles"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "claude_mcp.local.json").write_text("not valid json!!!", encoding="utf-8")
    ctx, _ = _ctx()

    claude_setup.register_mcp_servers(ctx)

    registered_names = {c.argv[3] for c in _add_json_calls(calls)}
    assert registered_names == {"http_only"}
    assert any("registering baseline servers only" in w for w in ctx.ui.warnings)


def test_mcp_secret_leak_guard_skips_server_with_op_ref(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 3 (CRITICAL): op:// after resolution → add-json NEVER called for that server."""
    # op absent (which returns None for "op"), no PAT set — github keeps its op:// → must skip
    _setup(monkeypatch, tmp_path, mcp_json=_GITHUB_MCP)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, op_whoami_ok=False))
    ctx, _ = _ctx()

    claude_setup.register_mcp_servers(ctx)

    github_add = [c for c in _add_json_calls(calls) if c.argv[3] == "github"]
    assert github_add == [], (
        "add-json must NEVER be called for a server with an unresolved op:// reference"
    )


def test_mcp_secret_leak_guard_emits_warnings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 3 (CRITICAL): skipped server emits both expected warnings."""
    _setup(monkeypatch, tmp_path, mcp_json=_GITHUB_MCP)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, op_whoami_ok=False))
    ctx, _ = _ctx()

    claude_setup.register_mcp_servers(ctx)

    assert any("unresolved 1Password reference" in w for w in ctx.ui.warnings), (
        "expected 'unresolved 1Password reference' warning is missing"
    )
    assert any("1Password not signed in" in w for w in ctx.ui.warnings), (
        "expected '1Password not signed in' warning is missing"
    )


def test_mcp_secret_leak_guard_op_ref_never_reaches_add_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 3 (CRITICAL): the literal op:// substring must never appear in any add-json call.

    This is the innermost security invariant: even if a future code path were to let a server
    name slip through the skip guard, the argv sent to the claude CLI must never carry an
    unresolved reference. The test exercises a multi-server baseline so the "safe" server
    is also registered, proving the guard is selective, not a blanket block.
    """
    baseline = {
        "safe": {"type": "http", "url": "https://example.com"},
        "secret": {
            "type": "http",
            "url": "https://secret.example.com",
            "headers": {"Authorization": "Bearer op://vault/item/field"},
        },
    }
    _setup(monkeypatch, tmp_path, mcp_json=baseline)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, op_whoami_ok=False))
    ctx, _ = _ctx()

    claude_setup.register_mcp_servers(ctx)

    for c in _add_json_calls(calls):
        server_json_str = c.argv[4]
        assert _OP_REF not in server_json_str, (
            f"op:// reference leaked into claude mcp add-json for '{c.argv[3]}': {c.argv}"
        )


def test_mcp_secret_leak_guard_skips_remove_too(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 3: a server skipped for op:// must not trigger remove either."""
    _setup(monkeypatch, tmp_path, mcp_json=_GITHUB_MCP)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, op_whoami_ok=False))
    ctx, _ = _ctx()

    claude_setup.register_mcp_servers(ctx)

    github_removes = [c for c in _remove_calls(calls) if c.argv[3] == "github"]
    assert github_removes == [], "remove must not be called for a skipped (op://) server"


def test_mcp_github_pat_rewrites_authorization_and_registers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 4: GITHUB_PERSONAL_ACCESS_TOKEN rewrites op:// auth; github server registered."""
    pat = "ghp_" + "X" * 30
    _setup(monkeypatch, tmp_path, mcp_json=_GITHUB_MCP)
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", pat)  # must be after _setup's delenv
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, op_whoami_ok=False))
    ctx, _ = _ctx()

    claude_setup.register_mcp_servers(ctx)

    github_adds = [c for c in _add_json_calls(calls) if c.argv[3] == "github"]
    assert len(github_adds) == 1, "github server must be registered when PAT is available"
    server_json_str = github_adds[0].argv[4]
    assert _OP_REF not in server_json_str, "op:// must not appear in the registered server JSON"
    assert f"Bearer {pat}" in server_json_str, "PAT must appear as the Bearer token"


def test_mcp_github_pat_emits_detail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 4: 'using a GitHub PAT from the environment' detail is printed on the PAT path."""
    pat = "ghp_" + "Y" * 30
    _setup(monkeypatch, tmp_path, mcp_json=_GITHUB_MCP)
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", pat)  # must be after _setup's delenv
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, op_whoami_ok=False))
    ctx, out = _ctx()

    claude_setup.register_mcp_servers(ctx)

    # The detail text is distinct from the "1Password not signed in … export a GitHub PAT"
    # warning — check for the specific phrase emitted by ctx.ui.detail().
    assert "using a GitHub PAT from the environment" in out.getvalue()


def test_mcp_pat_precedence_personal_beats_gh_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 4: GITHUB_PERSONAL_ACCESS_TOKEN takes precedence over GH_TOKEN."""
    personal = "ghp_" + "P" * 30
    gh = "ghp_" + "G" * 30
    _setup(monkeypatch, tmp_path, mcp_json=_GITHUB_MCP)
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", personal)  # after _setup's delenv
    monkeypatch.setenv("GH_TOKEN", gh)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, op_whoami_ok=False))
    ctx, _ = _ctx()

    claude_setup.register_mcp_servers(ctx)

    github_adds = [c for c in _add_json_calls(calls) if c.argv[3] == "github"]
    assert len(github_adds) == 1
    assert f"Bearer {personal}" in github_adds[0].argv[4], "personal PAT must win"
    assert gh not in github_adds[0].argv[4]


def test_mcp_pat_precedence_gh_token_beats_github_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 4: GH_TOKEN takes precedence over GITHUB_TOKEN."""
    gh = "ghp_" + "G" * 30
    github = "ghp_" + "H" * 30
    _setup(monkeypatch, tmp_path, mcp_json=_GITHUB_MCP)
    monkeypatch.setenv("GH_TOKEN", gh)  # after _setup's delenv
    monkeypatch.setenv("GITHUB_TOKEN", github)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, op_whoami_ok=False))
    ctx, _ = _ctx()

    claude_setup.register_mcp_servers(ctx)

    github_adds = [c for c in _add_json_calls(calls) if c.argv[3] == "github"]
    assert len(github_adds) == 1
    assert f"Bearer {gh}" in github_adds[0].argv[4], "GH_TOKEN must win over GITHUB_TOKEN"
    assert github not in github_adds[0].argv[4]


def test_mcp_op_signed_in_calls_inject_and_registers_resolved(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 5: op signed in → inject called with merged JSON; resolved values registered."""
    resolved = {
        "github": {
            "type": "http",
            "url": "https://api.githubcopilot.com/mcp/",
            "headers": {"Authorization": "Bearer resolved_token_abc"},
        }
    }
    _setup(monkeypatch, tmp_path, mcp_json=_GITHUB_MCP)
    # Override which so op is also available
    monkeypatch.setattr(
        commands,
        "which",
        lambda name: "/usr/local/bin/op" if name == "op" else "/usr/local/bin/claude",
    )
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(
        commands,
        "run",
        _fake_run(calls, op_whoami_ok=True, op_inject_json=json.dumps(resolved)),
    )
    ctx, _ = _ctx()

    claude_setup.register_mcp_servers(ctx)

    inject_calls = [c for c in calls if c.argv[:2] == ["op", "inject"]]
    assert len(inject_calls) == 1, "op inject must be called exactly once"
    assert inject_calls[0].input_text is not None
    injected_input = json.loads(inject_calls[0].input_text)
    assert "github" in injected_input, "inject input must be the merged MCP JSON"

    github_adds = [c for c in _add_json_calls(calls) if c.argv[3] == "github"]
    assert len(github_adds) == 1
    server_json_str = github_adds[0].argv[4]
    assert _OP_REF not in server_json_str, "op:// must not appear after inject"
    assert "resolved_token_abc" in server_json_str, "resolved token must be present"


def test_mcp_non_executable_absolute_command_skipped(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 6: server with non-executable absolute path → skipped + warn 'command not found'."""
    nonexec = str(tmp_path / "nonexistent_binary")
    baseline = {"badtool": {"type": "stdio", "command": nonexec, "args": []}}
    _setup(monkeypatch, tmp_path, mcp_json=baseline)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls))
    ctx, _ = _ctx()

    claude_setup.register_mcp_servers(ctx)

    assert not any(c.argv[3] == "badtool" for c in _add_json_calls(calls))
    assert any("command not found" in w for w in ctx.ui.warnings)


def test_mcp_http_server_without_command_is_registered(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 6: http server (no 'command' key) → registered unconditionally."""
    baseline = {"myhttp": {"type": "http", "url": "https://example.com"}}
    _setup(monkeypatch, tmp_path, mcp_json=baseline)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls))
    ctx, _ = _ctx()

    claude_setup.register_mcp_servers(ctx)

    assert any(c.argv[3] == "myhttp" for c in _add_json_calls(calls))


def test_mcp_executable_absolute_command_is_registered(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 6: server with a real executable absolute command → registered."""
    exec_cmd = tmp_path / "real_binary"
    exec_cmd.write_text("#!/bin/sh\n", encoding="utf-8")
    exec_cmd.chmod(0o755)
    baseline = {"mytool": {"type": "stdio", "command": str(exec_cmd), "args": []}}
    _setup(monkeypatch, tmp_path, mcp_json=baseline)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls))
    ctx, _ = _ctx()

    claude_setup.register_mcp_servers(ctx)

    assert any(c.argv[3] == "mytool" for c in _add_json_calls(calls))


def test_mcp_remove_precedes_add_json_with_user_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 7: remove is called before add-json; both carry '--scope user'."""
    baseline = {"myhttp": {"type": "http", "url": "https://example.com"}}
    _setup(monkeypatch, tmp_path, mcp_json=baseline)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls))
    ctx, _ = _ctx()

    claude_setup.register_mcp_servers(ctx)

    argvs = [c.argv for c in calls]
    remove_idx = next((i for i, a in enumerate(argvs) if a[:3] == _CLAUDE_MCP_REMOVE), None)
    add_idx = next((i for i, a in enumerate(argvs) if a[:3] == _CLAUDE_MCP_ADD), None)
    assert remove_idx is not None, "claude mcp remove was not called"
    assert add_idx is not None, "claude mcp add-json was not called"
    assert remove_idx < add_idx, "remove must precede add-json"
    remove_argv = argvs[remove_idx]
    assert "--scope" in remove_argv, "remove must carry --scope flag"
    assert "user" in remove_argv, "remove must carry user scope value"
    add_argv = argvs[add_idx]
    assert "--scope" in add_argv, "add-json must carry --scope flag"
    assert "user" in add_argv, "add-json must carry user scope value"


def test_mcp_failed_add_json_warns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 7: failing add-json exit → warn 'failed to register MCP server'."""
    baseline = {"myhttp": {"type": "http", "url": "https://example.com"}}
    _setup(monkeypatch, tmp_path, mcp_json=baseline)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, add_json_ok=False))
    ctx, _ = _ctx()

    claude_setup.register_mcp_servers(ctx)

    assert any("failed to register MCP server" in w for w in ctx.ui.warnings)


def test_mcp_happy_path_emits_ok(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 8: successful run emits ok('MCP servers registered')."""
    baseline = {"myhttp": {"type": "http", "url": "https://example.com"}}
    _setup(monkeypatch, tmp_path, mcp_json=baseline)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls))
    ctx, out = _ctx()

    claude_setup.register_mcp_servers(ctx)

    assert "MCP servers registered" in out.getvalue()


# ── Phase 13: write_user_settings ─────────────────────────────────────────────────────────────


def test_settings_skips_when_baseline_not_json_object(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 9: non-object baseline → warn + return, settings.json not created."""
    tmp_repo = tmp_path / "repo"
    tmp_repo.mkdir()
    (tmp_repo / "claude_settings.json").write_text("[]", encoding="utf-8")  # array, not object
    (tmp_repo / "claude_mcp.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(claude_setup, "DOTFILES", tmp_repo)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    ctx, _ = _ctx()

    claude_setup.write_user_settings(ctx)

    settings_path = tmp_path / "home" / ".claude" / "settings.json"
    assert not settings_path.exists(), "settings.json must not be created for an invalid baseline"
    assert any("not a JSON object" in w for w in ctx.ui.warnings)


def test_settings_happy_path_writes_both_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 10: baseline + no overlay + no live → settings.json = baseline, overlay = {}."""
    baseline = {"theme": "dark", "effortLevel": "high"}
    _setup(monkeypatch, tmp_path, settings_json=baseline)
    ctx, out = _ctx()

    claude_setup.write_user_settings(ctx)

    home = tmp_path / "home"
    settings_path = home / ".claude" / "settings.json"
    overlay_path = home / ".config" / "dotfiles" / "claude_settings.local.json"

    assert settings_path.exists(), "settings.json must be written"
    written = json.loads(settings_path.read_text())
    assert written == baseline, f"settings.json should match baseline; got {written}"

    assert overlay_path.exists(), "claude_settings.local.json must be written"
    overlay_written = json.loads(overlay_path.read_text())
    assert overlay_written == {}, f"overlay should be empty (no live drift); got {overlay_written}"

    assert "Claude settings written" in out.getvalue()


def test_settings_live_drift_folds_into_overlay_and_merged_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 11: live key beyond baseline → delta folds into overlay + appears in output."""
    baseline = {"theme": "dark"}
    _setup(monkeypatch, tmp_path, settings_json=baseline)

    home = tmp_path / "home"
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text(
        json.dumps({"theme": "dark", "newKey": "drift"}), encoding="utf-8"
    )
    ctx, _ = _ctx()

    claude_setup.write_user_settings(ctx)

    overlay_path = home / ".config" / "dotfiles" / "claude_settings.local.json"
    overlay_written = json.loads(overlay_path.read_text())
    assert overlay_written.get("newKey") == "drift", "live drift must be captured in the overlay"

    settings_written = json.loads((claude_dir / "settings.json").read_text())
    assert settings_written.get("theme") == "dark"
    assert settings_written.get("newKey") == "drift", "merged output must include the drift key"


def test_settings_non_object_live_warns_and_regenerates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 12 (live): non-object live settings → warn + regenerate from baseline+overlay."""
    baseline = {"theme": "dark"}
    _setup(monkeypatch, tmp_path, settings_json=baseline)

    home = tmp_path / "home"
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text("[1, 2, 3]", encoding="utf-8")
    ctx, _ = _ctx()

    claude_setup.write_user_settings(ctx)

    assert any("isn't a JSON object" in w for w in ctx.ui.warnings)
    settings_written = json.loads((claude_dir / "settings.json").read_text())
    assert settings_written == baseline, "regenerated settings must equal the baseline"


def test_settings_non_object_overlay_warns_and_rebuilds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 12 (overlay): non-object overlay → warn + rebuild from the live delta."""
    baseline = {"theme": "dark"}
    _setup(monkeypatch, tmp_path, settings_json=baseline)

    home = tmp_path / "home"
    cfg_dir = home / ".config" / "dotfiles"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "claude_settings.local.json").write_text("not-json", encoding="utf-8")

    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text(
        json.dumps({"theme": "dark", "newKey": "delta"}), encoding="utf-8"
    )
    ctx, _ = _ctx()

    claude_setup.write_user_settings(ctx)

    assert any("not a JSON object" in w for w in ctx.ui.warnings)
    overlay_path = cfg_dir / "claude_settings.local.json"
    overlay_written = json.loads(overlay_path.read_text())
    assert overlay_written.get("newKey") == "delta", "rebuilt overlay must capture the live delta"


def test_settings_dir_at_target_warns_skips_write_but_writes_overlay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 13: settings.json is a directory → warn; overlay still written; dir untouched."""
    baseline = {"theme": "dark"}
    _setup(monkeypatch, tmp_path, settings_json=baseline)

    home = tmp_path / "home"
    # Create settings.json as a DIRECTORY so the atomic write cannot proceed.
    settings_as_dir = home / ".claude" / "settings.json"
    settings_as_dir.mkdir(parents=True)
    ctx, _ = _ctx()

    claude_setup.write_user_settings(ctx)

    assert settings_as_dir.is_dir(), "the directory must not be replaced"
    assert any("is a directory" in w for w in ctx.ui.warnings)

    overlay_path = home / ".config" / "dotfiles" / "claude_settings.local.json"
    assert overlay_path.exists(), "overlay must still be written even when settings is a dir"


def test_settings_atomic_write_trailing_newline_and_no_temp_leftovers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Behavior 14: output ends with newline, parses as JSON, no leftover .tmp.<pid> files."""
    baseline = {"theme": "dark"}
    _setup(monkeypatch, tmp_path, settings_json=baseline)
    ctx, _ = _ctx()

    claude_setup.write_user_settings(ctx)

    home = tmp_path / "home"
    settings_path = home / ".claude" / "settings.json"
    raw = settings_path.read_text(encoding="utf-8")
    assert raw.endswith("\n"), "settings.json must end with a trailing newline"
    parsed = json.loads(raw)
    assert isinstance(parsed, dict), "settings.json must parse as a JSON object"

    claude_dir = home / ".claude"
    leftovers = list(claude_dir.glob("settings.json.tmp.*"))
    assert leftovers == [], f"leftover temp files found: {leftovers}"
