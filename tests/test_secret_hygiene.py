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


def test_no_literal_secret_in_mcp_config() -> None:
    """No value in claude_mcp.json matches a literal credential shape."""
    data = json.loads((REPO / "claude_mcp.json").read_text())
    offenders = [s for s in _strings(data) if LITERAL_SECRET.search(s)]
    assert not offenders, f"literal credential(s) found in claude_mcp.json: {offenders}"


def test_github_mcp_auth_uses_1password_reference() -> None:
    """The GitHub MCP auth header stays an op:// reference, never a baked-in token."""
    data = json.loads((REPO / "claude_mcp.json").read_text())
    auth = data["github"]["headers"]["Authorization"]
    assert "op://" in auth, f"GitHub MCP auth must be an op:// reference, got: {auth!r}"
