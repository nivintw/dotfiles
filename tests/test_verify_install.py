# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Behavior tests for the verify-install predicates, probes, and OK/BAD emitter.

The path/JSON/include predicates (ported from ``tests/verify_install.bats``), the live-state
probes (``pam_tid``, the firewall, the login shell), the :func:`iter_records` emitter, and the
phase-18 :func:`verify_and_summarize` renderer.
"""

from __future__ import annotations

import io
import os
import pwd
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from rich.console import Console

from dotfiles_install import commands, shell_select, verify_install
from dotfiles_install.context import InstallContext
from dotfiles_install.os_detect import OS
from dotfiles_install.ui import UI
from dotfiles_install.verify_install import (
    gitconfig_includes,
    is_json_object,
    prepush_hook_path,
    symlink_into_repo,
    tilde,
    touchid_enrolled_count,
)

if TYPE_CHECKING:
    import pytest


def _completed(stdout: str) -> subprocess.CompletedProcess[str]:
    """A successful CompletedProcess with the given stdout (for stubbing ``commands.run``)."""
    return subprocess.CompletedProcess([], returncode=0, stdout=stdout, stderr="")


def _brew_present(name: str) -> str | None:
    """A ``commands.which`` stub: brew present, everything else absent."""
    return "/usr/local/bin/brew" if name == "brew" else None


# --- symlink_into_repo ------------------------------------------------------


def test_symlink_into_repo_absolute_into_repo_passes(tmp_path: Path) -> None:
    """An absolute symlink pointing into the repo passes."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "file").write_text("x\n")
    link = tmp_path / "link"
    link.symlink_to(repo / "file")
    assert symlink_into_repo(link, repo)


def test_symlink_into_repo_relative_into_repo_passes(tmp_path: Path) -> None:
    """A relative symlink pointing into the repo passes."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "file").write_text("x\n")
    link = tmp_path / "link"
    link.symlink_to(Path("repo/file"))
    assert symlink_into_repo(link, repo)


def test_symlink_into_repo_real_file_fails(tmp_path: Path) -> None:
    """A real file (not a symlink) fails."""
    repo = tmp_path / "repo"
    repo.mkdir()
    real = tmp_path / "realfile"
    real.write_text("x\n")
    assert not symlink_into_repo(real, repo)


def test_symlink_into_repo_pointing_outside_fails(tmp_path: Path) -> None:
    """A symlink pointing outside the repo fails."""
    repo = tmp_path / "repo"
    repo.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_text("x\n")
    link = tmp_path / "link"
    link.symlink_to(elsewhere)
    assert not symlink_into_repo(link, repo)


def test_symlink_into_repo_missing_path_fails(tmp_path: Path) -> None:
    """A missing path fails."""
    repo = tmp_path / "repo"
    repo.mkdir()
    assert not symlink_into_repo(tmp_path / "nope", repo)


def test_symlink_into_repo_pointing_at_repo_root_fails(tmp_path: Path) -> None:
    """A symlink resolving to the repo root itself is not 'inside' it (bash requires under)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    link = tmp_path / "link"
    link.symlink_to(repo)
    assert not symlink_into_repo(link, repo)


