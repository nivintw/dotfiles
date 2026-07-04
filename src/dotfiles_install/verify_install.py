# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Verify-install checks, OK/BAD emitter, and the phase-18 summary.

The unit-testable predicates the summary is built from — resolving a symlink target into the
repo, rejecting non-object JSON, matching an ``[include]`` path through ``~`` expansion,
abbreviating ``$HOME`` to ``~`` for display, counting enrolled Touch ID templates, and resolving
the repo's pre-push hook path (via git, so a custom ``core.hooksPath`` and worktrees both
resolve correctly) — plus the heavier live-state probes, chosen per OS: ``brew bundle check``
everywhere, the firewall via ``socketfilterfw`` (macOS) or ufw's persistent
``/etc/ufw/ufw.conf`` (Linux), the login shell via ``dscl`` (macOS) or the passwd database
(Linux), and ``pam_tid`` (macOS only; WSL also skips the firewall — the Windows host owns it).
:func:`iter_records` aggregates them into
``("OK"|"BAD", msg)`` records, and :func:`verify_and_summarize` is the phase-18 body that renders
the closing summary.

Ported from install.sh's verification step (predicates pinned by ``tests/test_verify_install.py``).
This is now the single source of truth for the install summary, the ``dotfiles-install --verify``
re-check (``dotfiles-doctor``), and the ``--verify-stream`` record stream the vm-smoke harness gates
on.
"""

from __future__ import annotations

import json
import os
import pwd
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from dotfiles_install import commands
from dotfiles_install.brewfile import brewfile_core
from dotfiles_install.bundle_select import parse_bundles
from dotfiles_install.layout import DOTFILES
from dotfiles_install.os_detect import OS, current_os
from dotfiles_install.stow import PREK_SHIM_MARKER

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from dotfiles_install.context import InstallContext

type Record = tuple[str, str]  # ("OK" | "BAD", message)

_TEMPLATE_RE = re.compile(r"(\d+) biometric template")


def symlink_into_repo(link: Path, repo: Path) -> bool:
    """Report whether ``link`` is a symlink resolving to a path strictly inside ``repo``.

    Matches the bash original: ``repo`` must exist (it failed when ``cd "$repo"`` did) and the
    target must be *under* the repo, not the repo root itself.
    """
    if not link.is_symlink() or not repo.is_dir():
        return False
    target = link.readlink()
    if not target.is_absolute():
        target = link.parent / target
    return repo.resolve() in target.resolve().parents


def is_json_object(path: Path) -> bool:
    """Report whether ``path`` exists and contains a JSON object."""
    if not path.is_file():
        return False
    # Separate single-exception clauses rather than a tuple: the parenthesis-free PEP 758 form
    # ruff would enforce (`except A, B:`) reads like the Python-2 `except E, name:` bug.
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return False
    except UnicodeDecodeError:
        return False
    except json.JSONDecodeError:
        return False
    return isinstance(value, dict)


def gitconfig_includes(cfg: Path, want: Path | str) -> bool:
    """Report whether the git config at ``cfg`` has an ``include.path`` of ``want``.

    Tilde-aware: ``~`` is expanded on both the stored and wanted paths before comparison.
    """
    if not cfg.exists():
        return False
    git = shutil.which("git")
    if git is None:
        return False
    result = subprocess.run(
        [git, "config", "-f", str(cfg), "--get-all", "include.path"],
        capture_output=True,
        text=True,
        check=False,
    )
    wanted = Path(str(want)).expanduser()
    return any(Path(line).expanduser() == wanted for line in result.stdout.splitlines())


def prepush_hook_path(dotfiles: Path) -> Path | None:
    """Resolve the dotfiles repo's pre-push hook path via git, or ``None`` if unresolvable.

    Always asks git itself — never assumes ``.git/hooks`` — so a custom ``core.hooksPath``
    and a worktree's shared git-common-dir (its own ``.git`` is a file pointing elsewhere)
    both resolve correctly. Returns ``None`` when ``dotfiles`` isn't inside a git repo at all.
    """
    result = commands.run(
        ["git", "-C", str(dotfiles), "rev-parse", "--git-path", "hooks/pre-push"],
        capture=True,
    )
    path = (result.stdout or "").strip()
    if result.returncode != 0 or not path:
        return None
    hook = Path(path)
    return hook if hook.is_absolute() else dotfiles / hook


def tilde(path: Path | str) -> str:
    """Abbreviate a leading ``$HOME`` in ``path`` to ``~``, leaving other paths unchanged."""
    text = str(path)
    home = str(Path.home())
    if text == home:
        return "~"
    prefix = f"{home}/"
    if text.startswith(prefix):
        return f"~/{text[len(prefix) :]}"
    return text


def touchid_enrolled_count() -> int:
    """Return the number of enrolled Touch ID templates, or 0 when unavailable."""
    bioutil = shutil.which("bioutil")
    if bioutil is None:
        return 0
    result = subprocess.run(
        [bioutil, "-c"],
        capture_output=True,
        text=True,
        check=False,
    )
    return sum(int(match.group(1)) for match in _TEMPLATE_RE.finditer(result.stdout))


# --- live-state probes (shell out via the commands seam; not pure) ----------

_SUDO_LOCAL = Path("/etc/pam.d/sudo_local")
_SOCKETFILTERFW = Path("/usr/libexec/ApplicationFirewall/socketfilterfw")
_UFW_CONF = Path("/etc/ufw/ufw.conf")

# Key dotfiles symlinks that must resolve into the repo, relative to $HOME.
_KEY_LINKS = (".gitconfig", ".config/fish/config.fish", ".claude/CLAUDE.md")


def pam_tid_enabled() -> bool:
    """Report whether Touch ID for sudo is wired into /etc/pam.d/sudo_local (readable as user)."""
    return "pam_tid.so" in commands.read_text_or_empty(_SUDO_LOCAL)


def application_firewall_enabled() -> bool:
    """Report whether the application firewall's global state is enabled (readable without sudo)."""
    # Gate on executability (bash `[ -x ]`): a present-but-non-executable binary must degrade to
    # False, not raise PermissionError out of the run() — which only catches FileNotFoundError.
    if not os.access(_SOCKETFILTERFW, os.X_OK):
        return False
    result = commands.run([str(_SOCKETFILTERFW), "--getglobalstate"], capture=True)
    return "enabled" in (result.stdout or "").lower()


