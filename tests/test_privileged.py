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
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from rich.console import Console

from dotfiles_install import commands, privileged
from dotfiles_install.context import InstallContext
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


def _fake_run(
    calls: list[SimpleNamespace],
    *,
    brew_prefix: str = "/opt/homebrew",
    sudo_v_rc: int = 0,
    tee_rc: int = 0,
    firewall: str = "enabled",
) -> Callable[..., subprocess.CompletedProcess[str]]:
    """Build a ``commands.run`` replacement that records calls and answers by argv shape."""

    def run(
        argv: list[str],
        *,
        env: object = None,  # noqa: ARG001 — accepted to match the real signature
        capture: bool = False,  # noqa: ARG001
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        argv = list(argv)
        calls.append(SimpleNamespace(argv=argv, input_text=input_text))
        if argv[:2] == ["brew", "--prefix"]:
            return subprocess.CompletedProcess(argv, 0, stdout=brew_prefix, stderr="")
        if argv[:2] == ["sudo", "-v"]:
            return subprocess.CompletedProcess(argv, sudo_v_rc, stdout="", stderr="")
        if argv[:2] == ["sudo", "tee"]:
            return subprocess.CompletedProcess(argv, tee_rc, stdout="", stderr="")
        if "--getglobalstate" in argv:
            return subprocess.CompletedProcess(
                argv, 0, stdout=f"Firewall is {firewall}.", stderr=""
            )
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

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
    monkeypatch.setattr(commands, "run", _fake_run(calls, brew_prefix=str(tmp_path), tee_rc=1))
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
    monkeypatch.setattr(commands, "run", _fake_run(calls, sudo_v_rc=1))
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
