<!--
SPDX-FileCopyrightText: © 2026 Tyler Nivin
SPDX-License-Identifier: MIT
-->

# Tests

Two complementary suites, each using the right tool for its job.

| Suite | Tool | Covers |
|-------|------|--------|
| `*.bats` | bats-core | **behavior** of the fish functions |
| `test_*.py` | pytest | **validity & consistency** of the declarative config |

## Running

```bash
bats tests/          # fish behavior  (needs bats-core + fish, both in the Brewfile)
uv run pytest        # config validity (uv handles the Python env from pyproject.toml)
```

## bats — fish behavior

- **`git_prune_local.bats`** — the branch-pruning logic, the one function where a
  bug would delete unmerged work. Each test builds a throwaway repo with a local
  bare `origin` and asserts `--dry-run` decisions across the full matrix: merged +
  gone remote, multi-commit squash-merge, gone-but-unmerged (kept), merged
  local-only, unmerged local-only (kept), the current branch (never deleted), and
  a live-upstream branch (kept). Non-destructive — only `--dry-run` is exercised.
- **`fish_functions.bats`** — guard rails of the small wrapper helpers (usage
  messages, "not a git repository", missing-key handling). The interactive happy
  paths (fzf/rg/git pickers) aren't driven headless.

The bats tests shell out to fish to source and exercise the functions, so no fish
test framework is needed.

## pytest — config validity & consistency

Python is the right tool for parsing and cross-checking the repo's data files.
These catch the failure class the hooks and bats miss — a malformed TOML, a
resolved secret replacing an `op://` reference, a tool a hook needs but the
Brewfile doesn't declare.

- **`test_data_files.py`** — every `*.toml` parses (tomllib), `claude_mcp.json` is
  strict JSON, both `settings.json` parse as JSONC (json5), the iTerm plist loads
  (plistlib).
- **`test_secret_hygiene.py`** — `claude_mcp.json` carries no literal token and the
  GitHub MCP auth header stays an `op://` reference (the repo-specific invariant
  gitleaks doesn't know).
- **`test_manifests.py`** — Brewfile lines use known directives; `uv_tools.txt`
  lines are well-formed (`--with` flags paired).
- **`test_consistency.py`** — tools the scripts/hooks use are in the Brewfile,
  local hook scripts exist and are executable, and `install.sh`'s managed-files
  list matches what's actually stowed under `home/`.
