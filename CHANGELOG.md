<!--
SPDX-FileCopyrightText: © 2026 Tyler Nivin
SPDX-License-Identifier: MIT
-->

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