def test_symlink_into_repo_nonexistent_repo_fails(tmp_path: Path) -> None:
    """A non-existent repo dir yields False (bash failed when cd into it failed)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "file"
    target.write_text("x\n")
    link = tmp_path / "link"
    link.symlink_to(target)
    assert not symlink_into_repo(link, tmp_path / "does-not-exist")


# --- is_json_object ---------------------------------------------------------


def test_is_json_object_object_passes(tmp_path: Path) -> None:
    """A JSON object passes."""
    path = tmp_path / "o.json"
    path.write_text('{"a":1}\n')
    assert is_json_object(path)


def test_is_json_object_array_fails(tmp_path: Path) -> None:
    """A JSON array fails (must be an object)."""
    path = tmp_path / "a.json"
    path.write_text("[1,2,3]\n")
    assert not is_json_object(path)


def test_is_json_object_scalar_fails(tmp_path: Path) -> None:
    """A non-object scalar fails."""
    path = tmp_path / "n.json"
    path.write_text("42\n")
    assert not is_json_object(path)


def test_is_json_object_invalid_fails(tmp_path: Path) -> None:
    """Invalid JSON fails."""
    path = tmp_path / "bad.json"
    path.write_text("{not json\n")
    assert not is_json_object(path)


def test_is_json_object_missing_fails(tmp_path: Path) -> None:
    """A missing file fails."""
    assert not is_json_object(tmp_path / "missing.json")


def test_is_json_object_non_utf8_fails(tmp_path: Path) -> None:
    """A file with non-UTF-8 bytes is not a JSON object (and must not crash)."""
    path = tmp_path / "binary.json"
    path.write_bytes(b"\xff\xfe\x00")
    assert not is_json_object(path)


# --- gitconfig_includes -----------------------------------------------------


def test_gitconfig_includes_matches_exact_path(tmp_path: Path) -> None:
    """Matches an include.path equal to the wanted file."""
    cfg = tmp_path / ".gitconfig"
    want = tmp_path / ".gitconfig_local"
    cfg.write_text(f"[include]\n\tpath = {want}\n")
    assert gitconfig_includes(cfg, want)


def test_gitconfig_includes_matches_through_tilde(tmp_path: Path) -> None:
    """Matches through ~ expansion on both sides."""
    cfg = tmp_path / ".gitconfig"
    cfg.write_text("[include]\n\tpath = ~/.gitconfig_local\n")
    assert gitconfig_includes(cfg, "~/.gitconfig_local")


def test_gitconfig_includes_no_matching_include_fails(tmp_path: Path) -> None:
    """A non-matching include fails."""
    cfg = tmp_path / ".gitconfig"
    cfg.write_text(f"[include]\n\tpath = {tmp_path / '.some_other_file'}\n")
    assert not gitconfig_includes(cfg, tmp_path / ".gitconfig_local")


def test_gitconfig_includes_no_includes_fails(tmp_path: Path) -> None:
    """A config with no includes at all fails."""
    cfg = tmp_path / ".gitconfig"
    cfg.write_text("[core]\n\tpager = delta\n")
    assert not gitconfig_includes(cfg, tmp_path / ".gitconfig_local")


def test_gitconfig_includes_missing_config_fails(tmp_path: Path) -> None:
    """A missing config file fails."""
    assert not gitconfig_includes(tmp_path / "nope", tmp_path / ".gitconfig_local")


# --- prepush_hook_path -------------------------------------------------------


def _init_repo(tmp_path: Path) -> Path:
    """A real (empty) git repo, so ``git rev-parse --git-path`` resolves for real."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--quiet"], cwd=repo, check=True)
    return repo


def test_prepush_hook_path_plain_repo_resolves(tmp_path: Path) -> None:
    """A plain clone resolves to the direct ``.git/hooks/pre-push`` path."""
    repo = _init_repo(tmp_path)
    assert prepush_hook_path(repo) == repo / ".git" / "hooks" / "pre-push"


def test_prepush_hook_path_respects_custom_hooks_path(tmp_path: Path) -> None:
    """A repo with ``core.hooksPath`` set resolves there, not the default ``.git/hooks``.

    Regression coverage: an earlier version of this function stat'd ``.git/hooks/pre-push``
    directly as a "no subprocess needed" fast path, which silently ignored a custom
    ``core.hooksPath`` (confirmed to be configured on the real dotfiles checkout).
    """
    repo = _init_repo(tmp_path)
    custom_hooks = tmp_path / "custom-hooks"
    custom_hooks.mkdir()
    subprocess.run(
        ["git", "config", "core.hooksPath", str(custom_hooks)],
        cwd=repo,
        check=True,
    )
    assert prepush_hook_path(repo) == custom_hooks / "pre-push"


