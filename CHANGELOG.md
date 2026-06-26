<!--
SPDX-FileCopyrightText: © 2026 Tyler Nivin
SPDX-License-Identifier: MIT
-->

## v1.9.1 (2026-06-26)

### 🐛🚑️ Fixes

- **fish**: Bound launch-docs browser-open probe with an nc poll

## v1.9.0 (2026-06-18)

### ✨ Features

- **install**: Warm sudo through the bundle and add a verification summary

### ♻️ Refactorings

- **brew**: Move The Unarchiver out of the baseline into the personal bundle

### 💚👷 CI & Build

- **playwright**: Install only the Chromium headless shell, not the full browser
- **playwright**: Key the browser cache on the Playwright version, not uv.lock

## v1.8.0 (2026-06-18)

### ✨ Features

- **git**: Adopt an existing ~/.gitconfig instead of stomping it on install

## v1.7.0 (2026-06-18)

### ✨ Features

- **fish**: Add tab-completion for install.sh and shell functions
- **claude**: Overlay machine-local Claude Code settings

### 🐛🚑️ Fixes

- **claude**: Harden settings generation against non-object and empty input

## v1.6.3 (2026-06-18)

### 🐛🚑️ Fixes

- **hooks**: Scope lint-on-save to files inside the project

## v1.6.2 (2026-06-18)

### 🐛🚑️ Fixes

- **install**: Make installer failures loud and non-destructive

## v1.6.1 (2026-06-18)

### 🐛🚑️ Fixes

- **install**: Pre-select saved bundles on the fzf load event

## v1.6.0 (2026-06-18)

### ✨ Features

- **install**: Add --keep-bundles flag and rebuild the Dock unconditionally

### 📝💡 Documentation

- **install**: Decouple Dock-section comment from dock.sh's app list
- **casts**: Re-sync install cast with the unconditional Dock rebuild

## v1.5.0 (2026-06-18)

### ✨ Features

- **install**: Add bundle-selection flags and --help; re-prompt with current pick

### ♻️ Refactorings

- **install**: Address review — precedence comment, dedup flags, pre-seed tests

## v1.4.1 (2026-06-18)

### 🐛🚑️ Fixes

- **install**: Verify firewall state instead of trusting socketfilterfw exit code
- **fish**: Surface silent failures, fix launch-docs portability, drop dead code

### ✅🤡🧪 Tests

- Per-function coverage inventory, hook-wiring check, and real-delete tests

### 📝💡 Documentation

- **brewfile**: Fix stale atuin conf.d cross-reference

## v1.4.0 (2026-06-18)

### ✨ Features

- **claude**: Add project hooks, reviewer agent, check skill, and MCP servers

### 🐛🚑️ Fixes

- **claude**: Harden lint and typecheck hooks against missing tools and git failures

### 💚👷 CI & Build

- Put the project venv on PATH so the hook bats tests find ruff

### 📝💡 Documentation

- Add project CLAUDE.md

### 🧹 chore

- **claude**: Enable installed plugins in global settings

## v1.3.0 (2026-06-17)

### ✨ Features

- **docs**: use a real install.sh asciinema cast as the homepage hero

### 🐛🚑️ Fixes

- migrate stale prek hook shims off the git template on install

## v1.2.0 (2026-06-17)

### ✨ Features

- make 1Password optional and add machine-local overlays

## v1.1.0 (2026-06-17)

### ✨ Features

- **fish**: infer pubkey's SSH key from the agent

## v1.0.4 (2026-06-17)

### 🐛🚑️ Fixes

- **claude**: match nested .env paths in the Read deny rule
- **fish**: validate fkill signals case-insensitively against kill -l

### ♻️ Refactorings

- **install**: factor bundle selection into a tested lib

### ✅🤡🧪 Tests

- **typos**: assert the two typos configs keep shared rules in sync

### 📝💡 Documentation

- slim software_list.md to human-only steps

## v1.0.3 (2026-06-17)

### 🐛🚑️ Fixes

- **macos**: slow key repeat to stop double-paste

## v1.0.2 (2026-06-17)

### 🐛🚑️ Fixes

- **ci**: serialize release runs and stamp the live main tip

## v1.0.1 (2026-06-17)

### 🐛🚑️ Fixes

- **docs**: unnest anchors in the Quality card so it renders intact

### ⚡️ Performance

- **ci**: run hawkeye from its release binary, not the Docker action

### 💚👷 CI & Build

- run hawkeye+taplo in CI, fix release scratch-file leak, header changelog

### 📝💡 Documentation

- redesign README as an inviting front door
- remove dependency-free claim from site footer

## v1.0.0 (2026-06-17)

### ✨ Features

- adopt .brewfile bundle convention and polish install.sh
- add machine-local overlays and pre-public review hardening

### 🐛🚑️ Fixes

- **docs,gitignore**: animate cast typing, restore tmux ignore, enable castify
- **gitignore**: slim global ignore to universals, kill footgun globs
- address Copilot review feedback
- **fish**: harden destructive and edge-case paths in shell functions
- **ssh**: catch proxy/forward/Match directives and IPv6 in the host guard

### ♻️ Refactorings

- **install**: make clone-hook auto-install opt-in; guard macOS; confirm Dock

### ✅🤡🧪 Tests

- **git**: make git_prune_local origin setup hermetic

### 💚👷 CI & Build

- add manual release trigger and modernize action versions
- split into PR + main pipelines with a commitizen release stage
- install ripgrep for the fsearch behavior test
- skip no-commit-to-branch hook in CI

### 📝💡 Documentation

- reframe site as showcase + adoption, add Commands page with casts
- align docs with opt-in hooks and config-as-code convergence
- document overlays, opt-in bundles, and the new installer UX
- **readme**: link the documentation site near the top

### 🧹 chore

- collapse history into a single public-ready baseline
