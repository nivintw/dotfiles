# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for phase 2 (the privileged block) and the shared ``enable_touch_id_sudo``.

The behaviors that matter when porting the bash: one ``sudo -v`` gates the whole block and a
declined auth skips it (without aborting the run) and never acquires the ticket; the ticket is
always dropped (``sudo -k``) in a ``finally`` so nothing downstream inherits it; the Touch-ID
PAM write is idempotent, MDM-aware, picks pam_tid vs pam_reattach+pam_tid by what's installed,
and warns (never raises) on a failed write; the firewall is verified, not trusted; and the
exact PAM whitespace is preserved.

All subprocess goes through the ``commands`` seam, so the tests monkeypatch a single fake
``commands.run`` (``run_ok`` delegates to it) and repoint the ``/etc`` path constants at a
``tmp_path``.
"""

from __future__ import annotations

import io
import subprocess
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from rich.console import Console

from dotfiles_install import commands, privileged
from dotfiles_install.context import InstallContext
from dotfiles_install.os_detect import OS
from dotfiles_install.ui import UI

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_PAM_TID = "auth       sufficient     pam_tid.so"


def _ctx() -> tuple[InstallContext, io.StringIO]:
    """Build an install context over a wide in-memory console (wide so lines don't wrap)."""
    out = io.StringIO()
    ui = UI(stdout=Console(file=out, width=200), stderr=Console(file=io.StringIO(), width=200))
    return InstallContext(ui=ui), out


@dataclass
class _Rc:
    """Per-command exit codes a test wants the fake ``commands.run`` to return (0 = success)."""

    sudo_v: int = 0
    tee: int = 0  # the sudo_local write
    shells: int = 0  # the `tee -a /etc/shells` append
    chsh: int = 0
    getglobalstate: int = 0  # the firewall verify probe's exit code
    ufw_status: int = 0  # the `sudo ufw status` verify probe's exit code
    sshd: int = 3  # `systemctl is-active ssh[d]` — 0 = running, 3 = inactive (systemd's code)


def _fake_run(
    calls: list[SimpleNamespace],
    *,
    brew_prefix: str = "/opt/homebrew",
    firewall: str = "enabled",
    ufw: str = "active",
    rc: _Rc | None = None,
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Build a ``commands.run`` replacement that records calls and answers by argv shape."""
    rc = rc or _Rc()

    def run(
        argv: list[str],
        *,
        input_text: str | None = None,
        **_kwargs: object,  # absorb env/capture so the fake matches commands.run's signature
    ) -> subprocess.CompletedProcess[str]:
        argv = list(argv)
        calls.append(SimpleNamespace(argv=argv, input_text=input_text))
        code, stdout = 0, ""
        if argv[:2] == ["brew", "--prefix"]:
            stdout = brew_prefix
        elif argv[:2] == ["sudo", "-v"]:
            code = rc.sudo_v
        elif argv[:2] == ["sudo", "tee"]:
            code = rc.shells if argv[-1].endswith("shells") else rc.tee
        elif argv[:2] == ["sudo", "chsh"]:
            code = rc.chsh
        elif "--getglobalstate" in argv:
            code, stdout = rc.getglobalstate, f"Firewall is {firewall}."
        elif argv[:3] == ["sudo", "ufw", "status"]:
            code, stdout = rc.ufw_status, f"Status: {ufw}\n"
        elif argv[:2] == ["systemctl", "is-active"]:
            code = rc.sshd
        return subprocess.CompletedProcess(argv, code, stdout=stdout, stderr="")

    return run


def _point_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    sudo: str = "auth  include  sudo_local\n",
    sudo_local: str | None = None,
    shells: str = "/bin/bash\n/bin/zsh\n",
) -> None:
    """Repoint the three ``/etc`` path constants at tmp files, seeding their contents."""
    pam_sudo = tmp_path / "sudo"
    pam_sudo.write_text(sudo, encoding="utf-8")
    monkeypatch.setattr(privileged, "_PAM_SUDO", pam_sudo)
    pam_sudo_local = tmp_path / "sudo_local"
    if sudo_local is not None:
        pam_sudo_local.write_text(sudo_local, encoding="utf-8")
    monkeypatch.setattr(privileged, "_PAM_SUDO_LOCAL", pam_sudo_local)
    etc_shells = tmp_path / "shells"
    etc_shells.write_text(shells, encoding="utf-8")
    monkeypatch.setattr(privileged, "_ETC_SHELLS", etc_shells)


def _tee_calls(calls: list[SimpleNamespace], target: str) -> list[SimpleNamespace]:
    """Return the recorded ``sudo tee`` calls whose target path ends with ``target``."""
    return [c for c in calls if c.argv[:2] == ["sudo", "tee"] and c.argv[-1].endswith(target)]


# --- enable_touch_id_sudo --------------------------------------------------------------------


def test_touch_id_bails_when_sudo_local_is_not_included(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An MDM-managed /etc/pam.d/sudo (no sudo_local include) warns and does no sudo at all."""
    _point_paths(monkeypatch, tmp_path, sudo="auth  include  something_else\n")
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls))
    ctx, _ = _ctx()

    privileged.enable_touch_id_sudo(ctx)

    assert calls == []  # never shelled out — not even brew --prefix
    assert any("Touch ID for sudo unavailable" in w for w in ctx.ui.warnings)