def test_prepush_hook_path_worktree_shells_out(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A worktree (``.git`` is a file) resolves the shared hooks dir via ``git rev-parse``."""
    repo = tmp_path / "worktree"
    repo.mkdir()
    (repo / ".git").write_text("gitdir: /elsewhere/.git/worktrees/w\n", encoding="utf-8")
    monkeypatch.setattr(
        commands,
        "run",
        lambda *_a, **_k: _completed("/elsewhere/.git/worktrees/w/hooks/pre-push\n"),
    )
    assert prepush_hook_path(repo) == Path("/elsewhere/.git/worktrees/w/hooks/pre-push")


def test_prepush_hook_path_none_when_not_a_repo(tmp_path: Path) -> None:
    """Outside any git repo, resolution fails gracefully (None, not an exception)."""
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    assert prepush_hook_path(not_a_repo) is None


# --- pre-push hook record ----------------------------------------------------


def test_prepush_hook_ok_when_no_hook_installed(tmp_path: Path) -> None:
    """A fresh repo with no pre-push hook at all is fine (hooks are opt-in)."""
    repo = _init_repo(tmp_path)
    status, message = verify_install._prepush_hook_record(repo)
    assert status == "OK"
    assert "no pre-push hook installed" in message


def test_prepush_hook_ok_when_prek_generated(tmp_path: Path) -> None:
    """A pre-push hook carrying prek's marker passes."""
    repo = _init_repo(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/bin/sh\n# File generated by prek: https://github.com/j178/prek\n")
    status, _message = verify_install._prepush_hook_record(repo)
    assert status == "OK"


def test_prepush_hook_bad_when_owned_by_something_else(tmp_path: Path) -> None:
    """A pre-push hook present but NOT prek's (e.g. git-lfs's stub) flags the silent takeover."""
    repo = _init_repo(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_text("#!/bin/sh\ncommand -v git-lfs >/dev/null 2>&1 || exit 0\ngit lfs pre-push\n")
    status, message = verify_install._prepush_hook_record(repo)
    assert status == "BAD"
    assert "isn't prek-generated" in message


def test_prepush_hook_bad_when_hook_is_empty(tmp_path: Path) -> None:
    """An empty (but present) hook file is a broken occupant, not "nothing installed"."""
    repo = _init_repo(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.write_text("")
    status, message = verify_install._prepush_hook_record(repo)
    assert status == "BAD"
    assert "isn't prek-generated" in message


def test_prepush_hook_bad_when_hook_is_a_dangling_symlink(tmp_path: Path) -> None:
    """A dangling symlink at the hook path is still an occupant — not "nothing installed"."""
    repo = _init_repo(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-push"
    hook.symlink_to(repo / ".git" / "hooks" / "does-not-exist")
    status, message = verify_install._prepush_hook_record(repo)
    assert status == "BAD"
    assert "isn't prek-generated" in message


def test_prepush_hook_ok_when_not_a_git_repo(tmp_path: Path) -> None:
    """Outside any git repo the check degrades to OK rather than raising."""
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    status, message = verify_install._prepush_hook_record(not_a_repo)
    assert status == "OK"
    assert "no pre-push hook installed" in message


# --- tilde ------------------------------------------------------------------


def test_tilde_abbreviates_home() -> None:
    """Abbreviates a leading $HOME to ~."""
    assert tilde(Path.home() / ".gitconfig") == "~/.gitconfig"


def test_tilde_leaves_non_home_unchanged() -> None:
    """Leaves a path outside $HOME unchanged."""
    assert tilde("/etc/pam.d/sudo_local") == "/etc/pam.d/sudo_local"


# --- touchid_enrolled_count -------------------------------------------------


def _fake_bioutil(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> None:
    """Install a fake ``bioutil`` on PATH whose body is the given shell snippet."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    script = bindir / "bioutil"
    script.write_text(f"#!/usr/bin/env bash\n{body}\n")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")


def test_touchid_count_sums_enrolled_templates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sums enrolled templates from bioutil output."""
    _fake_bioutil(
        tmp_path,
        monkeypatch,
        r'printf "User 501:\t2 biometric template(s)\nOperation performed successfully.\n"',
    )
    expected = 2
    assert touchid_enrolled_count() == expected


def test_touchid_count_zero_when_none_enrolled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reports 0 for an enrolled count of zero."""
    _fake_bioutil(tmp_path, monkeypatch, r'printf "User 501:\t0 biometric template(s)\n"')
    assert touchid_enrolled_count() == 0


def test_touchid_count_zero_when_output_does_not_match(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reports 0 (no error) when bioutil output does not match the expected shape."""
    _fake_bioutil(tmp_path, monkeypatch, r'printf "no biometric data on this Mac\n"')
    assert touchid_enrolled_count() == 0


def test_touchid_count_zero_when_bioutil_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reports 0 when bioutil is absent from PATH."""
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    assert touchid_enrolled_count() == 0


# --- live-state probes ------------------------------------------------------


def test_pam_tid_enabled_detects_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Detects the pam_tid.so marker in sudo_local."""
    sudo_local = tmp_path / "sudo_local"
    sudo_local.write_text("auth       sufficient     pam_tid.so\n", encoding="utf-8")
    monkeypatch.setattr(verify_install, "_SUDO_LOCAL", sudo_local)
    assert verify_install.pam_tid_enabled()


def test_pam_tid_disabled_without_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No marker → not enabled."""
    sudo_local = tmp_path / "sudo_local"
    sudo_local.write_text("auth       include         sudo_local\n", encoding="utf-8")
    monkeypatch.setattr(verify_install, "_SUDO_LOCAL", sudo_local)
    assert not verify_install.pam_tid_enabled()


def test_pam_tid_disabled_when_file_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing sudo_local → not enabled (no crash)."""
    monkeypatch.setattr(verify_install, "_SUDO_LOCAL", tmp_path / "absent")
    assert not verify_install.pam_tid_enabled()


def test_firewall_enabled_when_state_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``socketfilterfw --getglobalstate`` reporting enabled → True."""
    fw = tmp_path / "socketfilterfw"
    fw.write_text("#!/bin/sh\n", encoding="utf-8")
    fw.chmod(0o755)
    monkeypatch.setattr(verify_install, "_SOCKETFILTERFW", fw)
    monkeypatch.setattr(
        commands, "run", lambda *_a, **_k: _completed("Firewall is enabled. (State = 1)")
    )
    assert verify_install.application_firewall_enabled()


def test_firewall_disabled_when_state_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A disabled global state → False."""
    fw = tmp_path / "socketfilterfw"
    fw.write_text("#!/bin/sh\n", encoding="utf-8")
    fw.chmod(0o755)
    monkeypatch.setattr(verify_install, "_SOCKETFILTERFW", fw)
    monkeypatch.setattr(
        commands, "run", lambda *_a, **_k: _completed("Firewall is disabled. (State = 0)")
    )
    assert not verify_install.application_firewall_enabled()


def test_firewall_false_when_binary_not_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A present-but-non-executable socketfilterfw degrades to False (no PermissionError crash)."""
    fw = tmp_path / "socketfilterfw"
    fw.write_text("#!/bin/sh\n", encoding="utf-8")
    fw.chmod(0o644)  # readable but NOT executable
    monkeypatch.setattr(verify_install, "_SOCKETFILTERFW", fw)

    def _boom(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        msg = "commands.run must not be invoked for a non-executable firewall binary"
        raise AssertionError(msg)

    monkeypatch.setattr(commands, "run", _boom)
    assert not verify_install.application_firewall_enabled()


def test_firewall_false_when_binary_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing socketfilterfw binary → False (and never shells out)."""
    monkeypatch.setattr(verify_install, "_SOCKETFILTERFW", tmp_path / "absent")
    assert not verify_install.application_firewall_enabled()


def test_login_shell_parses_dscl_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parses the shell path from ``dscl ... UserShell`` output."""
    monkeypatch.setattr(
        commands, "run", lambda *_a, **_k: _completed("UserShell: /opt/homebrew/bin/fish\n")
    )
    assert verify_install.login_shell() == "/opt/homebrew/bin/fish"


def test_login_shell_none_on_unexpected_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unparseable/empty dscl output → None (rather than an index error)."""
    monkeypatch.setattr(commands, "run", lambda *_a, **_k: _completed(""))
    assert verify_install.login_shell() is None


# --- _login_shell_record: shell-aware, fish default and persisted zsh -------


def test_login_shell_record_ok_with_no_persisted_choice_checks_fish(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """With nothing persisted, the record checks fish (the default) and passes when it matches."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(commands, "which", lambda name: f"/usr/local/bin/{name}")
    monkeypatch.setattr(verify_install, "login_shell", lambda: "/usr/local/bin/fish")
    assert verify_install._login_shell_record() == ("OK", "fish is the login shell")


def test_login_shell_record_follows_a_persisted_zsh_choice(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A persisted zsh choice makes the record check zsh, not fish.

    The zsh path was previously unexercised: this pins that it checks the right binary
    and passes when zsh actually is the login shell.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    shell_select.write_shell(tmp_path, "zsh")
    monkeypatch.setattr(commands, "which", lambda name: f"/usr/local/bin/{name}")
    monkeypatch.setattr(verify_install, "login_shell", lambda: "/usr/local/bin/zsh")
    assert verify_install._login_shell_record() == ("OK", "zsh is the login shell")


def test_login_shell_record_bad_when_persisted_zsh_but_login_shell_is_still_fish(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When zsh was selected but the actual login shell hasn't caught up yet → BAD, naming zsh."""
    monkeypatch.setenv("HOME", str(tmp_path))
    shell_select.write_shell(tmp_path, "zsh")
    monkeypatch.setattr(commands, "which", lambda name: f"/usr/local/bin/{name}")
    monkeypatch.setattr(verify_install, "login_shell", lambda: "/usr/local/bin/fish")
    status, message = verify_install._login_shell_record()
    assert status == "BAD"
    assert "not zsh" in message


# --- iter_records emitter ---------------------------------------------------


def _set_system_probes(monkeypatch: pytest.MonkeyPatch, *, ok: bool) -> None:
    """Stub the three non-brew system probes to uniformly passing or failing values."""
    monkeypatch.setattr(verify_install, "pam_tid_enabled", lambda: ok)
    monkeypatch.setattr(verify_install, "application_firewall_enabled", lambda: ok)
    monkeypatch.setattr(
        verify_install, "login_shell", lambda: "/usr/local/bin/fish" if ok else None
    )


def _all_probes(monkeypatch: pytest.MonkeyPatch, *, healthy: bool) -> None:
    """Stub every live-state probe (the three system probes + brew + Touch ID) uniformly."""
    _set_system_probes(monkeypatch, ok=healthy)
    monkeypatch.setattr(verify_install, "_brew_bundle_check", lambda _bf: healthy)
    monkeypatch.setattr(verify_install, "touchid_enrolled_count", lambda: 1 if healthy else 0)


def _healthy_repo_and_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a repo + tmp HOME where every file/symlink check passes; return the repo path."""
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    repo.mkdir()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (repo / "Brewfile").write_text('brew "git"\n', encoding="utf-8")
    for rel in (
        ".gitconfig",
        ".config/fish/config.fish",
        ".zshenv",
        ".config/zsh/.zshrc",
        ".claude/CLAUDE.md",
    ):
        src = repo / rel
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("x\n", encoding="utf-8")
        dst = home / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.symlink_to(src)
    # ~/.gitconfig is a symlink to repo/.gitconfig; put the overlay include there.
    (repo / ".gitconfig").write_text(
        f"[include]\n\tpath = {home}/.gitconfig_local\n", encoding="utf-8"
    )
    (home / ".claude" / "settings.json").write_text('{"theme":"dark"}\n', encoding="utf-8")
    return repo


def test_iter_records_all_ok_on_healthy_machine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fully set-up machine yields only OK records (the twelve baseline checks)."""
    repo = _healthy_repo_and_home(tmp_path, monkeypatch)
    monkeypatch.setattr(commands, "which", lambda name: f"/usr/local/bin/{name}")
    _all_probes(monkeypatch, healthy=True)
    records = list(verify_install.iter_records(repo, core=False))
    bad = [msg for status, msg in records if status == "BAD"]
    # brew, login, touch-id, firewall, 5 symlinks, settings, gitconfig, pre-push hook
    expected_checks = 12
    assert bad == []
    assert len(records) == expected_checks
    assert ("OK", "no pre-push hook installed (opt-in; nothing else owns it)") in records


def test_iter_records_flags_problems_on_bare_machine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bare machine (no brew, no symlinks) yields the expected BAD records."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(commands, "which", lambda _name: None)
    _all_probes(monkeypatch, healthy=False)
    records = list(verify_install.iter_records(repo, core=False))
    bad = [msg for status, msg in records if status == "BAD"]
    assert ("BAD", "Homebrew not found on PATH — the bundle step did not complete") in records
    assert any("not symlinked into repo" in msg for msg in bad)
    assert any("not a JSON object" in msg for msg in bad)


def _disable_system_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the non-brew probes all fail, so a test can focus on the brew records."""
    _set_system_probes(monkeypatch, ok=False)


def test_iter_records_checks_selected_opt_in_bundles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A selected opt-in bundle yields a record; comment/blank selection lines are skipped."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    repo = tmp_path / "repo"
    (repo / "Brewfile.d").mkdir(parents=True)
    (repo / "Brewfile").write_text("", encoding="utf-8")
    (repo / "Brewfile.d" / "work.brewfile").write_text('brew "gh"\n', encoding="utf-8")
    sel = home / ".config" / "dotfiles" / "bundles"
    sel.parent.mkdir(parents=True)
    sel.write_text("# a comment\nwork\n\n", encoding="utf-8")
    monkeypatch.setattr(commands, "which", _brew_present)
    monkeypatch.setattr(verify_install, "_brew_bundle_check", lambda bf: "work.brewfile" in str(bf))
    _disable_system_probes(monkeypatch)
    records = list(verify_install.iter_records(repo, core=False))
    assert ("OK", "opt-in bundle 'work' installed") in records


def test_iter_records_checks_machine_private_brewfile_local(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-empty Brewfile.local yields a record; an all-comment one is skipped."""
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Brewfile").write_text("", encoding="utf-8")
    local = home / ".config" / "dotfiles" / "Brewfile.local"
    local.parent.mkdir(parents=True)
    local.write_text('brew "fd"\n', encoding="utf-8")
    monkeypatch.setattr(commands, "which", _brew_present)
    monkeypatch.setattr(
        verify_install, "_brew_bundle_check", lambda bf: "Brewfile.local" in str(bf)
    )
    _disable_system_probes(monkeypatch)
    records = list(verify_install.iter_records(repo, core=False))
    assert ("OK", "machine-private Brewfile.local installed") in records


def test_touch_id_record_keeps_no_fingerprint_phrase(monkeypatch: pytest.MonkeyPatch) -> None:
    """The enrolled=0 message keeps the exact phrase vm-smoke's is_tolerated() matches."""
    monkeypatch.setattr(verify_install, "pam_tid_enabled", lambda: True)
    monkeypatch.setattr(verify_install, "touchid_enrolled_count", lambda: 0)
    status, message = verify_install._touch_id_record()
    assert status == "BAD"
    assert "NO fingerprint is enrolled" in message


def test_iter_records_core_strips_casks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Under --core the Brewfile checked is the casks-stripped subset."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "Brewfile").write_text('brew "git"\ncask "firefox"\n', encoding="utf-8")
    monkeypatch.setattr(
        commands, "which", lambda name: "/usr/local/bin/brew" if name == "brew" else None
    )
    captured: dict[str, str] = {}

    def _check_text(text: str) -> tuple[bool, Path]:
        captured["text"] = text
        return True, tmp_path / "core.brewfile"

    monkeypatch.setattr(verify_install, "_brew_bundle_check_text", _check_text)
    _all_probes(monkeypatch, healthy=False)  # the rest can fail; we only assert the core record
    records = list(verify_install.iter_records(repo, core=True))
    assert 'cask "firefox"' not in captured["text"]
    assert 'brew "git"' in captured["text"]
    assert ("OK", "Homebrew core (CLI formulae) packages all installed") in records


def test_verify_and_summarize_renders_partitioned_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Phase 18 splits records into Verified / Needs-attention and closes with the bash hints."""
    monkeypatch.setenv("HOME", str(tmp_path))  # no persisted shell choice here — fish default
    monkeypatch.setattr(
        verify_install,
        "iter_records",
        lambda *_a, **_k: iter([("OK", "all good"), ("BAD", "something broke")]),
    )
    out = io.StringIO()
    ui = UI(stdout=Console(file=out, width=200), stderr=Console(file=io.StringIO(), width=200))
    verify_install.verify_and_summarize(InstallContext(ui=ui))
    text = out.getvalue()
    assert "all good" in text
    assert "something broke" in text
    # A problem was present → the retry hint shows; the restart reminder is unconditional.
    assert "to retry" in text
    assert "exec fish" in text


def test_verify_and_summarize_no_retry_hint_when_all_clear(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """With nothing wrong, only the unconditional restart reminder closes the summary."""
    monkeypatch.setenv("HOME", str(tmp_path))  # no persisted shell choice here — fish default
    monkeypatch.setattr(
        verify_install, "iter_records", lambda *_a, **_k: iter([("OK", "all good")])
    )
    out = io.StringIO()
    ui = UI(stdout=Console(file=out, width=200), stderr=Console(file=io.StringIO(), width=200))
    verify_install.verify_and_summarize(InstallContext(ui=ui))
    text = out.getvalue()
    assert "to retry" not in text
    assert "exec fish" in text


def test_verify_and_summarize_exec_hint_follows_the_persisted_zsh_choice(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A persisted zsh choice makes the restart hint say 'exec zsh', not 'exec fish'."""
    monkeypatch.setenv("HOME", str(tmp_path))
    shell_select.write_shell(tmp_path, "zsh")
    monkeypatch.setattr(
        verify_install, "iter_records", lambda *_a, **_k: iter([("OK", "all good")])
    )
    out = io.StringIO()
    ui = UI(stdout=Console(file=out, width=200), stderr=Console(file=io.StringIO(), width=200))
    verify_install.verify_and_summarize(InstallContext(ui=ui))
    text = out.getvalue()
    assert "exec zsh" in text
    assert "exec fish" not in text


def test_login_shell_queries_the_real_user_not_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """login_shell resolves the account from the real uid, not a (possibly stale) $USER env."""
    monkeypatch.setenv("USER", "bogus-env-user")
    monkeypatch.setenv("LOGNAME", "bogus-env-user")
    real_user = pwd.getpwuid(os.getuid()).pw_name
    captured: dict[str, list[str]] = {}

    def _capture(argv: list[str], **_k: object) -> subprocess.CompletedProcess[str]:
        captured["argv"] = list(argv)
        return _completed("UserShell: /opt/homebrew/bin/fish\n")

    monkeypatch.setattr(commands, "run", _capture)
    verify_install.login_shell()
    assert f"/Users/{real_user}" in captured["argv"]
    assert "bogus-env-user" not in " ".join(captured["argv"])


def test_run_check_returns_problem_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """``run_check`` renders the summary and returns the count of BAD records (the exit signal)."""
    monkeypatch.setattr(
        verify_install,
        "iter_records",
        lambda *_a, **_k: iter([("OK", "fine"), ("BAD", "broke one"), ("BAD", "broke two")]),
    )
    out = io.StringIO()
    ui = UI(stdout=Console(file=out, width=200), stderr=Console(file=io.StringIO(), width=200))
    problems = verify_install.run_check(InstallContext(ui=ui))
    assert problems == 2  # noqa: PLR2004  # two BAD records above
    assert "broke one" in out.getvalue()


def test_run_check_returns_zero_when_all_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    """A healthy machine yields a zero problem count (-> exit 0 in the CLI)."""
    monkeypatch.setattr(
        verify_install, "iter_records", lambda *_a, **_k: iter([("OK", "all good")])
    )
    out = io.StringIO()
    ui = UI(stdout=Console(file=out, width=200), stderr=Console(file=io.StringIO(), width=200))
    assert verify_install.run_check(InstallContext(ui=ui)) == 0


def test_emit_stream_writes_raw_records_then_sentinel(monkeypatch: pytest.MonkeyPatch) -> None:
    """``emit_stream`` writes a record per line, closed by the BAD-count sentinel."""
    monkeypatch.setattr(
        verify_install,
        "iter_records",
        lambda *_a, **_k: iter([("OK", "fine"), ("BAD", "broke")]),
    )
    lines: list[str] = []
    verify_install.emit_stream(core=False, write=lines.append)
    # The sentinel carries the BAD count (1 here), not a hardcoded 0.
    assert lines == ["OK\tfine", "BAD\tbroke", "VERIFY_DONE\t1"]


def test_emit_stream_sentinel_is_zero_when_all_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean stream closes with a zero-count sentinel (no BAD records)."""
    monkeypatch.setattr(
        verify_install, "iter_records", lambda *_a, **_k: iter([("OK", "a"), ("OK", "b")])
    )
    lines: list[str] = []
    verify_install.emit_stream(core=False, write=lines.append)
    assert lines[-1] == "VERIFY_DONE\t0"


def test_emit_stream_passes_core_flag_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ``core`` flag reaches ``iter_records`` so the stream reflects the --core subset."""
    captured: dict[str, object] = {}

    def _iter(_dotfiles: object, *, core: bool) -> object:
        captured["core"] = core
        return iter(())

    monkeypatch.setattr(verify_install, "iter_records", _iter)
    verify_install.emit_stream(core=True, write=lambda _line: None)
    assert captured["core"] is True


# --- Linux / WSL shapes -----------------------------------------------------------------------


def test_login_shell_linux_reads_passwd(monkeypatch: pytest.MonkeyPatch) -> None:
    """On Linux the login shell comes from the passwd database (pw_shell), not dscl."""
    monkeypatch.setattr(verify_install, "current_os", lambda: OS.LINUX)

    class _Entry:
        pw_shell = "/home/linuxbrew/.linuxbrew/bin/fish"

    monkeypatch.setattr(pwd, "getpwuid", lambda _uid: _Entry())

    def _no_dscl(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        msg = "dscl must not be invoked on Linux"
        raise AssertionError(msg)

    monkeypatch.setattr(commands, "run", _no_dscl)
    assert verify_install.login_shell() == "/home/linuxbrew/.linuxbrew/bin/fish"


def test_ufw_active_reads_ufw_conf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ufw_active reflects the persistent ENABLED flag in ufw.conf; missing file reads inactive."""
    conf = tmp_path / "ufw.conf"
    monkeypatch.setattr(verify_install, "_UFW_CONF", conf)
    assert verify_install.ufw_active() is False  # no ufw.conf at all
    conf.write_text("# ufw config\nENABLED=yes\nLOGLEVEL=low\n", encoding="utf-8")
    assert verify_install.ufw_active() is True
    conf.write_text("ENABLED=no\n", encoding="utf-8")
    assert verify_install.ufw_active() is False


def test_iter_records_linux_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On Linux there is no Touch ID record, and the firewall record probes ufw (all OK here)."""
    monkeypatch.setattr(verify_install, "current_os", lambda: OS.LINUX)
    repo = _healthy_repo_and_home(tmp_path, monkeypatch)
    monkeypatch.setattr(commands, "which", lambda name: f"/usr/local/bin/{name}")
    _all_probes(monkeypatch, healthy=True)
    monkeypatch.setattr(verify_install, "ufw_active", lambda: True)
    records = list(verify_install.iter_records(repo, core=False))
    bad = [msg for status, msg in records if status == "BAD"]
    assert bad == []
    expected_checks = 11  # the macOS twelve, minus Touch ID
    assert len(records) == expected_checks
    assert any("ufw firewall active" in msg for _s, msg in records)
    assert not any("Touch ID" in msg for _s, msg in records)


def test_iter_records_linux_flags_inactive_ufw(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An inactive ufw yields a BAD firewall record on Linux."""
    monkeypatch.setattr(verify_install, "current_os", lambda: OS.LINUX)
    repo = _healthy_repo_and_home(tmp_path, monkeypatch)
    monkeypatch.setattr(commands, "which", lambda name: f"/usr/local/bin/{name}")
    _all_probes(monkeypatch, healthy=True)
    monkeypatch.setattr(verify_install, "ufw_active", lambda: False)
    records = list(verify_install.iter_records(repo, core=False))
    assert any(status == "BAD" and "ufw firewall is OFF" in msg for status, msg in records)


def test_iter_records_wsl_omits_the_firewall_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On WSL neither firewall record is yielded (the Windows host owns the firewall)."""
    monkeypatch.setattr(verify_install, "current_os", lambda: OS.WSL)
    repo = _healthy_repo_and_home(tmp_path, monkeypatch)
    monkeypatch.setattr(commands, "which", lambda name: f"/usr/local/bin/{name}")
    _all_probes(monkeypatch, healthy=True)
    records = list(verify_install.iter_records(repo, core=False))
    bad = [msg for status, msg in records if status == "BAD"]
    assert bad == []
    expected_checks = 10  # the macOS twelve, minus Touch ID and the firewall
    assert len(records) == expected_checks
    assert not any("firewall" in msg for _s, msg in records)


def test_iter_records_linux_distinguishes_missing_ufw(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With ufw absent, the Linux firewall BAD says to install it — not to enable it."""
    monkeypatch.setattr(verify_install, "current_os", lambda: OS.LINUX)
    repo = _healthy_repo_and_home(tmp_path, monkeypatch)
    monkeypatch.setattr(
        commands, "which", lambda name: None if name == "ufw" else f"/usr/local/bin/{name}"
    )
    _all_probes(monkeypatch, healthy=True)
    records = list(verify_install.iter_records(repo, core=False))
    assert any(status == "BAD" and "ufw is not installed" in msg for status, msg in records)
    assert not any("sudo ufw enable" in msg for _s, msg in records)
