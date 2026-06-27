# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Behavior tests for the opt-in Brewfile bundle-selection helpers.

Ported from ``tests/bundle_select.bats``. The invariant: ``write_bundles`` and
``parse_bundles`` are inverses — the parser reads back exactly the names the writer
wrote, ignoring the self-documenting comment header — and ``fzf_preselect_bind``
maps chosen names to 1-based menu positions in chosen order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dotfiles_install.bundle_select import (
    fzf_preselect_bind,
    parse_bundles,
    write_bundles,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_write_then_parse_roundtrips_chosen_names(tmp_path: Path) -> None:
    """The names written are the names read back, in order."""
    sel = tmp_path / "bundles"
    write_bundles(sel, ["personal", "homelab", "work"], ["personal", "work"])
    assert parse_bundles(sel) == ["personal", "work"]


def test_empty_selection_parses_to_nothing(tmp_path: Path) -> None:
    """A baseline-only selection (no chosen names) parses to an empty list."""
    sel = tmp_path / "bundles"
    write_bundles(sel, ["personal", "homelab"], [])
    assert parse_bundles(sel) == []


def test_parse_missing_file_yields_empty_without_error(tmp_path: Path) -> None:
    """Parsing an absent selection file reads as 'baseline only', not an error."""
    assert parse_bundles(tmp_path / "does-not-exist") == []


def test_written_file_documents_available_as_comments(tmp_path: Path) -> None:
    """Every available bundle is a ``#   <name>`` hint; bare lines are the chosen."""
    sel = tmp_path / "bundles"
    write_bundles(sel, ["personal", "homelab"], ["personal"])
    lines = sel.read_text().splitlines()
    assert "#   personal" in lines
    assert "#   homelab" in lines
    bare = [ln for ln in lines if ln and not ln.startswith("#")]
    assert bare == ["personal"]


def test_parse_ignores_comments_and_blank_lines(tmp_path: Path) -> None:
    """A hand-edited file's comments and blank lines are skipped."""
    sel = tmp_path / "bundles"
    sel.write_text("# a comment\n#   personal\n\nhomelab\n")
    assert parse_bundles(sel) == ["homelab"]


def test_bundle_name_with_space_survives_roundtrip(tmp_path: Path) -> None:
    """Bundle names containing spaces round-trip intact."""
    sel = tmp_path / "bundles"
    write_bundles(sel, ["my bundle", "other"], ["my bundle"])
    assert parse_bundles(sel) == ["my bundle"]


def test_fzf_preselect_maps_chosen_to_1based_positions() -> None:
    """Chosen names map to 1-based menu positions."""
    assert (
        fzf_preselect_bind(["personal", "homelab", "work"], ["personal", "work"])
        == "load:pos(1)+select+pos(3)+select"
    )


def test_fzf_preselect_emits_nothing_when_nothing_chosen() -> None:
    """Nothing chosen yields an empty bind string."""
    assert fzf_preselect_bind(["personal", "homelab"], []) == ""


def test_fzf_preselect_skips_names_absent_from_menu() -> None:
    """A chosen name not in the menu is skipped."""
    assert (
        fzf_preselect_bind(["personal", "homelab"], ["ghost", "personal"]) == "load:pos(1)+select"
    )


def test_fzf_preselect_emits_in_chosen_order_not_menu_order() -> None:
    """Positions follow the chosen order, which need not match the menu order."""
    assert (
        fzf_preselect_bind(["personal", "homelab", "work"], ["work", "personal"])
        == "load:pos(3)+select+pos(1)+select"
    )


def test_fzf_preselect_indexes_past_name_with_space() -> None:
    """A later entry's position is unaffected by an earlier name containing a space."""
    assert (
        fzf_preselect_bind(["alpha", "my bundle", "charlie"], ["charlie"]) == "load:pos(3)+select"
    )
