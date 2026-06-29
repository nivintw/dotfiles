# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Verify-install predicates.

The unit-testable checks the post-install summary is built from: resolving a symlink target
into the repo, rejecting non-object JSON, matching an ``[include]`` path through ``~`` expansion,
abbreviating ``$HOME`` to ``~`` for display, and counting enrolled Touch ID templates. Two of
these shell out to fixed commands (``git config`` for includes, ``bioutil`` for the Touch ID
count) but stay deterministically testable. The full summary *emitter* — which aggregates the
heavier live-state probes (``brew bundle check``, the firewall, the login shell) into OK/BAD
records — is orchestration and lands with the orchestrator port.

Ported from ``scripts/verify_install.sh`` (predicates pinned by ``tests/verify_install.bats``).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

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