def test_touch_id_writes_pam_tid_only_when_pam_reattach_absent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """With no pam_reattach.so installed, the write is the bare pam_tid line."""
    _point_paths(monkeypatch, tmp_path)
    calls: list[SimpleNamespace] = []
    # brew_prefix points at tmp_path with no lib/pam/pam_reattach.so under it.
    monkeypatch.setattr(commands, "run", _fake_run(calls, brew_prefix=str(tmp_path)))
    ctx, out = _ctx()

    privileged.enable_touch_id_sudo(ctx)

    writes = _tee_calls(calls, "sudo_local")
    assert len(writes) == 1
    assert writes[0].input_text == _PAM_TID + "\n"
    assert "Touch ID for sudo enabled" in out.getvalue()


def test_touch_id_writes_pam_reattach_pair_when_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When pam_reattach.so exists under brew --prefix, it precedes pam_tid (exact whitespace)."""
    pam_dir = tmp_path / "lib" / "pam"
    pam_dir.mkdir(parents=True)
    (pam_dir / "pam_reattach.so").write_text("", encoding="utf-8")
    _point_paths(monkeypatch, tmp_path)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, brew_prefix=str(tmp_path)))
    ctx, _ = _ctx()

    privileged.enable_touch_id_sudo(ctx)

    reattach = pam_dir / "pam_reattach.so"
    writes = _tee_calls(calls, "sudo_local")
    assert len(writes) == 1
    assert writes[0].input_text == f"auth       optional       {reattach}\n{_PAM_TID}\n"


def test_touch_id_is_idempotent_when_content_matches(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An already-correct sudo_local (trailing newline and all) triggers no write."""
    _point_paths(monkeypatch, tmp_path, sudo_local=_PAM_TID + "\n")
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, brew_prefix=str(tmp_path)))
    ctx, out = _ctx()

    privileged.enable_touch_id_sudo(ctx)

    assert _tee_calls(calls, "sudo_local") == []  # no write
    assert "Touch ID for sudo enabled" not in out.getvalue()
    assert ctx.ui.warnings == []


def test_touch_id_warns_and_does_not_raise_on_failed_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A declined/failed sudo tee warns (mirrors the #65 fix) instead of raising."""
    _point_paths(monkeypatch, tmp_path)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, brew_prefix=str(tmp_path), rc=_Rc(tee=1)))
    ctx, _ = _ctx()

    privileged.enable_touch_id_sudo(ctx)  # must not raise

    assert any("couldn't enable Touch ID for sudo" in w for w in ctx.ui.warnings)


# --- privileged_setup ------------------------------------------------------------------------


def test_setup_skips_block_and_acquires_nothing_when_sudo_declined(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A declined `sudo -v` warns, runs no further sudo (not even `sudo -k`), and returns."""
    _point_paths(monkeypatch, tmp_path)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, rc=_Rc(sudo_v=1)))
    monkeypatch.setattr(commands, "which", lambda _name: "/opt/homebrew/bin/fish")
    ctx, _ = _ctx()

    privileged.privileged_setup(ctx)

    assert [c.argv for c in calls] == [["sudo", "-v"]]  # nothing past the gate, no sudo -k
    assert any("couldn't authenticate for sudo" in w for w in ctx.ui.warnings)


def test_setup_happy_path_runs_every_step_then_drops_the_ticket(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The full block: Touch ID, /etc/shells + chsh, firewall on+verified, then `sudo -k` last."""
    _point_paths(monkeypatch, tmp_path)
    fish = "/opt/homebrew/bin/fish"
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, brew_prefix=str(tmp_path)))
    monkeypatch.setattr(commands, "which", lambda _name: fish)
    monkeypatch.setenv("SHELL", "/bin/zsh")  # differs from fish → chsh runs
    ctx, out = _ctx()

    privileged.privileged_setup(ctx)

    argvs = [c.argv for c in calls]
    assert argvs[0] == ["sudo", "-v"]
    assert _tee_calls(calls, "sudo_local")  # Touch ID written
    assert _tee_calls(calls, "shells")  # fish registered in /etc/shells
    assert ["sudo", "chsh", "-s", fish, privileged._current_username()] in argvs
    assert ["sudo", privileged._SOCKETFILTERFW, "--setglobalstate", "on"] in argvs
    assert ["sudo", privileged._SOCKETFILTERFW, "--setstealthmode", "on"] in argvs
    assert argvs[-1] == ["sudo", "-k"]  # ticket dropped last
    assert "application firewall enabled" in out.getvalue()
    assert "privileged setup complete" in out.getvalue()


