# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Behavior tests for the verify-install predicates.

Ported from the predicate tests in ``tests/verify_install.bats`` — the path/JSON/include
checks the post-install summary is built from. The summary *emitter* itself (which shells out
to brew/firewall/dscl to read live machine state) is system-probe orchestration and lands
with the orchestrator port (#53); only the unit-testable predicates are ported here.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from dotfiles_install.verify_install import (
    gitconfig_includes,
    is_json_object,
    symlink_into_repo,
    tilde,
    touchid_enrolled_count,
)

if TYPE_CHECKING:
    import pytest

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
