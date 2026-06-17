# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Cross-file consistency — the checks that catch "works on my machine".

These assert that what one file references actually exists in another: tools the
scripts/hooks invoke are declared in the Brewfile, local hook scripts exist and
are executable, and install.sh's managed-files list matches what's actually stowed.
"""

import os
import re
from typing import TYPE_CHECKING

import pytest
import yaml
from conftest import REPO

if TYPE_CHECKING:
    import pathlib

# Tools that must be installed on the machine for the scripts/hooks/tests to work,
# mapped to the Brewfile package that provides them. The pre-commit hooks for
# shellcheck/typos/gitleaks deliberately self-bootstrap their own pinned envs (so
# they're reproducible in CI), so they are NOT listed here — only genuine
# system-installed dependencies are. fish is the one hook tool prek can't
# bootstrap. (shellcheck/typos-cli/gitleaks remain in the Brewfile for manual use,
# but the hooks no longer depend on them being present.)
REQUIRED_BREW_PACKAGES = {
    "fish": "default login shell + the fish pre-commit hooks",
    "stow": "symlinking dotfiles in install.sh",
    "jq": "MCP registration in install.sh",
    "dockutil": "dock.sh",
    "bats-core": "fish behavior tests (bats)",
}


def _brewfile_packages() -> set[str]:
    pkgs = set()
    for raw in (REPO / "Brewfile").read_text().splitlines():
        m = re.match(r'^(?:brew|cask)\s+"([^"]+)"', raw.strip())
        if m:
            pkgs.add(m.group(1))
    return pkgs


def test_required_tools_are_in_brewfile() -> None:
    """Every tool the scripts/hooks invoke is declared in the Brewfile."""
    pkgs = _brewfile_packages()
    missing = {p: why for p, why in REQUIRED_BREW_PACKAGES.items() if p not in pkgs}
    assert not missing, f"tools used by scripts/hooks but not in Brewfile: {missing}"


def test_local_hook_scripts_exist_and_are_executable() -> None:
    """Local hooks that shell out to scripts/ point at real, executable files."""
    cfg = yaml.safe_load((REPO / ".pre-commit-config.yaml").read_text())
    referenced = [
        tok
        for repo in cfg.get("repos", [])
        if repo.get("repo") == "local"
        for hook in repo.get("hooks", [])
        for tok in hook.get("entry", "").split()
        if tok.startswith("scripts/")
    ]
    assert referenced, "expected at least one local hook to reference scripts/"
    for rel in referenced:
        path = REPO / rel
        assert path.is_file(), f"hook references missing script: {rel}"
        assert os.access(path, os.X_OK), f"hook script not executable: {rel}"


# An <a>/<\a> open or close tag. Literal `<a` shown in prose is HTML-escaped
# (&lt;a&gt;) in these hand-written pages, so a raw match is always a real anchor.
_ANCHOR_TAG = re.compile(r"<\s*(/?)\s*a\b", re.IGNORECASE)


@pytest.mark.parametrize("html", sorted((REPO / "docs").glob("*.html")), ids=lambda p: p.name)
def test_docs_have_no_nested_anchors(html: pathlib.Path) -> None:
    """No docs page nests an <a> inside another <a>.

    Nested anchors are invalid HTML: the browser silently closes the outer <a> at
    the inner one, so a card-link whose text contains links gets torn apart — its
    trailing content spills out of the card. The rendered DOM no longer shows the
    nesting (the parser already un-nested it), so this is checked on the raw source.
    """
    depth = 0
    bad: list[int] = []
    for lineno, line in enumerate(html.read_text().splitlines(), start=1):
        for match in _ANCHOR_TAG.finditer(line):
            if match.group(1):  # closing </a>
                depth = max(0, depth - 1)
            else:  # opening <a>
                if depth:
                    bad.append(lineno)
                depth += 1
    assert not bad, f"{html.name}: nested <a> at line(s) {bad}"


def test_install_managed_files_are_stowed() -> None:
    """Each file install.sh relinks must have a tracked source under home/."""
    text = (REPO / "install.sh").read_text()
    # Scope to the managed_files=( ... ) array, then pull the home-relative paths
    # out of its "$HOME/..." entries (don't match $HOME elsewhere, e.g. PATH=).
    block = re.search(r"managed_files=\((.*?)\)", text, re.DOTALL)
    assert block, "managed_files array not found in install.sh"
    rels = re.findall(r'"\$HOME/([^"]+)"', block.group(1))
    assert rels, "no managed_files entries found in install.sh"
    for rel in rels:
        source = REPO / "home" / rel
        assert source.exists(), f"install.sh manages $HOME/{rel} but home/{rel} isn't tracked"