def test_setup_warns_when_firewall_cannot_be_confirmed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """If --getglobalstate doesn't report enabled, warn — but still drop the ticket and finish."""
    _point_paths(monkeypatch, tmp_path)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(
        commands,
        "run",
        _fake_run(calls, brew_prefix=str(tmp_path), firewall="disabled"),
    )
    monkeypatch.setattr(commands, "which", lambda _name: "/opt/homebrew/bin/fish")
    monkeypatch.setenv("SHELL", "/bin/zsh")
    ctx, _ = _ctx()

    privileged.privileged_setup(ctx)

    assert any("could not confirm the firewall is on" in w for w in ctx.ui.warnings)
    assert [c.argv for c in calls][-1] == ["sudo", "-k"]


def test_setup_skips_shell_steps_when_already_default_and_registered(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Fish already in /etc/shells and already $SHELL → no `tee -a` and no `chsh`."""
    fish = "/opt/homebrew/bin/fish"
    _point_paths(monkeypatch, tmp_path, shells=f"/bin/bash\n{fish}\n")
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, brew_prefix=str(tmp_path)))
    monkeypatch.setattr(commands, "which", lambda _name: fish)
    monkeypatch.setenv("SHELL", fish)
    ctx, out = _ctx()

    privileged.privileged_setup(ctx)

    argvs = [c.argv for c in calls]
    assert _tee_calls(calls, "shells") == []  # not re-registered
    assert not any(a[:2] == ["sudo", "chsh"] for a in argvs)  # not re-chsh'd
    assert "fish already the default shell" in out.getvalue()


def test_setup_warns_and_skips_shell_when_fish_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Fish not on PATH → warn, skip /etc/shells and chsh, but still run firewall + drop sudo."""
    _point_paths(monkeypatch, tmp_path)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, brew_prefix=str(tmp_path)))
    monkeypatch.setattr(commands, "which", lambda _name: None)
    ctx, _ = _ctx()

    privileged.privileged_setup(ctx)

    argvs = [c.argv for c in calls]
    assert _tee_calls(calls, "shells") == []
    assert not any(a[:2] == ["sudo", "chsh"] for a in argvs)
    assert any("fish not found on PATH" in w for w in ctx.ui.warnings)
    assert argvs[-1] == ["sudo", "-k"]  # firewall + ticket-drop still happened


def test_setup_always_drops_the_ticket_even_if_a_step_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An unexpected error mid-block still drops the sudo ticket (the `finally`), then re-raises."""
    _point_paths(monkeypatch, tmp_path)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, brew_prefix=str(tmp_path)))
    monkeypatch.setattr(commands, "which", lambda _name: "/opt/homebrew/bin/fish")

    def _boom(_ctx: InstallContext) -> None:
        msg = "kaboom"
        raise RuntimeError(msg)

    monkeypatch.setattr(privileged, "_set_fish_login_shell", _boom)
    ctx, _ = _ctx()

    with pytest.raises(RuntimeError, match="kaboom"):
        privileged.privileged_setup(ctx)

    assert ["sudo", "-k"] in [c.argv for c in calls]  # ticket dropped despite the raise


def test_touch_id_writes_pam_tid_only_when_brew_prefix_is_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`brew --prefix` returning nothing (brew absent) → pam_tid-only, no reattach line."""
    _point_paths(monkeypatch, tmp_path)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, brew_prefix=""))
    ctx, _ = _ctx()

    privileged.enable_touch_id_sudo(ctx)

    writes = _tee_calls(calls, "sudo_local")
    assert len(writes) == 1
    assert writes[0].input_text == _PAM_TID + "\n"