def login_shell() -> str | None:
    """Return the current user's login shell, or ``None`` if unreadable.

    macOS asks Directory Services (``dscl``) — the authority under MDM/AD management, where the
    passwd database can lag. Linux reads the passwd database directly (``pwd.getpwuid``, the
    same NSS-backed source ``getent passwd`` uses) — no subprocess needed.
    """
    if current_os() != OS.MACOS:
        try:
            shell = pwd.getpwuid(os.getuid()).pw_shell
        except KeyError:
            # A UID with no passwd entry (some containers) must degrade to a BAD record,
            # not crash the whole verify stream.
            return None
        return shell or None
    # Resolve the user from the real uid (like bash `id -un`), NOT getpass.getuser(), which
    # trusts $USER/$LOGNAME and would query the wrong account under `su` or a stale env.
    username = pwd.getpwuid(os.getuid()).pw_name
    result = commands.run(
        ["dscl", ".", "-read", f"/Users/{username}", "UserShell"],
        capture=True,
    )
    # "UserShell: /opt/homebrew/bin/fish" — the shell path is the second field.
    match (result.stdout or "").split():
        case ["UserShell:", shell, *_]:
            return shell
        case _:
            return None


def ufw_active() -> bool:
    """Report whether the ufw firewall is enabled, readable without sudo.

    ``ufw status`` needs root, and the ``ufw.service`` systemd unit is a oneshot that stays
    "active (exited)" even after ``ufw disable`` — so neither reflects enablement for an
    unprivileged probe. Read ufw's own persistent state instead: ``ufw enable``/``disable``
    write ``ENABLED=yes``/``no`` to the world-readable ``/etc/ufw/ufw.conf`` (the Linux
    analogue of ``socketfilterfw --getglobalstate`` reading the firewall's configured state).
    """
    for line in commands.read_text_or_empty(_UFW_CONF).splitlines():
        key, _, value = line.partition("=")
        if key.strip() == "ENABLED":
            return value.strip() == "yes"
    return False


