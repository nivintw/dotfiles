# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for phase 3: GNU stow symlinking (stow.py).

Behaviors covered:
- MANAGED_FILES constant contains exactly the expected three $HOME-relative paths.
- _clear_managed_files: removes real files byte-identical to the repo copy with an active
  message; backs up differing files to numbered .pre-stow.bak paths (never clobbering earlier
  ones) with a warn; skips symlinks silently; skips absent files silently; warns when no repo
  copy exists (stow won't manage the path).
- _migrate_git_template_hooks: removes prek-generated shims (matched by the marker text),
  leaves hand-written hooks untouched, skips symlinks, emits an active message listing removed
  shim names, and is a silent no-op when the hooks directory is absent.
- _migrate_gitconfig: delegates to the real gitconfig_migrate (not mocked) for all normal paths;
  emits active when the file was identical-and-removed, warn when the file was backed up, and
  nothing on a no-op (absent / symlink); raises SystemExit(1) with an err when
  gitconfig_migrate raises OSError (mocked only for that case).
- _stow_preflight_and_apply: SystemExit(1) when the dry-run stow returns non-zero, surfacing the
  conflict lines; returns normally on a clean preflight + apply; SystemExit(1) when the apply
  step fails; dry-run argv contains -n and apply argv does not.
- stow_dotfiles happy path (no managed files, no template hooks, no .gitconfig, clean stow)
  emits the final ok line.
"""

from __future__ import annotations

import io
import subprocess
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from rich.console import Console

from dotfiles_install import commands, stow
from dotfiles_install.context import InstallContext
from dotfiles_install.ui import UI

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def _ctx() -> tuple[InstallContext, io.StringIO]:
    """Build an install context over a wide in-memory console (wide so lines don't wrap)."""
    out = io.StringIO()
    ui = UI(stdout=Console(file=out, width=200), stderr=Console(file=io.StringIO(), width=200))
    return InstallContext(ui=ui), out


def _ctx_err() -> tuple[InstallContext, io.StringIO, io.StringIO]:
    """Build an install context capturing both stdout and stderr (for fatal-path tests)."""
    out = io.StringIO()
    err = io.StringIO()
    ui = UI(stdout=Console(file=out, width=200), stderr=Console(file=err, width=200))
    return InstallContext(ui=ui), out, err


def _fake_stow_run(
    calls: list[SimpleNamespace],
    *,
    preflight_rc: int = 0,
    preflight_stdout: str = "",
    preflight_stderr: str = "",
    apply_rc: int = 0,
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Build a commands.run replacement that records calls and answers stow by dry-run flag."""

    def run(
        argv: list[str],
        *,
        input_text: str | None = None,
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        """Record the call and dispatch by whether -n (dry-run) is present."""
        argv = list(argv)
        calls.append(SimpleNamespace(argv=argv, input_text=input_text))
        if "-n" in argv:
            return subprocess.CompletedProcess(
                argv,
                preflight_rc,
                stdout=preflight_stdout,
                stderr=preflight_stderr,
            )
        return subprocess.CompletedProcess(argv, apply_rc, stdout="", stderr="")

    return run


def _setup_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Return (dotfiles_root, home_dir) under tmp_path; creates home_dir immediately."""
    dotfiles = tmp_path / "dotfiles"
    home_dir = tmp_path / "home_dir"
    home_dir.mkdir(parents=True)
    return dotfiles, home_dir


# --- MANAGED_FILES ---------------------------------------------------------------------------


def test_managed_files_contains_expected_paths() -> None:
    """MANAGED_FILES is a two-element tuple with the expected $HOME-relative paths.

    VS Code's settings.json is deliberately absent: it's generated (vscode_setup.py), not
    stowed, as of #40.
    """
    assert stow.MANAGED_FILES == (
        ".config/atuin/config.toml",
        ".config/topgrade.toml",
    ), f"MANAGED_FILES changed unexpectedly: {stow.MANAGED_FILES!r}"


# --- _clear_managed_files --------------------------------------------------------------------


def test_clear_managed_files_removes_identical_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A real file byte-identical to its repo copy is unlinked with an active message."""
    dotfiles, home_dir = _setup_repo(tmp_path)
    rel = ".config/atuin/config.toml"
    content = b"[settings]\nfilter_mode = workspace\n"

    repo_src = dotfiles / "home" / rel
    repo_src.parent.mkdir(parents=True)
    repo_src.write_bytes(content)

    target = home_dir / rel
    target.parent.mkdir(parents=True)
    target.write_bytes(content)

    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, out = _ctx()

    stow._clear_managed_files(ctx)

    assert not target.exists(), f"identical managed file should have been removed: {target}"
    assert "removing existing real file" in out.getvalue(), (
        f"expected active message; got: {out.getvalue()!r}"
    )
    assert ctx.ui.warnings == [], f"no warnings expected; got: {ctx.ui.warnings!r}"


def test_clear_managed_files_backs_up_differing_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A real file differing from the repo copy is moved to .pre-stow.bak with a warn."""
    dotfiles, home_dir = _setup_repo(tmp_path)
    rel = ".config/atuin/config.toml"

    repo_src = dotfiles / "home" / rel
    repo_src.parent.mkdir(parents=True)
    repo_src.write_bytes(b"repo content\n")

    target = home_dir / rel
    target.parent.mkdir(parents=True)
    target.write_bytes(b"user modified content\n")

    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, _ = _ctx()

    stow._clear_managed_files(ctx)

    backup = target.with_name(f"{target.name}.pre-stow.bak")
    assert not target.exists(), f"target should have been moved to backup: {target}"
    assert backup.exists(), f"backup should exist: {backup}"
    assert backup.read_bytes() == b"user modified content\n", (
        "backup should preserve the user's modified content"
    )
    assert any("backing up modified" in w for w in ctx.ui.warnings), (
        f"expected warn about backup; got: {ctx.ui.warnings!r}"
    )


def test_clear_managed_files_numbers_backups_without_clobbering(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When .pre-stow.bak already exists, the next backup lands in .pre-stow.bak.1."""
    dotfiles, home_dir = _setup_repo(tmp_path)
    rel = ".config/atuin/config.toml"

    repo_src = dotfiles / "home" / rel
    repo_src.parent.mkdir(parents=True)
    repo_src.write_bytes(b"repo content\n")

    target = home_dir / rel
    target.parent.mkdir(parents=True)
    target.write_bytes(b"user content v2\n")

    # Occupy the first slot so the code must step to .1
    existing_backup = target.with_name(f"{target.name}.pre-stow.bak")
    existing_backup.write_bytes(b"user content v1\n")

    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, _ = _ctx()

    stow._clear_managed_files(ctx)

    backup_1 = target.with_name(f"{target.name}.pre-stow.bak.1")
    assert existing_backup.read_bytes() == b"user content v1\n", (
        "earlier backup must not be clobbered"
    )
    assert backup_1.exists(), f"numbered backup .pre-stow.bak.1 should exist: {backup_1}"
    assert backup_1.read_bytes() == b"user content v2\n", (
        "numbered backup should hold the new content"
    )


def test_clear_managed_files_skips_symlinks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A symlink at a managed path is left untouched (already stow-managed)."""
    dotfiles, home_dir = _setup_repo(tmp_path)
    rel = ".config/atuin/config.toml"

    repo_src = dotfiles / "home" / rel
    repo_src.parent.mkdir(parents=True)
    repo_src.write_bytes(b"repo content\n")

    link_target = tmp_path / "atuin_config_real.toml"
    link_target.write_bytes(b"real file\n")

    managed = home_dir / rel
    managed.parent.mkdir(parents=True)
    managed.symlink_to(link_target)

    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, out = _ctx()

    stow._clear_managed_files(ctx)

    assert managed.is_symlink(), "symlink should remain untouched"
    assert ctx.ui.warnings == [], f"no warnings expected for symlinks; got: {ctx.ui.warnings!r}"
    assert "removing" not in out.getvalue(), (
        f"no active message expected for symlinks; got: {out.getvalue()!r}"
    )


def test_clear_managed_files_skips_folded_parent_into_repo(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A managed file reached through a FOLDED parent symlink into the repo is never deleted.

    Regression for issue #153: when a managed dir (~/.config/atuin) is a single folded Stow
    symlink into the repo, the managed file inside it (config.toml) is not itself a symlink
    (is_symlink tests only the final component) but resolves to the repo's own tracked file.
    The old code unlinked it, deleting home/.config/atuin/config.toml from the repo. The guard
    must skip any target that resolves into the repo, treating the fold like a managed symlink.
    """
    dotfiles, home_dir = _setup_repo(tmp_path)
    rel = ".config/atuin/config.toml"

    repo_src = dotfiles / "home" / rel
    repo_src.parent.mkdir(parents=True)
    repo_src.write_bytes(b"[settings]\nfilter_mode = workspace\n")

    # Fold: ~/.config/atuin is a symlink to the repo's home/.config/atuin directory, so
    # ~/.config/atuin/config.toml IS the repo file (same inode) reached through the fold.
    (home_dir / ".config").mkdir(parents=True)
    (home_dir / ".config" / "atuin").symlink_to(repo_src.parent)

    target = home_dir / rel
    assert target.is_file(), "sanity: the folded target is a real file, not a leaf symlink"
    assert not target.is_symlink(), "sanity: only the parent dir is the symlink"

    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, out = _ctx()

    stow._clear_managed_files(ctx)

    assert repo_src.exists(), "the repo's tracked config must NOT be deleted through the fold"
    assert repo_src.read_bytes() == b"[settings]\nfilter_mode = workspace\n"
    backup = repo_src.with_name(f"{repo_src.name}.pre-stow.bak")
    assert not backup.exists(), "the repo file must not be renamed to a backup either"
    assert ctx.ui.warnings == [], f"no warnings expected for a fold; got: {ctx.ui.warnings!r}"
    assert "removing" not in out.getvalue(), (
        f"no active removal message expected for a fold; got: {out.getvalue()!r}"
    )


def test_clear_managed_files_skips_missing_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A managed path that does not exist in $HOME is silently skipped."""
    dotfiles, home_dir = _setup_repo(tmp_path)
    rel = ".config/atuin/config.toml"

    repo_src = dotfiles / "home" / rel
    repo_src.parent.mkdir(parents=True)
    repo_src.write_bytes(b"repo content\n")

    # No target file created in home_dir
    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, out = _ctx()

    stow._clear_managed_files(ctx)  # must not raise

    assert ctx.ui.warnings == [], f"no warnings expected for missing file; got: {ctx.ui.warnings!r}"
    assert out.getvalue() == "", f"no output expected for missing file; got: {out.getvalue()!r}"


def test_clear_managed_files_warns_when_no_repo_copy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A real $HOME file with no repo copy emits a warn and leaves the file untouched."""
    dotfiles, home_dir = _setup_repo(tmp_path)
    rel = ".config/atuin/config.toml"

    # No repo copy — dotfiles/home/<rel> is NOT created
    target = home_dir / rel
    target.parent.mkdir(parents=True)
    target.write_bytes(b"user content\n")

    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, _ = _ctx()

    stow._clear_managed_files(ctx)

    assert target.exists(), "target must be left in place when no repo copy exists"
    assert any("no repo copy" in w for w in ctx.ui.warnings), (
        f"expected 'no repo copy' warn; got: {ctx.ui.warnings!r}"
    )


# --- _migrate_git_template_hooks -------------------------------------------------------------


def test_migrate_template_hooks_removes_prek_shims(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """prek-generated shims are removed; names appear in the active message."""
    home_dir = tmp_path / "home_dir"
    tmpl_hooks = home_dir / ".config" / "git" / "template" / "hooks"
    tmpl_hooks.mkdir(parents=True)
    (tmpl_hooks / "pre-commit").write_text(
        "#!/bin/sh\n# File generated by prek\nexec prek run\n",
        encoding="utf-8",
    )
    (tmpl_hooks / "pre-push").write_text(
        "#!/bin/sh\n# File generated by prek\nexec prek run --hook pre-push\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("HOME", str(home_dir))
    ctx, out = _ctx()

    stow._migrate_git_template_hooks(ctx)

    assert not (tmpl_hooks / "pre-commit").exists(), "prek shim pre-commit should be removed"
    assert not (tmpl_hooks / "pre-push").exists(), "prek shim pre-push should be removed"
    output = out.getvalue()
    assert "migrated git template to notify-on-clone" in output, (
        f"expected active message about migration; got: {output!r}"
    )
    assert "pre-commit" in output, (
        f"shim name 'pre-commit' should appear in message; got: {output!r}"
    )
    assert "pre-push" in output, f"shim name 'pre-push' should appear in message; got: {output!r}"


def test_migrate_template_hooks_leaves_hand_written_hooks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A hook without the prek marker is left untouched (never clobbered)."""
    home_dir = tmp_path / "home_dir"
    tmpl_hooks = home_dir / ".config" / "git" / "template" / "hooks"
    tmpl_hooks.mkdir(parents=True)
    hand_written = tmpl_hooks / "commit-msg"
    hand_written.write_text(
        "#!/bin/sh\n# my custom hook\necho checking message\n", encoding="utf-8"
    )

    monkeypatch.setenv("HOME", str(home_dir))
    ctx, out = _ctx()

    stow._migrate_git_template_hooks(ctx)

    assert hand_written.exists(), "hand-written hook without prek marker should not be removed"
    assert "migrated" not in out.getvalue(), (
        f"no active message expected when no shims removed; got: {out.getvalue()!r}"
    )


def test_migrate_template_hooks_skips_symlinks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A symlink in the template hooks directory is not touched even if it targets prek content."""
    home_dir = tmp_path / "home_dir"
    tmpl_hooks = home_dir / ".config" / "git" / "template" / "hooks"
    tmpl_hooks.mkdir(parents=True)

    real_target = tmp_path / "real_hook.sh"
    real_target.write_text("# File generated by prek\n", encoding="utf-8")
    hook_link = tmpl_hooks / "pre-commit"
    hook_link.symlink_to(real_target)

    monkeypatch.setenv("HOME", str(home_dir))
    ctx, out = _ctx()

    stow._migrate_git_template_hooks(ctx)

    assert hook_link.is_symlink(), "symlink should be skipped and left in place"
    assert "migrated" not in out.getvalue(), (
        f"no active message expected when only symlinks present; got: {out.getvalue()!r}"
    )


def test_migrate_template_hooks_is_noop_when_dir_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When the template hooks directory does not exist, the function is a silent no-op."""
    home_dir = tmp_path / "home_dir"
    home_dir.mkdir()

    monkeypatch.setenv("HOME", str(home_dir))
    ctx, out = _ctx()

    stow._migrate_git_template_hooks(ctx)  # must not raise

    assert ctx.ui.warnings == [], f"no warnings expected; got: {ctx.ui.warnings!r}"
    assert out.getvalue() == "", f"no output expected; got: {out.getvalue()!r}"


# --- _migrate_gitconfig ----------------------------------------------------------------------


def test_migrate_gitconfig_emits_active_when_identical_to_baseline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A .gitconfig identical to the repo baseline is removed; an active message is emitted."""
    dotfiles, home_dir = _setup_repo(tmp_path)
    baseline_content = b"[core]\n\tautocrlf = input\n"

    baseline = dotfiles / "home" / ".gitconfig"
    baseline.parent.mkdir(parents=True)
    baseline.write_bytes(baseline_content)

    target = home_dir / ".gitconfig"
    target.write_bytes(baseline_content)

    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, out = _ctx()

    stow._migrate_gitconfig(ctx)

    assert not target.exists(), "identical .gitconfig should have been removed"
    assert "removed" in out.getvalue(), (
        f"expected active 'removed' message; got: {out.getvalue()!r}"
    )
    assert ctx.ui.warnings == [], f"no warnings expected; got: {ctx.ui.warnings!r}"


def test_migrate_gitconfig_warns_and_backs_up_differing_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A differing .gitconfig is backed up and its contents migrated; a warn is emitted."""
    dotfiles, home_dir = _setup_repo(tmp_path)

    baseline = dotfiles / "home" / ".gitconfig"
    baseline.parent.mkdir(parents=True)
    baseline.write_bytes(b"[core]\n\tautocrlf = input\n")

    target = home_dir / ".gitconfig"
    target.write_bytes(b"[user]\n\tname = Tyler\n\temail = tyler@example.com\n")

    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, _ = _ctx()

    stow._migrate_gitconfig(ctx)

    backup = home_dir / ".gitconfig.pre-stow.bak"
    assert not target.exists(), ".gitconfig should have been moved to backup"
    assert backup.exists(), f"backup should exist: {backup}"
    assert any("backed up" in w for w in ctx.ui.warnings), (
        f"expected warn about backup; got: {ctx.ui.warnings!r}"
    )


def test_migrate_gitconfig_is_noop_when_gitconfig_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When ~/.gitconfig does not exist, _migrate_gitconfig returns silently."""
    dotfiles, home_dir = _setup_repo(tmp_path)

    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, out = _ctx()

    stow._migrate_gitconfig(ctx)  # must not raise

    assert ctx.ui.warnings == [], f"no warnings expected; got: {ctx.ui.warnings!r}"
    assert out.getvalue() == "", f"no output expected; got: {out.getvalue()!r}"


def test_migrate_gitconfig_is_noop_when_gitconfig_is_symlink(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A symlinked ~/.gitconfig (already stow-managed) is left untouched."""
    dotfiles, home_dir = _setup_repo(tmp_path)

    real_gitconfig = tmp_path / "real_gitconfig"
    real_gitconfig.write_bytes(b"[user]\n\tname = Tyler\n")
    symlink = home_dir / ".gitconfig"
    symlink.symlink_to(real_gitconfig)

    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, out = _ctx()

    stow._migrate_gitconfig(ctx)

    assert symlink.is_symlink(), "symlink should remain untouched"
    assert ctx.ui.warnings == [], f"no warnings expected; got: {ctx.ui.warnings!r}"
    assert out.getvalue() == "", f"no output expected; got: {out.getvalue()!r}"


def test_migrate_gitconfig_raises_system_exit_on_oserror(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An OSError from gitconfig_migrate triggers SystemExit(1) after an err message."""
    dotfiles, home_dir = _setup_repo(tmp_path)

    def _boom(*_args: object, **_kwargs: object) -> str:
        msg = "permission denied"
        raise OSError(msg)

    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setattr(stow, "gitconfig_migrate", _boom)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, _, err_out = _ctx_err()

    with pytest.raises(SystemExit) as exc_info:
        stow._migrate_gitconfig(ctx)

    assert exc_info.value.code == 1, f"expected SystemExit(1); got code={exc_info.value.code!r}"
    assert "adopt" in err_out.getvalue(), (
        f"expected err message about adoption; got: {err_out.getvalue()!r}"
    )


# --- _stow_preflight_and_apply ---------------------------------------------------------------


def test_stow_preflight_exits_on_nonzero_preflight(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A non-zero preflight stow dry-run raises SystemExit(1) and surfaces conflict lines."""
    dotfiles, home_dir = _setup_repo(tmp_path)
    conflict_output = (
        "WARNING! stowing home would cause conflicts:\n"
        "  * cannot stow /repo/home/.config/fish/config.fish over existing target\n"
        "  * cannot stow /repo/home/.bashrc over existing target\n"
        "All operations aborted.\n"
    )
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(
        commands,
        "run",
        _fake_stow_run(calls, preflight_rc=1, preflight_stderr=conflict_output),
    )
    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, out, err_out = _ctx_err()

    with pytest.raises(SystemExit) as exc_info:
        stow._stow_preflight_and_apply(ctx)

    assert exc_info.value.code == 1, f"expected SystemExit(1); got code={exc_info.value.code!r}"
    assert "already exist in $HOME" in err_out.getvalue(), (
        f"expected conflict error; got: {err_out.getvalue()!r}"
    )
    assert "cannot stow" in out.getvalue(), (
        f"expected conflict lines in stdout; got: {out.getvalue()!r}"
    )


def test_stow_preflight_dry_run_argv_contains_n_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The preflight stow call carries -n; the apply call does not."""
    dotfiles, home_dir = _setup_repo(tmp_path)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_stow_run(calls))
    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, _ = _ctx()

    stow._stow_preflight_and_apply(ctx)

    dry_run_calls = [c for c in calls if "-n" in c.argv]
    apply_calls = [c for c in calls if "-n" not in c.argv]
    assert dry_run_calls, "at least one dry-run call (with -n) expected"
    assert apply_calls, "at least one apply call (without -n) expected"
    assert all("-n" in c.argv for c in dry_run_calls), "all preflight calls should have -n"
    assert all("-n" not in c.argv for c in apply_calls), "apply calls must not have -n"


def test_stow_preflight_and_apply_succeeds_without_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A clean preflight + successful apply returns normally and emits the active status."""
    dotfiles, home_dir = _setup_repo(tmp_path)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_stow_run(calls))
    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, out = _ctx()

    stow._stow_preflight_and_apply(ctx)  # must not raise

    assert "checking for conflicts" in out.getvalue(), (
        f"expected active 'checking for conflicts' message; got: {out.getvalue()!r}"
    )


def test_stow_apply_exits_on_failed_apply(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A clean preflight but a failed stow apply raises SystemExit(1)."""
    dotfiles, home_dir = _setup_repo(tmp_path)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_stow_run(calls, apply_rc=1))
    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, _, err_out = _ctx_err()

    with pytest.raises(SystemExit) as exc_info:
        stow._stow_preflight_and_apply(ctx)

    assert exc_info.value.code == 1, f"expected SystemExit(1); got code={exc_info.value.code!r}"
    assert "stow failed" in err_out.getvalue(), (
        f"expected err about failed stow apply; got: {err_out.getvalue()!r}"
    )


# --- stow_dotfiles (end-to-end happy path) ---------------------------------------------------


def test_stow_dotfiles_happy_path_emits_ok(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """stow_dotfiles emits the final ok when there are no managed files, hooks, or gitconfig.

    No managed files exist in $HOME, the git template hooks dir is absent, ~/.gitconfig is
    absent, and the fake stow commands return success — the happy path.
    """
    dotfiles, home_dir = _setup_repo(tmp_path)
    # home_dir has no managed files, no .config/git/template/hooks/, no .gitconfig
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_stow_run(calls))
    monkeypatch.setattr(commands, "which", lambda name: f"/usr/bin/{name}")  # stow present
    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, out = _ctx()

    stow.stow_dotfiles(ctx)

    assert "dotfiles symlinked (stow, 0 conflicts)" in out.getvalue(), (
        f"expected final ok message; got: {out.getvalue()!r}"
    )
    assert ctx.ui.warnings == [], f"no warnings expected on happy path; got: {ctx.ui.warnings!r}"


def test_stow_dotfiles_aborts_clearly_when_stow_is_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A missing `stow` binary fails fast with a clear message, not a phantom conflict abort.

    On Linux/WSL the package phase that installs stow is deferred, so stow can be absent. The
    guard must catch that up front rather than letting the preflight misread stow's exit 127.
    """
    dotfiles, home_dir = _setup_repo(tmp_path)
    monkeypatch.setattr(commands, "which", lambda _name: None)  # stow not installed
    monkeypatch.setattr(stow, "DOTFILES", dotfiles)
    monkeypatch.setenv("HOME", str(home_dir))
    ctx, _out, err = _ctx_err()

    with pytest.raises(SystemExit) as excinfo:
        stow.stow_dotfiles(ctx)

    assert excinfo.value.code == 1
    assert "stow isn't installed" in err.getvalue()
