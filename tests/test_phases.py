# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for the phase registry: ordering, gating, and port completeness."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dotfiles_install import phases as phases_mod
from dotfiles_install.os_detect import OS
from dotfiles_install.phases import REGISTRY, phases_for

if TYPE_CHECKING:
    import pytest

EXPECTED_PHASE_COUNT = 18  # install.sh phases 0-17 inclusive

# Phases whose bodies carry no OS-specific assumption (phases.py's ``_ALL``): they run on macOS,
# Linux, and WSL2. The complement is macOS-gated until its Linux port lands (#112 packages, #113
# privileged/verify). These two sets must partition the registry — asserted below.
_OS_AGNOSTIC_PHASES = frozenset({3, 4, 5, 6, 7, 9, 10, 11, 12, 13})
_MACOS_ONLY_PHASES = frozenset({0, 1, 2, 8, 14, 15, 16, 17})


def test_registry_mirrors_install_sh_phase_count() -> None:
    """The registry has one entry per install.sh phase (0-17)."""
    assert len(REGISTRY) == EXPECTED_PHASE_COUNT


def test_phase_numbers_are_contiguous_and_ordered() -> None:
    """Phases are numbered 0..17 in registry order."""
    assert [phase.number for phase in REGISTRY] == list(range(EXPECTED_PHASE_COUNT))


def test_phase_names_are_unique() -> None:
    """No two phases share a display name."""
    names = [phase.name for phase in REGISTRY]
    assert len(set(names)) == len(names)


def test_only_the_privileged_block_needs_root() -> None:
    """Exactly phase 2 (the sudo/firewall/PAM block) is marked privileged."""
    privileged = [phase.number for phase in REGISTRY if phase.privileged]
    assert privileged == [2]


def test_every_phase_is_ported() -> None:
    """The port is complete: every phase 0-17 carries a ``run`` callable (no stubs left)."""
    for phase in REGISTRY:
        assert phase.run is not None, f"phase {phase.number} should be ported"


def test_applies_gates_on_os() -> None:
    """A macOS-only phase (phase 0, the Homebrew bootstrap) applies to macOS and not to Linux."""
    phase = REGISTRY[0]
    assert phase.applies(OS.MACOS) is True
    assert phase.applies(OS.LINUX) is False


def test_phases_for_macos_returns_everything() -> None:
    """On macOS — the fully-supported platform — the run sees the whole registry."""
    assert phases_for(OS.MACOS) == list(REGISTRY)


def test_phases_for_linux_runs_only_the_os_agnostic_phases() -> None:
    """Linux selects exactly the OS-agnostic phases — no Homebrew, privileged, or macOS tweaks."""
    assert [phase.number for phase in phases_for(OS.LINUX)] == sorted(_OS_AGNOSTIC_PHASES)


def test_phases_for_wsl_matches_linux() -> None:
    """WSL2 runs the same phase set as plain Linux (this slice doesn't split them yet)."""
    assert phases_for(OS.WSL) == phases_for(OS.LINUX)


def test_os_agnostic_phases_apply_on_every_os() -> None:
    """Each OS-agnostic phase applies to macOS, Linux, and WSL alike."""
    for phase in REGISTRY:
        if phase.number in _OS_AGNOSTIC_PHASES:
            assert phase.applies(OS.MACOS)
            assert phase.applies(OS.LINUX)
            assert phase.applies(OS.WSL)


def test_macos_only_phases_are_skipped_off_macos() -> None:
    """Each macOS-only phase applies to macOS but neither Linux nor WSL."""
    for phase in REGISTRY:
        if phase.number in _MACOS_ONLY_PHASES:
            assert phase.applies(OS.MACOS)
            assert not phase.applies(OS.LINUX)
            assert not phase.applies(OS.WSL)


def test_os_class_buckets_partition_the_registry() -> None:
    """Every phase is classified exactly once as OS-agnostic or macOS-only (no gaps, no overlap)."""
    registry_numbers = {phase.number for phase in REGISTRY}
    assert registry_numbers == _OS_AGNOSTIC_PHASES | _MACOS_ONLY_PHASES
    assert not (_OS_AGNOSTIC_PHASES & _MACOS_ONLY_PHASES)


def test_phases_for_defaults_to_current_os(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no argument, gating uses the detected current OS."""
    monkeypatch.setattr(phases_mod, "current_os", lambda: OS.MACOS)
    assert phases_for() == list(REGISTRY)