# --- OK/BAD record emitter --------------------------------------------------


def iter_records(dotfiles: Path, *, core: bool) -> Iterator[Record]:
    """Yield an ``("OK"|"BAD", message)`` record per post-install check.

    Re-derives the intended end state and reports it; never mutates anything and never needs
    sudo (every probe reads as the user). The single source of truth for the phase-18 install
    summary, the ``dotfiles-install --verify`` re-check (``dotfiles-doctor``), and the
    ``--verify-stream`` record stream the vm-smoke harness gates on.

    OS-aware: each check either probes per-OS (login shell, firewall) or applies only where the
    state exists — Touch ID is macOS-only, and WSL yields no firewall record at all (the Windows
    host owns the firewall, so there is nothing in the guest to verify).
    """
    target = current_os()
    yield from _brew_records(dotfiles, core=core)
    yield _login_shell_record()
    if target == OS.MACOS:
        yield _touch_id_record()
    if target != OS.WSL:
        yield _firewall_record()
    yield from _symlink_records(dotfiles)
    yield _settings_record()
    yield _gitconfig_include_record()
    yield _prepush_hook_record(dotfiles)


def verify_and_summarize(ctx: InstallContext) -> None:
    """Phase 18: render the closing post-install summary (reads only, never gates).

    The cli registry loop already prints the ``[18] Verification & summary`` step header, so this
    adds no banner of its own. It closes with the same two detail lines as the bash phase 17.
    """
    _summarize(ctx)


def run_check(ctx: InstallContext) -> int:
    """Render the verification summary standalone and return the problem count (0 = healthy).

    Backs ``dotfiles-install --verify`` and, through it, the ``dotfiles-doctor`` command — the
    caller turns the count into an exit code.
    """
    return _summarize(ctx)


def emit_stream(*, core: bool, write: Callable[[str], object]) -> None:
    """Emit the raw ``OK<TAB>msg`` / ``BAD<TAB>msg`` records + a trailing ``VERIFY_DONE<TAB>count``.

    The machine-readable stream the vm-smoke harness's ``evaluate_stream`` gates on (it tolerates
    only the no-Touch-ID BAD and fails closed when the sentinel is missing). The sentinel carries
    the BAD count (mirroring the bash original, which appended the verify exit status), so it stays
    honest rather than always claiming zero. Replaces sourcing the retired
    ``scripts/verify_install.sh`` in the guest.
    """
    problems = 0
    for status, message in iter_records(DOTFILES, core=core):
        if status != "OK":
            problems += 1
        write(f"{status}\t{message}")
    write(f"VERIFY_DONE\t{problems}")


def _summarize(ctx: InstallContext) -> int:
    """Partition the records into the Verified / Needs-attention summary + closing hints.

    Returns the problem count. Closing lines mirror the bash phase 17: a retry hint when anything
    needs attention, then the unconditional restart reminder.
    """
    verified: list[str] = []
    problems: list[str] = []
    for status, message in iter_records(DOTFILES, core=ctx.core):
        (verified if status == "OK" else problems).append(message)
    ctx.ui.summary(verified, problems)
    # "Needs attention" = failed checks plus the run's warnings (what ui.summary folds in).
    if problems or ctx.ui.warnings:
        ctx.ui.detail(
            "re-run ~/dotfiles/install.sh to retry, or 'dotfiles-install --verify' to re-check.",
        )
    ctx.ui.detail("Restart your shell (or run 'exec fish') to pick everything up.")
    return len(problems)


def _record(ok_message: str, bad_message: str, *, passed: bool) -> Record:
    """Build an OK record when ``passed``, else a BAD one."""
    return ("OK", ok_message) if passed else ("BAD", bad_message)