def test_read_text_degrades_to_empty_on_a_non_missing_os_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A non-missing OSError reading sudo_local degrades to empty and writes, never raising."""
    _point_paths(monkeypatch, tmp_path)
    # A regular file standing where a directory is expected makes read_text raise
    # NotADirectoryError — exercising the broad `except OSError` rather than the missing-file path.
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")
    monkeypatch.setattr(privileged, "_PAM_SUDO_LOCAL", blocker / "sudo_local")
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, brew_prefix=str(tmp_path)))
    ctx, _ = _ctx()

    privileged.enable_touch_id_sudo(ctx)  # must not raise

    assert len(_tee_calls(calls, "sudo_local")) == 1  # read-as-empty → content differs → writes


def test_read_text_does_not_raise_on_non_utf8_sudo_local(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Non-UTF-8 bytes in sudo_local round-trip via surrogateescape, never raising on decode."""
    _point_paths(monkeypatch, tmp_path)
    # Seed sudo_local with invalid UTF-8 — a plain encoding="utf-8" read would raise (a ValueError,
    # not an OSError, so the broad OSError guard wouldn't catch it).
    (tmp_path / "sudo_local").write_bytes(b"\xff\xfe not utf-8 \x80\x81")
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, brew_prefix=str(tmp_path)))
    ctx, _ = _ctx()

    privileged.enable_touch_id_sudo(ctx)  # must not raise

    assert len(_tee_calls(calls, "sudo_local")) == 1  # garbled content differs → rewrites


def test_firewall_unconfirmed_when_getglobalstate_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A nonzero `--getglobalstate` exit is not trusted even if its stdout says 'enabled'."""
    _point_paths(monkeypatch, tmp_path)
    calls: list[SimpleNamespace] = []
    # stdout still contains "enabled", but the rc!=0 guard must override it.
    monkeypatch.setattr(
        commands,
        "run",
        _fake_run(calls, brew_prefix=str(tmp_path), firewall="enabled", rc=_Rc(getglobalstate=1)),
    )
    monkeypatch.setattr(commands, "which", lambda _name: "/opt/homebrew/bin/fish")
    monkeypatch.setenv("SHELL", "/bin/zsh")
    ctx, _ = _ctx()

    privileged.privileged_setup(ctx)

    assert any("could not confirm the firewall is on" in w for w in ctx.ui.warnings)


def test_setup_warns_when_chsh_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed `chsh` (e.g. a managed account) warns rather than falsely claiming success."""
    _point_paths(monkeypatch, tmp_path)
    fish = "/opt/homebrew/bin/fish"
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(
        commands, "run", _fake_run(calls, brew_prefix=str(tmp_path), rc=_Rc(chsh=1))
    )
    monkeypatch.setattr(commands, "which", lambda _name: fish)
    monkeypatch.setenv("SHELL", "/bin/zsh")
    ctx, out = _ctx()

    privileged.privileged_setup(ctx)

    assert any("couldn't set fish as the default shell" in w for w in ctx.ui.warnings)
    assert "fish set as the default shell" not in out.getvalue()  # no false success


