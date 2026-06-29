# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for phases 5-11: the post-stow installers.

Covers install_fish_plugins, install_tmux_plugins, import_atuin_history,
configure_iterm2, install_uv_tools, report_clone_hook, and install_claude_cli,
plus the _ensure_local_bin_on_path helper.

All subprocess goes through the ``commands`` seam; tests monkeypatch commands.run,
commands.run_ok, commands.which, commands.fetch, and commands.retry at that boundary
rather than patching subprocess directly.
"""

from __future__ import annotations

import io
import os
import stat
import subprocess
from typing import TYPE_CHECKING

from rich.console import Console

from dotfiles_install import commands, post_stow
from dotfiles_install.context import InstallContext
from dotfiles_install.ui import UI

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import pytest


def _ctx() -> tuple[InstallContext, io.StringIO]:
    """Build an install context over a wide in-memory console (wide so lines don't wrap)."""
    out = io.StringIO()
    ui = UI(stdout=Console(file=out, width=200), stderr=Console(file=io.StringIO(), width=200))
    return InstallContext(ui=ui), out


def _fake_retry_once(
    _description: str,
    _attempts: int,
    func: Callable[[], bool],
    **_kwargs: object,
) -> bool:
    """Fake retry that calls func() exactly once — avoids the real 3s time.sleep delays."""
    return func()


# --- install_fish_plugins (phase 5) -----------------------------------------------------------


def test_fish_plugins_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful fisher run emits ok and invokes fish with exactly _FISHER_SCRIPT."""
    run_ok_calls: list[list[str]] = []

    def _run_ok(argv: list[str], **_kwargs: object) -> bool:
        run_ok_calls.append(list(argv))
        return True

    monkeypatch.setattr(commands, "retry", _fake_retry_once)
    monkeypatch.setattr(commands, "run_ok", _run_ok)
    ctx, out = _ctx()

    post_stow.install_fish_plugins(ctx)

    assert "fish plugins installed" in out.getvalue()
    assert ctx.ui.warnings == []
    assert run_ok_calls == [["fish", "-c", post_stow._FISHER_SCRIPT]]


def test_fish_plugins_failure_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    """When retry returns False, a warn containing 'fisher bootstrap failed' is emitted."""
    monkeypatch.setattr(commands, "retry", lambda *_a, **_k: False)
    ctx, _ = _ctx()

    post_stow.install_fish_plugins(ctx)

    assert any("fisher bootstrap failed" in w for w in ctx.ui.warnings)


# --- install_tmux_plugins (phase 6) -----------------------------------------------------------


def test_tmux_plugins_entrypoint_already_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When bin/install_plugins is already executable, no clone is attempted; install + ok."""
    monkeypatch.setenv("HOME", str(tmp_path))
    tpm_bin = tmp_path / ".config" / "tmux" / "plugins" / "tpm" / "bin"
    tpm_bin.mkdir(parents=True)
    install_plugins = tpm_bin / "install_plugins"
    install_plugins.write_text("#!/bin/sh\n", encoding="utf-8")
    install_plugins.chmod(install_plugins.stat().st_mode | stat.S_IXUSR)

    retry_calls: list[str] = []
    run_calls: list[list[str]] = []

    def _fake_retry(desc: str, _attempts: int, _func: object, **_kwargs: object) -> bool:
        retry_calls.append(desc)
        return True

    def _run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        run_calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(commands, "retry", _fake_retry)
    monkeypatch.setattr(commands, "run", _run)
    ctx, out = _ctx()

    post_stow.install_tmux_plugins(ctx)

    assert retry_calls == []  # no clone attempt
    assert "tmux plugins installed" in out.getvalue()
    assert any(c[0] == str(install_plugins) for c in run_calls)


def test_tmux_plugins_clones_when_entrypoint_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Absent entrypoint triggers a clone; after entrypoint appears, install runs + ok."""
    monkeypatch.setenv("HOME", str(tmp_path))
    tpm_bin = tmp_path / ".config" / "tmux" / "plugins" / "tpm" / "bin"
    install_plugins = tpm_bin / "install_plugins"

    def _fake_retry(_desc: str, _attempts: int, _func: object, **_kwargs: object) -> bool:
        # Simulate the git clone creating bin/install_plugins.
        tpm_bin.mkdir(parents=True, exist_ok=True)
        install_plugins.write_text("#!/bin/sh\n", encoding="utf-8")
        install_plugins.chmod(install_plugins.stat().st_mode | stat.S_IXUSR)
        return True

    run_calls: list[list[str]] = []

    def _run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        run_calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(commands, "retry", _fake_retry)
    monkeypatch.setattr(commands, "run", _run)
    ctx, out = _ctx()

    post_stow.install_tmux_plugins(ctx)

    assert "tmux plugins installed" in out.getvalue()
    assert ctx.ui.warnings == []
    assert any(c[0] == str(install_plugins) for c in run_calls)


def test_tmux_plugins_warns_when_clone_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Clone failure (retry False, no entrypoint) → warn 'TPM clone failed', no ok."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(commands, "retry", lambda *_a, **_k: False)

    run_calls: list[list[str]] = []

    def _run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        run_calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(commands, "run", _run)
    ctx, out = _ctx()

    post_stow.install_tmux_plugins(ctx)

    assert any("TPM clone failed" in w for w in ctx.ui.warnings)
    assert "tmux plugins installed" not in out.getvalue()


def test_tmux_clone_runs_real_closure_and_asserts_argv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Real _clone closure executes; git clone argv is exact; ok('tmux plugins installed')."""
    monkeypatch.setenv("HOME", str(tmp_path))
    tpm_dir = tmp_path / ".config" / "tmux" / "plugins" / "tpm"
    install_plugins = tpm_dir / "bin" / "install_plugins"

    run_ok_argvs: list[list[str]] = []

    def _run_ok(argv: list[str], **_kwargs: object) -> bool:
        run_ok_argvs.append(list(argv))
        if argv[:2] == ["git", "clone"]:
            install_plugins.parent.mkdir(parents=True, exist_ok=True)
            install_plugins.write_text("#!/bin/sh\n", encoding="utf-8")
            install_plugins.chmod(0o755)
        return True

    run_argvs: list[list[str]] = []

    def _run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        run_argvs.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(commands, "retry", _fake_retry_once)
    monkeypatch.setattr(commands, "run_ok", _run_ok)
    monkeypatch.setattr(commands, "run", _run)
    ctx, out = _ctx()

    post_stow.install_tmux_plugins(ctx)

    expected_clone = [
        "git",
        "clone",
        "--depth",
        "1",
        "https://github.com/tmux-plugins/tpm",
        str(tpm_dir),
    ]
    assert expected_clone in run_ok_argvs
    assert "tmux plugins installed" in out.getvalue()


# --- import_atuin_history (phase 7) -----------------------------------------------------------


def test_atuin_absent_emits_detail_and_skips_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When atuin is not on PATH, a detail line is emitted and no atuin command is run."""
    monkeypatch.setattr(commands, "which", lambda _name: None)
    run_calls: list[list[str]] = []

    def _run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        run_calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(commands, "run", _run)
    ctx, out = _ctx()

    post_stow.import_atuin_history(ctx)

    assert "atuin not installed" in out.getvalue()
    assert run_calls == []
    assert ctx.ui.warnings == []


def test_atuin_present_runs_import_and_emits_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """When atuin is present, runs ['atuin', 'import', 'auto'] and emits ok."""
    monkeypatch.setattr(commands, "which", lambda _name: "/usr/bin/atuin")
    run_calls: list[list[str]] = []

    def _run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        run_calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(commands, "run", _run)
    ctx, out = _ctx()

    post_stow.import_atuin_history(ctx)

    assert ["atuin", "import", "auto"] in run_calls
    assert "shell history imported into atuin" in out.getvalue()


# --- configure_iterm2 (phase 8) ---------------------------------------------------------------


def test_configure_iterm2_records_two_defaults_write_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Phase 8 runs PrefsCustomFolder + LoadPrefsFromCustomFolder writes and emits ok."""
    monkeypatch.setattr(post_stow, "DOTFILES", tmp_path)
    run_calls: list[list[str]] = []

    def _run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        run_calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    monkeypatch.setattr(commands, "run", _run)
    ctx, out = _ctx()

    post_stow.configure_iterm2(ctx)

    iterm2_calls = [c for c in run_calls if "com.googlecode.iterm2" in c]
    prefs_calls = [c for c in iterm2_calls if "PrefsCustomFolder" in c]
    load_calls = [c for c in iterm2_calls if "LoadPrefsFromCustomFolder" in c]

    assert len(prefs_calls) == 1
    assert str(tmp_path / "iterm2") in prefs_calls[0]

    assert len(load_calls) == 1
    assert "true" in load_calls[0]

    assert "iTerm2 pointed at tracked preferences" in out.getvalue()


def test_configure_iterm2_warns_when_defaults_write_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Defaults write failure emits 'couldn't point iTerm2' warning; success line absent."""
    monkeypatch.setattr(post_stow, "DOTFILES", tmp_path)
    monkeypatch.setattr(commands, "run_ok", lambda *_a, **_k: False)
    ctx, out = _ctx()

    post_stow.configure_iterm2(ctx)

    assert any("couldn't point iTerm2 at the tracked prefs" in w for w in ctx.ui.warnings)
    assert "iTerm2 pointed at tracked preferences" not in out.getvalue()


# --- install_uv_tools (phase 9) ---------------------------------------------------------------


def test_uv_tools_skips_blank_and_comment_lines(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Blank lines and #comment lines are skipped; tool lines produce uv tool install calls."""
    (tmp_path / "uv_tools.txt").write_text(
        "\n# a comment\nruff\nhttpx --with charset-normalizer\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(post_stow, "DOTFILES", tmp_path)
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setattr(commands, "retry", _fake_retry_once)
    run_ok_calls: list[list[str]] = []

    def _run_ok(argv: list[str], **_kwargs: object) -> bool:
        run_ok_calls.append(list(argv))
        return True

    monkeypatch.setattr(commands, "run_ok", _run_ok)
    ctx, _ = _ctx()

    post_stow.install_uv_tools(ctx)

    tool_installs = {tuple(c) for c in run_ok_calls if c[:3] == ["uv", "tool", "install"]}
    assert tool_installs == {
        ("uv", "tool", "install", "ruff"),
        ("uv", "tool", "install", "httpx", "--with", "charset-normalizer"),
    }


def test_uv_tools_all_success_emits_ok(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When all tools install successfully, ok('uv tools installed') is emitted."""
    (tmp_path / "uv_tools.txt").write_text("ruff\n", encoding="utf-8")
    monkeypatch.setattr(post_stow, "DOTFILES", tmp_path)
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setattr(commands, "retry", _fake_retry_once)
    monkeypatch.setattr(commands, "run_ok", lambda *_a, **_k: True)
    ctx, out = _ctx()

    post_stow.install_uv_tools(ctx)

    assert "uv tools installed" in out.getvalue()
    assert ctx.ui.warnings == []


def test_uv_tools_failing_tool_warns_per_tool_and_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failing tool emits a per-tool warn and a summary warn about the failure count."""
    (tmp_path / "uv_tools.txt").write_text("ruff\nbad-tool\n", encoding="utf-8")
    monkeypatch.setattr(post_stow, "DOTFILES", tmp_path)
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setattr(commands, "retry", _fake_retry_once)

    def _run_ok(argv: list[str], **_kwargs: object) -> bool:
        return "bad-tool" not in argv

    monkeypatch.setattr(commands, "run_ok", _run_ok)
    ctx, _ = _ctx()

    post_stow.install_uv_tools(ctx)

    assert any("uv tool install failed for:" in w for w in ctx.ui.warnings)
    assert any("uv tool(s) failed" in w for w in ctx.ui.warnings)


def test_uv_tools_puts_local_bin_on_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """After install_uv_tools, ~/.local/bin is prepended to os.environ['PATH']."""
    (tmp_path / "uv_tools.txt").write_text("ruff\n", encoding="utf-8")
    monkeypatch.setattr(post_stow, "DOTFILES", tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setattr(commands, "retry", _fake_retry_once)
    monkeypatch.setattr(commands, "run_ok", lambda *_a, **_k: True)
    ctx, _ = _ctx()

    post_stow.install_uv_tools(ctx)

    expected = str(tmp_path / ".local" / "bin")
    assert expected in os.environ["PATH"].split(os.pathsep)


def test_uv_tools_playwright_install_argv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Playwright install uses the correct argv with --project pointing at DOTFILES."""
    (tmp_path / "uv_tools.txt").write_text("", encoding="utf-8")
    monkeypatch.setattr(post_stow, "DOTFILES", tmp_path)
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setattr(commands, "retry", _fake_retry_once)
    run_ok_calls: list[list[str]] = []

    def _run_ok(argv: list[str], **_kwargs: object) -> bool:
        run_ok_calls.append(list(argv))
        return True

    monkeypatch.setattr(commands, "run_ok", _run_ok)
    ctx, _ = _ctx()

    post_stow.install_uv_tools(ctx)

    playwright_calls = [c for c in run_ok_calls if "playwright" in c]
    assert len(playwright_calls) == 1
    assert playwright_calls[0] == [
        "uv",
        "run",
        "--project",
        str(tmp_path),
        "playwright",
        "install",
        "--only-shell",
        "chromium",
    ]


def test_uv_tools_playwright_failure_warns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A Playwright install failure emits a warn."""
    (tmp_path / "uv_tools.txt").write_text("", encoding="utf-8")
    monkeypatch.setattr(post_stow, "DOTFILES", tmp_path)
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setattr(commands, "retry", _fake_retry_once)

    def _run_ok(argv: list[str], **_kwargs: object) -> bool:
        return "playwright" not in argv

    monkeypatch.setattr(commands, "run_ok", _run_ok)
    ctx, _ = _ctx()

    post_stow.install_uv_tools(ctx)

    assert any("Playwright" in w for w in ctx.ui.warnings)


# --- report_clone_hook (phase 10) -------------------------------------------------------------


def test_clone_hook_enabled_emits_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """When git config returns rc0 and stdout 'true', ok about auto-install is emitted."""

    def _run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, stdout="true\n", stderr="")

    monkeypatch.setattr(commands, "run", _run)
    ctx, out = _ctx()

    post_stow.report_clone_hook(ctx)

    assert "auto-install" in out.getvalue()
    assert ctx.ui.warnings == []


def test_clone_hook_nonzero_rc_emits_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    """When git config returns nonzero, a detail about notify-on-clone mode is emitted."""

    def _run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 1, stdout="", stderr="")

    monkeypatch.setattr(commands, "run", _run)
    ctx, out = _ctx()

    post_stow.report_clone_hook(ctx)

    assert "fresh clones will notify" in out.getvalue()
    assert ctx.ui.warnings == []


def test_clone_hook_false_value_emits_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    """rc0 but stdout 'false' (not 'true') is treated as disabled."""

    def _run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, 0, stdout="false\n", stderr="")

    monkeypatch.setattr(commands, "run", _run)
    ctx, out = _ctx()

    post_stow.report_clone_hook(ctx)

    assert "fresh clones will notify" in out.getvalue()


# --- install_claude_cli (phase 11) ------------------------------------------------------------


def test_claude_already_installed_emits_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    """When 'claude' is already on PATH, a detail is emitted and no install runs."""
    monkeypatch.setattr(commands, "which", lambda _name: "/usr/local/bin/claude")
    fetch_called: list[bool] = []
    monkeypatch.setattr(commands, "fetch", lambda _argv: (fetch_called.append(True), None)[1])
    ctx, out = _ctx()

    post_stow.install_claude_cli(ctx)

    assert "already installed" in out.getvalue()
    assert fetch_called == []
    assert ctx.ui.warnings == []


def test_claude_absent_success_runs_fetch_then_bash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When claude is absent, fetch is called and the script is piped into bash."""
    monkeypatch.setattr(commands, "which", lambda _name: None)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "/usr/bin")

    fetch_calls: list[list[str]] = []
    run_ok_calls: list[dict[str, object]] = []

    def _fetch(argv: list[str]) -> str | None:
        fetch_calls.append(list(argv))
        return "INSTALL_SCRIPT"

    def _run_ok(argv: list[str], **kwargs: object) -> bool:
        run_ok_calls.append({"argv": list(argv), **kwargs})
        return True

    monkeypatch.setattr(commands, "fetch", _fetch)
    monkeypatch.setattr(commands, "run_ok", _run_ok)
    monkeypatch.setattr(commands, "retry", _fake_retry_once)
    ctx, out = _ctx()

    post_stow.install_claude_cli(ctx)

    assert len(fetch_calls) == 1
    assert fetch_calls[0][0] == "curl"
    assert len(run_ok_calls) == 1
    assert run_ok_calls[0]["argv"] == ["bash"]
    assert run_ok_calls[0].get("input_text") == "INSTALL_SCRIPT"
    assert "Claude Code CLI installed" in out.getvalue()
    assert ctx.ui.warnings == []


def test_claude_absent_fetch_failure_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    """A None fetch (download fail) causes retry to return False, then a warn is emitted."""
    monkeypatch.setattr(commands, "which", lambda _name: None)
    monkeypatch.setattr(commands, "fetch", lambda _argv: None)
    monkeypatch.setattr(commands, "retry", _fake_retry_once)
    ctx, _ = _ctx()

    post_stow.install_claude_cli(ctx)

    assert any("Claude Code install failed" in w for w in ctx.ui.warnings)


def test_claude_absent_bash_failure_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful fetch but failed bash run → retry returns False → warn."""
    monkeypatch.setattr(commands, "which", lambda _name: None)
    monkeypatch.setattr(commands, "fetch", lambda _argv: "SCRIPT")
    monkeypatch.setattr(commands, "run_ok", lambda *_a, **_k: False)
    monkeypatch.setattr(commands, "retry", _fake_retry_once)
    ctx, _ = _ctx()

    post_stow.install_claude_cli(ctx)

    assert any("Claude Code install failed" in w for w in ctx.ui.warnings)


def test_claude_install_puts_local_bin_on_path_on_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """On successful install, _ensure_local_bin_on_path adds ~/.local/bin to PATH."""
    monkeypatch.setattr(commands, "which", lambda _name: None)
    monkeypatch.setattr(commands, "fetch", lambda _argv: "SCRIPT")
    monkeypatch.setattr(commands, "run_ok", lambda *_a, **_k: True)
    monkeypatch.setattr(commands, "retry", _fake_retry_once)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "/usr/bin")
    ctx, _ = _ctx()

    post_stow.install_claude_cli(ctx)

    expected = str(tmp_path / ".local" / "bin")
    assert expected in os.environ["PATH"].split(os.pathsep)