def _brew_records(dotfiles: Path, *, core: bool) -> Iterator[Record]:
    """Records for the Homebrew baseline (or --core subset), opt-in bundles, and Brewfile.local."""
    if commands.which("brew") is None:
        yield ("BAD", "Homebrew not found on PATH — the bundle step did not complete")
        return
    brewfile = dotfiles / "Brewfile"
    if core:
        core_text = brewfile_core(commands.read_text_or_empty(brewfile))
        core_ok, core_bf = _brew_bundle_check_text(core_text)
        yield _record(
            "Homebrew core (CLI formulae) packages all installed",
            f"Homebrew core packages missing — re-check: "
            f"brew bundle check --verbose --file={core_bf} (kept for inspection)",
            passed=core_ok,
        )
    else:
        yield _record(
            "Homebrew baseline packages all installed",
            f"Homebrew baseline packages missing — run: "
            f"brew bundle check --verbose --file={brewfile}",
            passed=_brew_bundle_check(brewfile),
        )
    yield from _opt_in_bundle_records(dotfiles)
    yield from _brewfile_local_records()


def _brew_bundle_check(brewfile: Path) -> bool:
    """Report whether ``brew bundle check`` passes for ``brewfile`` (quietly)."""
    return commands.run_ok(["brew", "bundle", "check", f"--file={brewfile}"], capture=True)


def _brew_bundle_check_text(brewfile_text: str) -> tuple[bool, Path]:
    """``brew bundle check`` the cask-stripped --core subset; return (passed, the temp Brewfile).

    ``brew bundle check`` needs a real path, so the subset is written to a temp file. On success
    the temp file is removed; on FAILURE it is kept so the BAD message can point the user at a
    runnable ``--file=`` re-check (matching the bash original). ``surrogateescape`` round-trips any
    non-UTF-8 bytes from the source Brewfile, so the write can't raise UnicodeEncodeError.
    """
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".brewfile",
        prefix="brewfile-core",
        delete=False,
        encoding="utf-8",
        errors="surrogateescape",
    ) as handle:
        handle.write(brewfile_text)
        tmp = Path(handle.name)
    passed = _brew_bundle_check(tmp)
    if passed:
        tmp.unlink(missing_ok=True)
    return passed, tmp


def _opt_in_bundle_records(dotfiles: Path) -> Iterator[Record]:
    """A record per selected opt-in bundle (read from the persisted selection file)."""
    # Read the selection with the same parser the installer wrote it with, so they can't drift.
    sel = Path.home() / ".config" / "dotfiles" / "bundles"
    for name in parse_bundles(sel):
        brewfile = dotfiles / "Brewfile.d" / f"{name}.brewfile"
        if not brewfile.is_file():
            continue
        yield _record(
            f"opt-in bundle '{name}' installed",
            f"opt-in bundle '{name}' has missing packages — run: "
            f"brew bundle check --verbose --file={brewfile}",
            passed=_brew_bundle_check(brewfile),
        )


def _brewfile_local_records() -> Iterator[Record]:
    """A record for a machine-private ``Brewfile.local`` when it declares anything."""
    local_bf = Path.home() / ".config" / "dotfiles" / "Brewfile.local"
    if not _has_directive(local_bf):
        return
    yield _record(
        "machine-private Brewfile.local installed",
        f"Brewfile.local has missing packages — run: brew bundle check --verbose --file={local_bf}",
        passed=_brew_bundle_check(local_bf),
    )


def _has_directive(path: Path) -> bool:
    """Report whether ``path`` has any non-blank, non-comment line (empty/missing → False)."""
    return any(
        (stripped := line.strip()) and not stripped.startswith("#")
        for line in commands.read_text_or_empty(path).splitlines()
    )


def _login_shell_record() -> Record:
    """OK when fish is installed and is the login shell."""
    fish = commands.which("fish")
    shell = login_shell()
    return _record(
        "fish is the login shell",
        f"login shell is '{shell or 'unknown'}', not fish ({fish or 'not installed'})",
        passed=fish is not None and shell == fish,
    )


