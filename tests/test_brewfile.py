# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Behavior tests for the Brewfile text parsers.

Ported from ``tests/brewfile_taps.bats`` and ``tests/brewfile_core.bats``: ``brewfile_taps``
emits the first quoted argument of each ``tap`` line (ignoring URLs, comments, and other
directives), and ``brewfile_core`` drops the GUI-bound directive lines while preserving
everything else — taps, brews, and comments — verbatim.
"""

from __future__ import annotations

from dotfiles_install.brewfile import brewfile_core, brewfile_taps, brewfile_without_vscode


def test_taps_extracts_first_quoted_name() -> None:
    """Each ``tap`` line yields its name; a clone URL second argument is ignored."""
    text = 'tap "owner/one"\nbrew "git"\ntap "owner/two", "https://example/x.git"\n'
    assert brewfile_taps(text) == ["owner/one", "owner/two"]


def test_taps_ignores_trailing_comment() -> None:
    """A trailing comment after the tap name is dropped."""
    assert brewfile_taps('tap "a/b"   # a note\n') == ["a/b"]


def test_taps_skips_commented_out_lines() -> None:
    """Commented-out tap lines (the first non-space char is ``#``) are not taps."""
    assert brewfile_taps('# tap "a/b"\n  # tap "c/d"\n') == []


def test_taps_ignores_other_directives() -> None:
    """``brew`` / ``cask`` / ``untap`` lines are not taps."""
    assert brewfile_taps('brew "git"\ncask "firefox"\nuntap "z/q"\n') == []


def test_taps_empty_when_no_taps() -> None:
    """A Brewfile with no tap lines yields an empty list."""
    assert brewfile_taps('brew "git"\nbrew "jq"\n') == []


def test_core_keeps_taps_brews_and_comments_verbatim() -> None:
    """Taps, brews, and comment lines pass through unchanged."""
    text = '# header\ntap "a/b"\nbrew "git"\n'
    assert brewfile_core(text) == text


def test_core_drops_every_gui_directive() -> None:
    """``cask`` / ``vscode`` / ``mas`` / ``whalebrew`` lines are removed."""
    text = (
        'brew "git"\n'
        'cask "firefox"\n'
        'vscode "ms.python"\n'
        'mas "Xcode", id: 497799835\n'
        'whalebrew "w"\n'
    )
    assert brewfile_core(text) == 'brew "git"\n'


def test_core_drops_indented_casks() -> None:
    """An indented cask line is still a GUI directive and is dropped."""
    assert brewfile_core('brew "git"\n  cask "firefox"\n') == 'brew "git"\n'


def test_core_preserves_inline_comment_on_a_kept_line() -> None:
    """A kept line's inline comment survives intact."""
    text = 'brew "git" # version control\n'
    assert brewfile_core(text) == text


def test_core_is_a_no_op_without_gui_entries() -> None:
    """A Brewfile with only taps and brews is returned unchanged."""
    text = 'tap "a/b"\nbrew "git"\nbrew "jq"\n'
    assert brewfile_core(text) == text


def test_without_vscode_drops_only_vscode_lines() -> None:
    """``vscode`` lines are removed; brews, casks, mas, taps, and comments are kept verbatim.

    Unlike ``brewfile_core``, casks/mas/whalebrew survive — only the Settings-Sync-managed
    VS Code extensions are stripped (#158).
    """
    text = (
        "# header\n"
        'tap "a/b"\n'
        'brew "git"\n'
        'cask "firefox"\n'
        'vscode "ms.python"\n'
        'mas "Xcode", id: 497799835\n'
    )
    assert brewfile_without_vscode(text) == (
        '# header\ntap "a/b"\nbrew "git"\ncask "firefox"\nmas "Xcode", id: 497799835\n'
    )


def test_without_vscode_drops_indented_vscode() -> None:
    """An indented ``vscode`` line is still stripped."""
    assert brewfile_without_vscode('brew "git"\n  vscode "ms.python"\n') == 'brew "git"\n'


def test_without_vscode_is_a_no_op_without_vscode_entries() -> None:
    """A Brewfile with no vscode lines is returned unchanged (casks included)."""
    text = 'tap "a/b"\nbrew "git"\ncask "firefox"\n'
    assert brewfile_without_vscode(text) == text
