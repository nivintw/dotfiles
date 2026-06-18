<!--
SPDX-FileCopyrightText: © 2026 Tyler Nivin
SPDX-License-Identifier: MIT
-->

# dotfiles

Tyler's macOS dotfiles: GNU stow for symlinking, a prek hook gate, a pytest + bats
test suite, and a signed-commit release pipeline. The global `~/.claude/CLAUDE.md`
rules apply everywhere — this file is **project specifics only**.

## Local checks (run before declaring work done)

```bash
prek run --all-files   # every lint/format/security/license/commit hook
uv run pytest          # config validity & consistency (Python is tests-only)
bats tests/            # fish/shell behavior (needs bats-core + fish, both in the Brewfile)
```

## Layout

- `home/` — stowed into `$HOME` (e.g. `home/.claude/` → `~/.claude/`). Editing a
  stowed file edits the live target.
- `install.sh` — orchestrates the whole setup (Brewfile → stow → macOS defaults);
  idempotent, safe to re-run.
- `Brewfile` / `Brewfile.d/` — package manifests; `macos.sh` — system defaults.
- `docs/` — static docs site with asciinema casts; `tests/test_docs_site.py` drives
  it via pytest-playwright.
- `scripts/` — repo helper scripts. `tests/` — pytest (`test_*.py`, config validity)
  and bats (`*.bats`, fish behavior).

## Gotchas

- **`~/.claude/settings.json` is generated, not stowed.** `install.sh` deep-merges
  the tracked `claude_settings.json` baseline with the untracked
  `~/.config/dotfiles/claude_settings.local.json` overlay (arrays like
  `permissions.allow` union; the overlay wins per scalar) and writes a real file.
  `/config`, `/plugin`, and plugin installs write through that real file; the next
  `install.sh` run folds whatever they changed into this machine's overlay — not the
  repo. Change shared defaults by editing `claude_settings.json` and re-running
  install. Merge logic + caveats live in `scripts/claude_settings_merge.sh`.
- **Python is not a package** (`[tool.uv] package = false`). pyproject.toml exists
  only to give the test suite a managed env. Manage deps with `uv`.
- **SPDX headers are required** — reuse/hawkeye enforce them; new files need a
  license header (the hooks add/format them).

## Git & releases

- **`main` is protected** (prek `no-commit-to-branch`). Make changes on a branch in
  a git worktree, then open a PR. Live-test stow-symlinked dotfiles in the main
  checkout first, then move the change into a worktree for the PR.
- **Commits:** write a plain Conventional Commit (`type(scope): Description`); the
  `conventional-gitmoji` hook prepends the emoji — don't add it yourself.
- **Releases:** commitizen (`cz_gitmoji`) drives versioning and `CHANGELOG.md`; CI's
  release stage creates the signed bump commit via the GitHub App +
  `createCommitOnBranch`. The changelog and version are tool-generated — don't
  hand-edit. Don't merge a second PR while a release run from the first is still in
  flight.
