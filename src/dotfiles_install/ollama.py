# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Phase 14: pull the local Ollama models for offline AI.

Two consumers, two models, both read from the shared ``scripts/ollama_models.sh`` fragment
(the single source of truth that also drives ``uninstall.sh``, so the ids can never drift):

* ``OLLAMA_MODEL`` — baseline (~4.7GB), backs GitLens commit-message generation and is the
  non-MLX fallback; pulled on every capable machine.
* ``OLLAMA_MLX_MODEL`` — gated MLX reasoning model (~21GB) for Claude bulk-offload; only pulled
  on Apple Silicon with more than 32 GiB of unified memory and macOS 13+ (the MLX engine's
  requirements). Other machines keep just the baseline.

The phase first makes sure the Ollama API is listening: it probes the daemon, launches the
menu-bar app (which also registers the login item), retries the probe, and only then falls back
to a detached headless ``ollama serve``. Every step is non-fatal — a missing ``ollama`` binary,
an unreachable server, or a failed pull degrades to a warning and the install continues.

Ported from ``install.sh`` phase 14.
"""

from __future__ import annotations

import platform
import re
import subprocess
from typing import TYPE_CHECKING

from dotfiles_install import commands
from dotfiles_install.layout import DOTFILES
from dotfiles_install.os_detect import OS, current_os

if TYPE_CHECKING:
    from dotfiles_install.context import InstallContext

# MLX-engine gate: 32 GiB in bytes (require strictly more, so exactly-32GB machines fall back to
# the baseline) and the minimum supported macOS major version.
_MEM_32_GIB_BYTES = 34359738368
_MIN_MACOS_MAJOR = 13

# The Ollama daemon's REST endpoint; a 200 here means the server is listening.
_API_URL = "http://localhost:11434/api/tags"

# Model ids live in the shared fragment as `NAME="value"`; anchor each at line start so the
# `OLLAMA_MODEL` pattern can't also match the `OLLAMA_MLX_MODEL` line.
_MODEL_PATTERN = re.compile(r'^OLLAMA_MODEL="([^"]+)"', re.MULTILINE)
_MLX_MODEL_PATTERN = re.compile(r'^OLLAMA_MLX_MODEL="([^"]+)"', re.MULTILINE)


def install_ollama_models(ctx: InstallContext) -> None:
    """Phase 14: ensure the Ollama server is up, then pull the baseline (and gated MLX) models."""
    if commands.which("ollama") is None:
        ctx.ui.warn("skipping Ollama setup (ollama not installed; see Brewfile 'ollama-app')")
        return

    # A malformed scripts/ollama_models.sh is a broken-repo invariant, but it must not abort the
    # whole install — this phase is non-fatal (like the bash original), so degrade to a warning and
    # let phases 15-17 (macOS defaults, Dock, verify) still run.
    try:
        model, mlx_model = _read_model_ids()
    except RuntimeError as exc:
        ctx.ui.warn(f"skipping Ollama setup ({exc})")
        return
    _ensure_server_up(ctx)

    # Capture the model inventory once and reuse it for both pull checks; a failed `ollama list`
    # degrades to an empty inventory (each model is then treated as absent → pulled).
    installed = _list_installed_models()

    _pull_model(ctx, model, "~4.7GB", installed)
    if _mlx_supported():
        _pull_model(ctx, mlx_model, "~21GB", installed)
    else:
        ctx.ui.detail(
            f"skipping MLX model {mlx_model} (needs Apple Silicon + >32GB RAM + macOS 13+)",
        )


def _read_model_ids() -> tuple[str, str]:
    """Parse ``(OLLAMA_MODEL, OLLAMA_MLX_MODEL)`` from the shared ``ollama_models.sh`` fragment."""
    content = commands.read_text_or_empty(DOTFILES / "scripts" / "ollama_models.sh")
    model = _MODEL_PATTERN.search(content)
    mlx_model = _MLX_MODEL_PATTERN.search(content)
    if model is None or mlx_model is None:
        msg = "could not parse model ids from scripts/ollama_models.sh"
        raise RuntimeError(msg)
    return model.group(1), mlx_model.group(1)


def _ensure_server_up(ctx: InstallContext) -> None:
    """Make the Ollama API reachable: probe, launch the app, retry, then a detached ``serve``."""
    if _server_responding():
        return

    ctx.ui.active("starting Ollama (server + login auto-start)")
    # Prefer the GUI app (it also registers the login item). `open -a` returns once the launch is
    # accepted, not when the server is listening — so key the fallback on actual API readiness.
    commands.run(["open", "-a", "Ollama"], capture=True)  # launch is best-effort
    if _server_responding_with_retry():
        return

    # Still down: start a headless server, detached so it outlives this process, then probe once
    # more. Popen (not the `commands` seam) because this one call must background, not block.
    subprocess.Popen(
        ["ollama", "serve"],  # noqa: S607  # `ollama` is resolved on PATH (guarded by which())
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    if not _server_responding_with_retry():
        ctx.ui.warn("Ollama server didn't come up; start it and re-run to pull the model.")


def _server_responding() -> bool:
    """Quick single probe of the Ollama API (matches the bash ``curl -fsS -m 2``)."""
    return commands.run_ok(["curl", "-fsS", "-m", "2", _API_URL], capture=True)


def _server_responding_with_retry() -> bool:
    """Probe the API, waiting for it to come up (``--retry-connrefused`` avoids a foreground sleep).

    Mirrors the bash ``curl -fsS --retry 20 --retry-delay 1 --retry-connrefused -m 30``.
    """
    return commands.run_ok(
        [
            "curl",
            "-fsS",
            "--retry",
            "20",
            "--retry-delay",
            "1",
            "--retry-connrefused",
            "-m",
            "30",
            _API_URL,
        ],
        capture=True,
    )


def _list_installed_models() -> list[str]:
    """Return the model names from ``ollama list`` (column 1, header dropped); [] on failure."""
    result = commands.run(["ollama", "list"], capture=True)
    if result.returncode != 0:
        return []
    lines = (result.stdout or "").splitlines()
    # Drop the header row, then take the first whitespace-delimited column of each non-blank line.
    return [tokens[0] for line in lines[1:] if (tokens := line.split())]


def _pull_model(ctx: InstallContext, model: str, size: str, installed: list[str]) -> None:
    """Pull ``model`` unless it is already in ``installed``; a failed pull warns (non-fatal)."""
    if model in installed:
        ctx.ui.ok(f"Ollama model {model} already present")
        return
    ctx.ui.active(f"pulling Ollama model {model} ({size}, one-time)")
    if commands.run_ok(["ollama", "pull", model]):
        ctx.ui.ok(f"Ollama model {model} pulled")
    else:
        ctx.ui.warn(f"Ollama pull failed for {model} (network?); re-run install.sh to retry.")


def _mlx_supported() -> bool:
    """Whether this machine meets the MLX gate: Apple Silicon + >32 GiB RAM + macOS 13+.

    MLX is Apple-only, so any non-macOS host fails the gate up front — before the ``sysctl`` /
    ``sw_vers`` probes, which don't exist on Linux and would only produce stderr noise on their
    way to the same closed-gate answer.
    """
    if current_os() != OS.MACOS:
        return False
    if platform.machine() != "arm64":
        return False
    if _mem_bytes() <= _MEM_32_GIB_BYTES:
        return False
    return _macos_major() >= _MIN_MACOS_MAJOR


def _mem_bytes() -> int:
    """Total physical memory in bytes from ``sysctl -n hw.memsize``; 0 if it can't be read."""
    result = commands.run(["sysctl", "-n", "hw.memsize"], capture=True)
    if result.returncode != 0:
        return 0
    try:
        return int((result.stdout or "").strip())
    except ValueError:
        return 0


def _macos_major() -> int:
    """The macOS major version from ``sw_vers -productVersion`` (first dotted part); 0 if unknown.

    Bash uses ``${os_major:-0}``, defaulting an empty or unreadable value to 0 (gate fails closed).
    """
    result = commands.run(["sw_vers", "-productVersion"], capture=True)
    if result.returncode != 0:
        return 0
    first = (result.stdout or "").strip().split(".")[0]
    try:
        return int(first)
    except ValueError:
        return 0
