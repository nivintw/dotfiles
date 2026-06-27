# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Opt-in end-to-end VM smoke test.

Boots a clean Tart VM and runs ``install.sh`` inside it via ``scripts/vm-smoke.sh``. Skipped
by default — it is heavy (a multi-GB base-image pull plus a full from-scratch install) — and
runs only when ``DOTFILES_VM_SMOKE=1`` and ``tart`` is installed. Marked ``integration`` so it
can also be selected explicitly with ``-m integration``.
"""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest
from conftest import REPO

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.environ.get("DOTFILES_VM_SMOKE") != "1",
    reason="opt-in: set DOTFILES_VM_SMOKE=1 to run the VM smoke test",
)
def test_install_runs_clean_in_a_fresh_vm() -> None:
    """install.sh runs end-to-end in a clean VM and verify_install reports healthy."""
    if shutil.which("tart") is None:
        pytest.skip("tart is not installed (brew bundle from the Brewfile installs it)")
    script = REPO / "scripts" / "vm-smoke.sh"
    result = subprocess.run([str(script)], check=False)
    assert result.returncode == 0
