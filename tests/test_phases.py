# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Tests for the phase registry: ordering, gating, and stub state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dotfiles_install import phases as phases_mod
from dotfiles_install.os_detect import OS
from dotfiles_install.phases import REGISTRY, phases_for

if TYPE_CHECKING:
    import pytest

EXPECTED_PHASE_COUNT = 18  # install.sh phases 0-17 inclusive
PORTED_PHASES = {0, 1}  # bootstrap toolchain + brew bundle carry a run callable (#67)


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


def test_ported_phases_have_bodies_and_the_rest_are_stubs() -> None:
    """Phases 0-1 carry a ``run`` callable (#67); every other phase is still a ``None`` stub."""
    for phase in REGISTRY:
        if phase.number in PORTED_PHASES:
            assert phase.run is not None, f"phase {phase.number} should be ported"
        else:
            assert phase.run is None, f"phase {phase.number} should still be a stub"


def test_applies_gates_on_os() -> None:
    """A macOS-only phase applies to macOS and not to Linux."""
    phase = REGISTRY[0]
    assert phase.applies(OS.MACOS) is True
    assert phase.applies(OS.LINUX) is False


def test_phases_for_macos_returns_everything() -> None:
    """Every current phase is macOS-gated, so macOS sees the whole registry."""
    assert phases_for(OS.MACOS) == list(REGISTRY)


def test_phases_for_linux_is_empty_today() -> None:
    """No phase is Linux-gated yet, so Linux selects nothing."""
    assert phases_for(OS.LINUX) == []


def test_phases_for_defaults_to_current_os(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no argument, gating uses the detected current OS."""
    monkeypatch.setattr(phases_mod, "current_os", lambda: OS.MACOS)
    assert phases_for() == list(REGISTRY)