def _touch_id_record() -> Record:
    """OK when Touch ID for sudo is enabled AND a fingerprint is enrolled."""
    if not pam_tid_enabled():
        return (
            "BAD",
            "Touch ID for sudo not enabled (/etc/pam.d/sudo_local) — sudo will prompt for your "
            "password",
        )
    enrolled = touchid_enrolled_count()
    if enrolled >= 1:
        return ("OK", f"Touch ID for sudo enabled ({enrolled} fingerprint(s) enrolled)")
    return (
        "BAD",
        "Touch ID for sudo is enabled but NO fingerprint is enrolled — sudo will keep prompting "
        "for your password. Enroll one in System Settings → Touch ID & Password (or this Mac has "
        "no Touch ID sensor).",
    )


def _firewall_record() -> Record:
    """OK when the OS firewall is enabled (macOS application firewall, or ufw on Linux)."""
    if current_os() == OS.LINUX:
        # Tell "ufw is off" apart from "ufw isn't installed" — `sudo ufw enable` is only
        # actionable advice in the first case.
        if commands.which("ufw") is None:
            return _record(
                "ufw firewall active",
                "ufw is not installed — install it and re-run install.sh (or configure your "
                "distro's firewall yourself)",
                passed=False,
            )
        return _record(
            "ufw firewall active",
            "ufw firewall is OFF — enable it with `sudo ufw enable` (or re-run install.sh)",
            passed=ufw_active(),
        )
    return _record(
        "application firewall enabled",
        "application firewall is OFF — enable it in System Settings → Network → Firewall",
        passed=application_firewall_enabled(),
    )


def _symlink_records(dotfiles: Path) -> Iterator[Record]:
    """A record per key dotfiles symlink that should resolve into the repo."""
    for rel in _KEY_LINKS:
        link = Path.home() / rel
        yield _record(
            f"symlinked into repo: {tilde(link)}",
            f"not symlinked into repo (stow may not have run): {tilde(link)}",
            passed=symlink_into_repo(link, dotfiles),
        )


def _settings_record() -> Record:
    """OK when the generated Claude settings file is a valid JSON object."""
    settings = Path.home() / ".claude" / "settings.json"
    return _record(
        f"{tilde(settings)} is valid JSON",
        f"{tilde(settings)} missing or not a JSON object",
        passed=is_json_object(settings),
    )


def _gitconfig_include_record() -> Record:
    """OK when ~/.gitconfig [include]s the machine-local overlay."""
    gitconfig = Path.home() / ".gitconfig"
    gitconfig_local = Path.home() / ".gitconfig_local"
    return _record(
        f"{tilde(gitconfig)} includes {tilde(gitconfig_local)}",
        f"{tilde(gitconfig)} does not [include] {tilde(gitconfig_local)}",
        passed=gitconfig_includes(gitconfig, gitconfig_local),
    )


def _prepush_hook_record(dotfiles: Path) -> Record:
    """OK unless something other than prek occupies the repo's pre-push hook slot.

    Hooks are opt-in here (phase 10 only notifies on clone, never force-installs), so a
    genuinely MISSING pre-push hook is fine. Anything else occupying the slot and not
    prek's — a foreign hook, an empty/unreadable file, a dangling symlink — means another
    tool (typically ``git lfs install``, if it ran first) silently claimed it, so prek's
    checks — including the VM-smoke pre-push gate — never run on push. See issue #124.
    """
    hook = prepush_hook_path(dotfiles)
    if hook is None or not (hook.is_symlink() or hook.exists()):
        return ("OK", "no pre-push hook installed (opt-in; nothing else owns it)")
    contents = commands.read_text_or_empty(hook)
    return _record(
        "pre-push hook is prek-generated",
        f"{tilde(hook)} exists but isn't prek-generated — another tool (e.g. git-lfs) likely "
        "silently took over the slot, so prek's pre-push checks never run. Re-run "
        "`prek install` (its migration mode chains any existing hook to `.legacy`).",
        passed=PREK_SHIM_MARKER in contents,
    )
