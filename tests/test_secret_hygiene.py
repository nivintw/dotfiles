# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""claude_mcp.json must never carry a resolved secret.

The design is that secrets are 1Password references (op://...) resolved only at
install time. gitleaks catches generic secret shapes, but it does NOT know this
repo's specific invariant: the GitHub MCP auth header must stay a reference, not
a baked-in token. If someone pastes a working token to "just make it work", this
fails the build.
"""

import json
import re
from typing import TYPE_CHECKING

from conftest import REPO

if TYPE_CHECKING:
    from collections.abc import Iterator

# Literal credential shapes that must never appear as a value. The Bearer pattern
# deliberately requires the secret char-class right after "Bearer " — so the
# real "Bearer {{ op://... }}" reference (next char is "{") does not match.
LITERAL_SECRET = re.compile(
    r"ghp_[A-Za-z0-9]{20,}"
    r"|gho_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|Bearer\s+[A-Za-z0-9._-]{20,}",
)


def _strings(obj: object) -> Iterator[str]:
    """Yield every string value in a nested JSON structure."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def test_detector_matches_synthetic_secret_shapes() -> None:
    """The detector must actually fire on credential shapes.

    Without this, the absence-based checks below are green-by-default: if the
    regex ever rotted (e.g. to an empty pattern), nothing would notice. The
    samples are assembled at runtime so no real-looking token literal lives in
    this source file (which would itself trip gitleaks).
    """
    samples = [
        "ghp_" + "A" * 30,
        "gho_" + "B" * 30,
        "github_pat_" + "C" * 30,
        "Bearer " + "d" * 25,
    ]
    for s in samples:
        assert LITERAL_SECRET.search(s), f"detector failed to match a secret shape: {s!r}"


def test_detector_ignores_1password_reference() -> None:
    """The op:// reference form must never be mistaken for a literal secret."""
    assert not LITERAL_SECRET.search("Bearer {{ op://MCP/github-claude-pat/credential }}")


def test_no_literal_secret_in_mcp_config() -> None:
    """No value in claude_mcp.json matches a literal credential shape."""
    data = json.loads((REPO / "claude_mcp.json").read_text())
    offenders = [s for s in _strings(data) if LITERAL_SECRET.search(s)]
    assert not offenders, f"literal credential(s) found in claude_mcp.json: {offenders}"


def test_github_mcp_auth_uses_1password_reference() -> None:
    """The GitHub MCP auth header stays an op:// reference, never a baked-in token."""
    data = json.loads((REPO / "claude_mcp.json").read_text())
    auth = data["github"]["headers"]["Authorization"]
    # Require the full {{ op://... }} reference template, not just the substring
    # "op://" (which would also pass for "Bearer op://x ghp_realtoken"), and
    # assert no literal credential shape co-occurs in the header.
    assert re.search(r"\{\{\s*op://\S+\s*\}\}", auth), (
        f"GitHub MCP auth must be a 1Password reference, got: {auth!r}"
    )
    assert not LITERAL_SECRET.search(auth), (
        f"GitHub MCP auth carries a literal credential: {auth!r}"
    )
