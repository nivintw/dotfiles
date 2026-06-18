# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Inventory coverage — the dotfiles analogue of "line coverage".

`coverage.py` is the wrong tool here: it only instruments these Python helpers,
which are thin glue, and says nothing about the fish/bash/config that *is* the
repo. The metric that maps to real breakage is **inventory coverage**: every
shippable artifact either has a behavior test or sits on an explicit, documented
allowlist. That turns "I added a function and forgot to test it" into a red
build, and forces every "not tested" into a conscious, reviewed decision.

This complements, not replaces, the other layers: `fish -n` (a pre-commit hook)
parses every function, `shellcheck` lints every script, and the data-file tests
parse every config. This test answers the orthogonal question — does each thing
that can break have *something* watching it?
"""

import re

from conftest import tracked

# Functions deliberately without a behavior test, each with the reason. An entry
# here is a reviewed decision; a function that is neither tested nor listed fails
# the suite. Keep this list honest — it is the repo's "known gaps" ledger.
UNTESTED_FUNCTIONS = {
    "__open_at_line": "internal helper exercised via fif/fsearch; opens $EDITOR, no guard",
    "dnsflush": "two privileged side-effects (sudo dscacheutil/killall), no testable logic",
    "fif": "interactive fzf+rg picker; its only non-interactive branch is the rg-missing dep guard",
    "gp-all": "thin wrapper that delegates to the tested forrepos",
    "gs-all": "thin wrapper that delegates to the tested forrepos",
    "_pubkey_emit": "internal helper of pubkey; its empty-key guard is exercised by"
    " pubkey's bats tests",
}

# Shell scripts without a behavior test. These mutate the host (stow, chsh, brew,
# macOS defaults, the Dock), so the realistic safety net is shellcheck + the
# consistency tests + a manual run on a throwaway VM, not a headless harness.
UNTESTED_SCRIPTS = {
    "install.sh": "orchestrates host-mutating steps (stow/chsh/brew/firewall/defaults). The"
    " bundle round-trip and fzf pre-seed logic is factored into scripts/bundle_select.sh and"
    " tested there; the CLI arg parsing (--help/--bundle/--no-bundles) and the interactive"
    " SELECTION wiring around it (legacy migration, discovery, non-interactive fallback) are"
    " not yet extracted and ride on shellcheck + manual VM runs; the rest is host-mutating"
    " glue guarded by shellcheck + the consistency tests",
    "macos.sh": "writes macOS defaults; covered by shellcheck + manual VM runs",
    "dock.sh": "rebuilds the Dock via dockutil; covered by shellcheck + manual VM runs",
}


def _fish_function_names() -> set[str]:
    """Every function DEFINED across the autoload files, not just one per file.

    Inventory by `function <name>` declaration rather than file stem, so a second
    helper added to an existing file (e.g. `_pubkey_emit` in pubkey.fish) can't slip
    past the coverage gate invisibly.
    """
    names: set[str] = set()
    for p in tracked("home/.config/fish/functions/*.fish"):
        names |= set(re.findall(r"^function\s+(\S+)", p.read_text(), re.MULTILINE))
    return names


def _bats_text() -> str:
    return "\n".join(p.read_text() for p in tracked("tests/*.bats"))


def _referenced(name: str, haystack: str) -> bool:
    """True if `name` appears as a whole token in the bats sources."""
    return re.search(rf"(?<!\w){re.escape(name)}(?!\w)", haystack) is not None


def test_every_fish_function_is_tested_or_allowlisted() -> None:
    """Each fish function is named in a bats test or sits on the documented allowlist."""
    functions = _fish_function_names()
    assert functions, "found no fish functions to check"

    bats = _bats_text()
    untested = {f for f in functions if not _referenced(f, bats)}
    gaps = untested - set(UNTESTED_FUNCTIONS)
    assert not gaps, (
        f"fish functions with no test and no allowlist entry: {sorted(gaps)}. "
        "Add a bats test, or add it to UNTESTED_FUNCTIONS with a reason."
    )


def test_every_shell_script_is_tested_or_allowlisted() -> None:
    """Each shell script is named in a bats test or sits on the documented allowlist."""
    scripts = {p.name for p in tracked("*.sh", "scripts/*.sh")}
    assert scripts, "found no shell scripts to check"

    bats = _bats_text()
    untested = {s for s in scripts if not _referenced(s, bats)}
    gaps = untested - set(UNTESTED_SCRIPTS)
    assert not gaps, (
        f"shell scripts with no test and no allowlist entry: {sorted(gaps)}. "
        "Add a bats test, or add it to UNTESTED_SCRIPTS with a reason."
    )


def test_allowlists_have_no_stale_entries() -> None:
    """Every allowlisted name must still exist — no rot when files are renamed."""
    functions = _fish_function_names()
    scripts = {p.name for p in tracked("*.sh", "scripts/*.sh")}

    stale_funcs = set(UNTESTED_FUNCTIONS) - functions
    stale_scripts = set(UNTESTED_SCRIPTS) - scripts
    assert not stale_funcs, f"UNTESTED_FUNCTIONS names a missing function: {sorted(stale_funcs)}"
    assert not stale_scripts, f"UNTESTED_SCRIPTS names a missing script: {sorted(stale_scripts)}"


def test_allowlisted_items_are_not_also_tested() -> None:
    """If an allowlisted item gains a real test, remove it from the allowlist."""
    bats = _bats_text()
    redundant_funcs = {f for f in UNTESTED_FUNCTIONS if _referenced(f, bats)}
    redundant_scripts = {s for s in UNTESTED_SCRIPTS if _referenced(s, bats)}
    assert not redundant_funcs, (
        f"now tested — drop from UNTESTED_FUNCTIONS: {sorted(redundant_funcs)}"
    )
    assert not redundant_scripts, (
        f"now tested — drop from UNTESTED_SCRIPTS: {sorted(redundant_scripts)}"
    )