def test_setup_warns_and_skips_chsh_when_shells_registration_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed `/etc/shells` append warns and skips chsh (no point), but the run continues."""
    _point_paths(monkeypatch, tmp_path)
    fish = "/opt/homebrew/bin/fish"
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(
        commands, "run", _fake_run(calls, brew_prefix=str(tmp_path), rc=_Rc(shells=1))
    )
    monkeypatch.setattr(commands, "which", lambda _name: fish)
    monkeypatch.setenv("SHELL", "/bin/zsh")
    ctx, _ = _ctx()

    privileged.privileged_setup(ctx)

    argvs = [c.argv for c in calls]
    assert any("couldn't register" in w for w in ctx.ui.warnings)
    assert not any(a[:2] == ["sudo", "chsh"] for a in argvs)  # chsh skipped after failed register
    assert argvs[-1] == ["sudo", "-k"]  # firewall + ticket-drop still ran


# --- privileged_setup: Linux / WSL ------------------------------------------------------------


def test_setup_linux_runs_ufw_and_skips_touch_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """On Linux: no Touch-ID PAM write, chsh still runs, and ufw is enabled + verified."""
    monkeypatch.setattr(privileged, "current_os", lambda: OS.LINUX)
    _point_paths(monkeypatch, tmp_path)
    fish = "/home/linuxbrew/.linuxbrew/bin/fish"
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls))
    monkeypatch.setattr(commands, "which", lambda _name: fish)
    monkeypatch.setenv("SHELL", "/bin/bash")
    ctx, out = _ctx()

    privileged.privileged_setup(ctx)

    argvs = [c.argv for c in calls]
    assert not _tee_calls(calls, "sudo_local")  # Touch ID never touched on Linux
    assert ["sudo", "chsh", "-s", fish, privileged._current_username()] in argvs
    assert ["sudo", "ufw", "default", "deny", "incoming"] in argvs
    assert ["sudo", "ufw", "default", "allow", "outgoing"] in argvs
    assert ["sudo", "ufw", "--force", "enable"] in argvs
    assert ["sudo", "ufw", "allow", "22/tcp"] not in argvs  # no sshd running -> no hole punched
    assert not any(privileged._SOCKETFILTERFW in a for a in argvs)  # no macOS firewall calls
    assert argvs[-1] == ["sudo", "-k"]
    assert "ufw firewall enabled" in out.getvalue()


def test_setup_linux_warns_when_ufw_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A Linux box without ufw warns and skips firewall setup; the rest of the block still runs."""
    monkeypatch.setattr(privileged, "current_os", lambda: OS.LINUX)
    _point_paths(monkeypatch, tmp_path)
    fish = "/home/linuxbrew/.linuxbrew/bin/fish"
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls))
    monkeypatch.setattr(commands, "which", lambda name: None if name == "ufw" else fish)
    monkeypatch.setenv("SHELL", "/bin/bash")
    ctx, _ = _ctx()

    privileged.privileged_setup(ctx)

    argvs = [c.argv for c in calls]
    assert any("ufw not installed" in w for w in ctx.ui.warnings)
    assert not any(a[:2] == ["sudo", "ufw"] for a in argvs)
    assert argvs[-1] == ["sudo", "-k"]


def test_setup_linux_warns_when_ufw_not_confirmed_active(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """If `ufw status` doesn't report active after enable, warn — but still drop the ticket."""
    monkeypatch.setattr(privileged, "current_os", lambda: OS.LINUX)
    _point_paths(monkeypatch, tmp_path)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, ufw="inactive"))
    monkeypatch.setattr(commands, "which", lambda _name: "/home/linuxbrew/.linuxbrew/bin/fish")
    monkeypatch.setenv("SHELL", "/bin/bash")
    ctx, _ = _ctx()

    privileged.privileged_setup(ctx)

    assert any("could not confirm ufw is active" in w for w in ctx.ui.warnings)
    assert [c.argv for c in calls][-1] == ["sudo", "-k"]


def test_setup_wsl_skips_firewall_entirely(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """On WSL neither firewall is touched (the Windows host owns it); shell setup still runs."""
    monkeypatch.setattr(privileged, "current_os", lambda: OS.WSL)
    _point_paths(monkeypatch, tmp_path)
    fish = "/home/linuxbrew/.linuxbrew/bin/fish"
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls))
    monkeypatch.setattr(commands, "which", lambda _name: fish)
    monkeypatch.setenv("SHELL", "/bin/bash")
    ctx, out = _ctx()

    privileged.privileged_setup(ctx)

    argvs = [c.argv for c in calls]
    assert not any(a[:2] == ["sudo", "ufw"] for a in argvs)
    assert not any(privileged._SOCKETFILTERFW in a for a in argvs)
    assert not _tee_calls(calls, "sudo_local")
    assert ["sudo", "chsh", "-s", fish, privileged._current_username()] in argvs
    assert "privileged setup complete" in out.getvalue()


def test_setup_linux_allows_ssh_before_enabling_ufw(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """With sshd active, 22/tcp is allowed BEFORE ufw enables.

    A headless SSH install must not lock out its own operator when default-deny-incoming
    comes up.
    """
    monkeypatch.setattr(privileged, "current_os", lambda: OS.LINUX)
    _point_paths(monkeypatch, tmp_path)
    calls: list[SimpleNamespace] = []
    monkeypatch.setattr(commands, "run", _fake_run(calls, rc=_Rc(sshd=0)))
    monkeypatch.setattr(commands, "which", lambda _name: "/home/linuxbrew/.linuxbrew/bin/fish")
    monkeypatch.setenv("SHELL", "/bin/bash")
    ctx, out = _ctx()

    privileged.privileged_setup(ctx)

    argvs = [c.argv for c in calls]
    allow = argvs.index(["sudo", "ufw", "allow", "22/tcp"])
    enable = argvs.index(["sudo", "ufw", "--force", "enable"])
    assert allow < enable, "the SSH allow rule must land before the firewall comes up"
    assert "ufw firewall enabled" in out.getvalue()
