# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Cross-file consistency — the checks that catch "works on my machine".

These assert that what one file references actually exists in another: tools the
scripts/hooks invoke are declared in the Brewfile, local hook scripts exist and
are executable, and the installer's managed-files list matches what's actually stowed.
"""

import os
import re
import tomllib
from typing import TYPE_CHECKING

import json5
import pytest
import yaml
from conftest import REPO

from dotfiles_install import stow

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
    "stow": "symlinking dotfiles in the installer",
    "jq": "MCP registration in the installer",
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


# Commands that run the next token as a script through an interpreter — so that script needs
# no executable bit of its own (`python3 scripts/foo.py`), unlike one invoked directly.
_HOOK_INTERPRETERS = frozenset({"python3", "python", "bash", "sh", "uv", "uvx"})


def test_local_hook_scripts_exist_and_are_executable() -> None:
    """Local hooks that shell out to scripts/ point at real files (executable when run directly).

    A script invoked through an interpreter (``python3 scripts/foo.py``) doesn't need its own
    executable bit; one invoked directly (``exec scripts/foo.sh``) does.
    """
    cfg = yaml.safe_load((REPO / ".pre-commit-config.yaml").read_text())
    # (path, invoked_directly) per scripts/ reference. Strip shell punctuation: an entry like
    # `bash -c '... exec scripts/vm-smoke.sh; ...'` tokenizes the path as `scripts/vm-smoke.sh;`
    # — the trailing `;` isn't part of the path.
    referenced: list[tuple[str, bool]] = []
    for repo in cfg.get("repos", []):
        if repo.get("repo") != "local":
            continue
        for hook in repo.get("hooks", []):
            toks = [tok.strip("'\";") for tok in hook.get("entry", "").split()]
            for i, tok in enumerate(toks):
                if not tok.startswith("scripts/"):
                    continue
                direct = i == 0 or toks[i - 1] not in _HOOK_INTERPRETERS
                referenced.append((tok, direct))
    assert referenced, "expected at least one local hook to reference scripts/"
    for rel, direct in referenced:
        path = REPO / rel
        assert path.is_file(), f"hook references missing script: {rel}"
        if direct:
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


def _typos_shared_rules(path: pathlib.Path) -> dict[str, object]:
    """Return the shared rule surface of a typos config: ignore-regexes + word whitelist."""
    default = tomllib.loads(path.read_text()).get("default", {})
    return {
        "extend-ignore-re": default.get("extend-ignore-re", []),
        "extend-words": default.get("extend-words", {}),
    }


def test_typos_configs_keep_shared_rules_in_sync() -> None:
    """.config/typos.toml and home/.typos.toml carry an identical shared rule surface.

    Both files are hand-maintained standalone copies (not a symlink — see each
    file's header), so their ignore-regex shapes and word whitelist can silently
    drift. That would break the stated guarantee that a token flags identically
    under the repo hook / CI (.config/typos.toml) and under the personal ~/.typos.toml
    everywhere else. Only the genuinely repo-only keys are excluded from the
    comparison by construction: .config/typos.toml's [files].extend-exclude (docs/ vendored
    + cast artifacts) and home/.typos.toml's empty [default.extend-identifiers]
    placeholder, neither of which is part of the shared surface.
    """
    repo = _typos_shared_rules(REPO / ".config" / "typos.toml")
    home = _typos_shared_rules(REPO / "home" / ".typos.toml")
    assert repo == home, (
        "typos shared rules drifted between .config/typos.toml and home/.typos.toml; "
        "update both so local and CI flag identically (see each file's header)"
    )


def test_install_managed_files_are_stowed() -> None:
    """Each file the stow phase relinks must have a tracked source under home/."""
    assert stow.MANAGED_FILES, "no managed files declared in dotfiles_install.stow"
    for rel in stow.MANAGED_FILES:
        source = REPO / "home" / rel
        assert source.exists(), f"stow manages $HOME/{rel} but home/{rel} isn't tracked"


def test_tracked_gitconfig_carries_no_personal_identity() -> None:
    """The public home/.gitconfig ships no [user] identity.

    Name, email, and signing key are machine-local: they live in the untracked
    ~/.gitconfig_local overlay (Include-d last) and the installer migrates a
    pre-existing ~/.gitconfig into it. Re-introducing a [user] block here would
    impose one person's identity (and leak an email) as the public default on every
    machine that adopts these dotfiles.
    """
    text = (REPO / "home" / ".gitconfig").read_text()
    assert not re.search(r"(?m)^\s*\[user\]", text), (
        "home/.gitconfig has a [user] section; move identity to ~/.gitconfig_local"
    )
    for key in ("name", "email", "signingkey"):
        assert not re.search(rf"(?m)^\s*{key}\s*=", text), (
            f"home/.gitconfig sets user.{key}; identity belongs in ~/.gitconfig_local"
        )


def test_gitconfig_overlay_include_is_last() -> None:
    """The ~/.gitconfig_local include is the final section in home/.gitconfig.

    The overlay only wins for keys declared before any later tracked section, so the
    machine-local include must come last for it to override every baseline key.
    """
    sections = re.findall(r"(?m)^\s*\[([^\]]+)\]", (REPO / "home" / ".gitconfig").read_text())
    assert sections, "no sections found in home/.gitconfig"
    assert sections[-1].strip() == "include", (
        f"home/.gitconfig must end with the [include] of the overlay, got [{sections[-1]}]"
    )


def test_claude_settings_hooks_point_at_executable_scripts() -> None:
    """Each hook wired in the project .claude/settings.json references a real, executable script.

    The analogue of test_local_hook_scripts_exist_and_are_executable, for the Claude
    Code hooks: if a hook script is renamed or its path in settings drifts, the hook
    silently stops firing — this turns that into a red build. The hooks are project-
    scoped, so they live in the repo-root .claude/settings.json (distinct from the
    user-scope claude_settings.json baseline that the installer merges into
    ~/.claude/settings.json).
    """
    settings = json5.loads((REPO / ".claude" / "settings.json").read_text())
    commands = [
        hook["command"]
        for group in settings.get("hooks", {}).values()
        for entry in group
        for hook in entry.get("hooks", [])
        if hook.get("type") == "command"
    ]
    assert commands, "expected hook commands wired in .claude/settings.json"
    for cmd in commands:
        match = re.search(r"\.claude/hooks/[\w.+-]+\.(?:sh|py)", cmd)
        assert match, f"hook command doesn't reference a .claude/hooks script: {cmd}"
        path = REPO / match.group(0)
        assert path.is_file(), f"settings.json hook references missing script: {match.group(0)}"
        # A `.py` hook runs via `python3 <path>`, so it needn't carry the executable bit; a
        # directly-invoked `.sh` hook must.
        if match.group(0).endswith(".sh"):
            assert os.access(path, os.X_OK), f"hook script not executable: {match.group(0)}"


def test_claude_baseline_settings_hooks_point_at_executable_scripts() -> None:
    """Each hook wired in the user-scope claude_settings.json baseline references a real script.

    The analogue of test_claude_settings_hooks_point_at_executable_scripts, for the
    installer's user-scope baseline (distinct from the project-scoped .claude/settings.json
    above): the installer deep-merges this file into ~/.claude/settings.json, so its hook
    commands reference the stowed ``$HOME/...`` path rather than ``$CLAUDE_PROJECT_DIR``.
    If the target script is renamed or loses its executable bit, the SessionStart hook
    silently stops firing on the next install — this turns that into a red build.
    """
    settings = json5.loads((REPO / "claude_settings.json").read_text())
    commands = [
        hook["command"]
        for group in settings.get("hooks", {}).values()
        for entry in group
        for hook in entry.get("hooks", [])
        if hook.get("type") == "command"
    ]
    assert commands, "expected hook commands wired in claude_settings.json"
    paths: set[str] = set()
    for cmd in commands:
        # A command may be a compound like `[ ! -x "$HOME/x.sh" ] || "$HOME/x.sh"`, so extract
        # every unique $HOME/<path>.sh occurrence rather than assuming a single reference.
        matches = re.findall(r"\$HOME/([\w./-]+\.sh)", cmd)
        assert matches, f"hook command doesn't reference a $HOME/....sh script: {cmd}"
        paths.update(matches)
    for rel in paths:
        path = REPO / "home" / rel
        assert path.is_file(), f"claude_settings.json hook references missing script: home/{rel}"
        assert os.access(path, os.X_OK), f"hook script not executable: home/{rel}"
