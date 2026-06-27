# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

"""Python port of the dotfiles installer's pure-logic helpers.

This package holds the testable, side-effect-light logic the bash installer
currently sources from ``scripts/*.sh`` (bundle selection, the Claude settings
merge, the gitconfig migration, and the verify-install predicates). It is the
foundation the privileged orchestrator port consumes later; until then the bash
helpers remain in place and drive ``install.sh``.

The package is intentionally not installed (``[tool.uv] package = false``); tests
import it via ``pythonpath = ["src"]``.
"""
