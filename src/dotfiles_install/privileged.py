# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Phase 2: the single privileged (root-requiring) block.

One ``sudo -v`` authenticates the whole contiguous block — the Touch-ID-for-sudo finalize
(macOS), fish as the login shell (``/etc/shells`` + ``chsh``, portable), and the firewall
(macOS application firewall, or ufw on Linux; WSL skips it — the Windows host owns the
firewall) — then ``sudo -k`` drops the ticket so nothing downstream (the fisher/Claude
``curl|bash`` installers) runs with a warm timestamp. The ticket is acquired *after*
``brew bundle`` by design (the bundle invalidates any earlier sudo timestamp), so it can't
fail fast: a declined/failed auth WARNS and skips only these privileged steps — stow and
every other non-root step still run (losing root must not cost the user their symlinks).

:func:`enable_touch_id_sudo` is shared with the pre-bundle call site in phase 1
(:mod:`dotfiles_install.brew_bundle`): the same helper writes pam_tid-only before the bundle
(``pam_reattach.so`` isn't installed yet) and the pam_reattach+pam_tid pair after it. The PAM
content and whitespace match what ``uninstall.sh`` recognizes as ours.

Ported from ``install.sh`` phase 2 (the privileged block) and its shared ``enable_touch_id_sudo``.
"""

from __future__ import annotations

import os
import pwd
from pathlib import Path
from typing import TYPE_CHECKING

from dotfiles_install import commands
from dotfiles_install.os_detect import OS, current_os

if TYPE_CHECKING:
    from dotfiles_install.context import InstallContext

# Filesystem touchpoints, as module constants so tests can repoint them at a tmp_path.
_PAM_SUDO = Path("/etc/pam.d/sudo")
_PAM_SUDO_LOCAL = Path("/etc/pam.d/sudo_local")
_ETC_SHELLS = Path("/etc/shells")

# The PAM lines, whitespace-for-whitespace identical to install.sh's `enable_touch_id_sudo` and
# recognized by `uninstall.sh` (un_pam_is_ours). pam_reattach MUST precede pam_tid so
# Touch ID keeps working inside tmux/screen.
_PAM_TID_LINE = "auth       sufficient     pam_tid.so"
_PAM_REATTACH_TEMPLATE = "auth       optional       {path}"

_SOCKETFILTERFW = "/usr/libexec/ApplicationFirewall/socketfilterfw"


def privileged_setup(ctx: InstallContext) -> None:
    """Run the single root-requiring block off one sudo ticket; skip (warn) if auth fails."""
    if not commands.run_ok(["sudo", "-v"]):
        ctx.ui.warn(
            "couldn't authenticate for sudo — skipping privileged setup (fish as the default "
            "shell, the firewall, and on macOS Touch ID for sudo); re-run install.sh as an "
            "administrator to finish these",
        )
        return
    target = current_os()
    try:
        if target == OS.MACOS:
            enable_touch_id_sudo(ctx)  # pam_tid/pam_reattach exist only on macOS
        _set_fish_login_shell(ctx)  # chsh + /etc/shells — portable
        if target == OS.MACOS:
            _enable_firewall(ctx)
        elif target == OS.LINUX:
            _enable_ufw_firewall(ctx)
        else:
            # WSL: the Windows host owns the firewall; nothing to manage in the guest.
            ctx.ui.detail("skipping firewall setup on WSL (the Windows host manages it)")
    finally:
        # Drop the ticket promptly so nothing downstream (the fisher/Claude curl|bash installers,
        # in phases 5+) runs with a warm sudo timestamp — even if a step above raised. The CLI's
        # run-level finally (cli._run) is the global backstop for an abort before this phase runs;
        # this drop is the mirror of install.sh's in-block `sudo -k` at the end of the block.
        commands.run(["sudo", "-k"])
    ctx.ui.ok("privileged setup complete")


def enable_touch_id_sudo(ctx: InstallContext) -> None:
    """Write ``/etc/pam.d/sudo_local`` for Touch-ID sudo, idempotently; no-op when unchanged.

    Shared by the pre-bundle (phase 1) and post-bundle (phase 2) call sites: pam_reattach is
    included only once brew has installed it, so the pre-bundle write is pam_tid-only and the
    post-bundle write gains the pam_reattach line. Bails (warn) when ``/etc/pam.d/sudo`` has no
    ``sudo_local`` include (likely MDM-managed). A failed write warns and continues — it never
    aborts, because the pre-bundle call has no warm ticket and a declined auth must not sink the
    run (#65).
    """
    if not _sudo_local_supported():
        ctx.ui.warn(
            "Touch ID for sudo unavailable (/etc/pam.d/sudo has no sudo_local include — "
            "likely MDM-managed); sudo will prompt for your password",
        )
        return
    desired = _desired_pam_content()
    # Compare against the file with trailing newlines stripped, mirroring bash's `$(cat ...)`
    # command substitution — so a correct file (written as `desired\n`) reads as a no-op.
    if commands.read_text_or_empty(_PAM_SUDO_LOCAL).rstrip("\n") == desired:
        return  # already correct — and the read cost no sudo (sudo_local is world-readable)
    if commands.run_ok(
        ["sudo", "tee", str(_PAM_SUDO_LOCAL)],
        input_text=desired + "\n",
        capture=True,  # swallow tee's stdout echo (the bash original redirects to /dev/null)
    ):
        ctx.ui.ok("Touch ID for sudo enabled (/etc/pam.d/sudo_local)")
    else:
        ctx.ui.warn(
            "couldn't enable Touch ID for sudo (auth declined/failed); continuing — sudo will "
            "prompt for your password",
        )


def _sudo_local_supported() -> bool:
    """Report whether ``/etc/pam.d/sudo`` includes sudo_local (false means MDM-managed)."""
    return "sudo_local" in commands.read_text_or_empty(_PAM_SUDO)


def _desired_pam_content() -> str:
    """Build the desired sudo_local content: pam_tid, prefixed by pam_reattach when installed."""
    reattach = _pam_reattach_path()
    if reattach is not None:
        return f"{_PAM_REATTACH_TEMPLATE.format(path=reattach)}\n{_PAM_TID_LINE}"
    return _PAM_TID_LINE


def _pam_reattach_path() -> str | None:
    """Return the installed ``pam_reattach.so`` path under ``brew --prefix``, or None if absent."""
    prefix = commands.fetch(["brew", "--prefix"])  # None when brew is missing or prints nothing
    if not prefix:
        return None
    candidate = Path(prefix.strip()) / "lib" / "pam" / "pam_reattach.so"
    return str(candidate) if candidate.is_file() else None


def _set_fish_login_shell(ctx: InstallContext) -> None:
    """Register fish in ``/etc/shells`` (if absent) and ``chsh`` to it (if it isn't already)."""
    fish_bin = commands.which("fish")
    if fish_bin is None:
        ctx.ui.warn("fish not found on PATH — leaving the default shell unchanged")
        return
    if fish_bin not in commands.read_text_or_empty(_ETC_SHELLS).splitlines():
        ctx.ui.active(f"registering {fish_bin} in /etc/shells")
        if not commands.run_ok(
            ["sudo", "tee", "-a", str(_ETC_SHELLS)],
            input_text=fish_bin + "\n",
            capture=True,  # swallow tee's stdout echo
        ):
            # No point running chsh against a shell that isn't registered — warn and stop here.
            ctx.ui.warn(
                f"couldn't register {fish_bin} in /etc/shells; leaving the default shell unchanged",
            )
            return
    if os.environ.get("SHELL") == fish_bin:
        ctx.ui.ok("fish already the default shell")
        return
    ctx.ui.active("setting fish as the default shell (chsh)")
    # chsh via sudo: root sets the login shell without a second password prompt, keeping this
    # inside the single sudo session (a bare `chsh` would prompt on its own). Gate the success
    # message on the exit code — chsh fails on directory-service-managed (MDM/AD) accounts, and
    # claiming success there would be a lie.
    if commands.run_ok(["sudo", "chsh", "-s", fish_bin, _current_username()]):
        ctx.ui.ok("fish set as the default shell")
    else:
        ctx.ui.warn(
            "couldn't set fish as the default shell (chsh failed — a managed account?); "
            "set it manually with `chsh -s` once you can",
        )


def _enable_firewall(ctx: InstallContext) -> None:
    """Turn on the macOS application firewall + stealth mode, then verify (warn if unconfirmed)."""
    ctx.ui.active("enabling the macOS application firewall + stealth mode")
    # socketfilterfw can print a deprecation and no-op while still exiting 0, so the apply calls'
    # exit codes are deliberately ignored — the truth comes from --getglobalstate below.
    commands.run(["sudo", _SOCKETFILTERFW, "--setglobalstate", "on"], capture=True)
    commands.run(["sudo", _SOCKETFILTERFW, "--setstealthmode", "on"], capture=True)
    if _firewall_enabled():
        ctx.ui.ok("application firewall enabled")
    else:
        ctx.ui.warn(
            "could not confirm the firewall is on (macOS may have changed socketfilterfw); "
            "enable it in System Settings → Network → Firewall",
        )


def _firewall_enabled() -> bool:
    """Report whether ``socketfilterfw --getglobalstate`` says the firewall is enabled."""
    result = commands.run(["sudo", _SOCKETFILTERFW, "--getglobalstate"], capture=True)
    if result.returncode:
        return False
    return "enabled" in result.stdout.lower()


def _enable_ufw_firewall(ctx: InstallContext) -> None:
    """Enable ufw with default-deny-incoming on Linux; skip (warn) when ufw isn't installed.

    The Linux analogue of the macOS application firewall: ``ufw --force enable`` (--force skips
    the interactive "may disrupt ssh" prompt, which would hang an unattended install) plus the
    stock deny-incoming/allow-outgoing policy. When sshd is running, port 22 is allowed FIRST —
    default-deny-incoming hard-blocks new SSH connections (unlike the macOS app firewall), so
    without the rule a headless install driven over SSH would lock its own operator out the
    moment the firewall came up. Verified via ``ufw status`` under the same sudo ticket — the
    apply calls' exit codes aren't trusted alone, mirroring the socketfilterfw path.
    """
    if commands.which("ufw") is None:
        ctx.ui.warn(
            "ufw not installed — skipping firewall setup; install ufw and re-run install.sh "
            "(or configure your distro's firewall yourself)",
        )
        return
    ctx.ui.active("enabling the ufw firewall (default deny incoming)")
    if _sshd_running():
        ctx.ui.detail("sshd is running — allowing 22/tcp so the firewall can't cut off SSH")
        commands.run(["sudo", "ufw", "allow", "22/tcp"], capture=True)
    commands.run(["sudo", "ufw", "default", "deny", "incoming"], capture=True)
    commands.run(["sudo", "ufw", "default", "allow", "outgoing"], capture=True)
    commands.run(["sudo", "ufw", "--force", "enable"], capture=True)
    if _ufw_active():
        ctx.ui.ok("ufw firewall enabled")
    else:
        ctx.ui.warn(
            "could not confirm ufw is active; check `sudo ufw status` and enable it manually",
        )


def _sshd_running() -> bool:
    """Report whether an OpenSSH server is enabled, checking every common systemd unit shape.

    Both service names are probed (``ssh`` on Debian/Ubuntu, ``sshd`` elsewhere), plus their
    ``.socket`` units: Ubuntu 22.10+ ships socket-activated OpenSSH, where ``ssh.service`` is
    inactive until a client connects — a local-console install there would otherwise skip the
    allow rule and the new default-deny would block the (intentionally enabled) SSH server.
    """
    if commands.which("systemctl") is None:
        return False
    return any(
        commands.run_ok(["systemctl", "is-active", "--quiet", unit], capture=True)
        for unit in ("ssh", "sshd", "ssh.socket", "sshd.socket")
    )


def _ufw_active() -> bool:
    """Report whether ``ufw status`` (run under the sudo ticket) says the firewall is active.

    Deliberately probes ufw's *live* state, unlike ``verify_install.ufw_active`` which reads
    the persistent ``/etc/ufw/ufw.conf``: this runs immediately after the enable, under the
    same sudo ticket, so asking ufw directly is both possible and the strongest confirmation.
    The verify phase runs later without sudo, where only the persistent config is readable.
    """
    result = commands.run(["sudo", "ufw", "status"], capture=True)
    if result.returncode:
        return False
    return "status: active" in result.stdout.lower()


def _current_username() -> str:
    """Return the invoking user's login name (bash ``id -un``)."""
    return pwd.getpwuid(os.getuid()).pw_name
