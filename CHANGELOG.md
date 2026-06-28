<!--
SPDX-FileCopyrightText: © 2026 Tyler Nivin
SPDX-License-Identifier: MIT
-->

# Changelog

<!-- release-please prepends new releases above; entries below predate the release-please migration. -->

## [1.13.0](https://github.com/nivintw/dotfiles/compare/v1.12.1...v1.13.0) (2026-06-28)


### Features

* **install:** Port bootstrap toolchain + brew bundle to Python (phases 0-1) ([87344a7](https://github.com/nivintw/dotfiles/commit/87344a777d531fde9fb4899e6d1ddeebc6d00767)), closes [#67](https://github.com/nivintw/dotfiles/issues/67)


### Bug Fixes

* **install:** Address adversarial review of the phase 0-1 port ([ab1283b](https://github.com/nivintw/dotfiles/commit/ab1283b05ebb189fccf9bffa00f93f9bf06118d2)), closes [#67](https://github.com/nivintw/dotfiles/issues/67)
* **install:** Address code-review findings on the phase 0-1 port ([b30085b](https://github.com/nivintw/dotfiles/commit/b30085b09e1d389679c410ad2efc0a950be83966)), closes [#67](https://github.com/nivintw/dotfiles/issues/67)

## [1.12.1](https://github.com/nivintw/dotfiles/compare/v1.12.0...v1.12.1) (2026-06-28)


### Bug Fixes

* **gitconfig:** Round-trip a non-UTF-8 ~/.gitconfig byte-faithfully ([3e84f6f](https://github.com/nivintw/dotfiles/commit/3e84f6fc63dcac84f19512f20a16e1b588032d6b))
* **install:** Use rm -f when clearing managed files pre-stow ([42db894](https://github.com/nivintw/dotfiles/commit/42db894e7bd742e34e5848e04318a3f65e1a680e))

## [1.12.0](https://github.com/nivintw/dotfiles/compare/v1.11.1...v1.12.0) (2026-06-28)


### Features

* **install:** Add Python orchestrator skeleton (registry, Typer CLI, Rich UI) ([39f57be](https://github.com/nivintw/dotfiles/commit/39f57be287afca44abc96fc048e588d1bcb82ef6)), closes [#53](https://github.com/nivintw/dotfiles/issues/53)

## [1.11.1](https://github.com/nivintw/dotfiles/compare/v1.11.0...v1.11.1) (2026-06-28)


### Bug Fixes

* **install:** Authenticate sudo once, after the bundle (not across it) ([3e6954e](https://github.com/nivintw/dotfiles/commit/3e6954e1d9d452ef1c28ce28cea674ed47571e84)), closes [#62](https://github.com/nivintw/dotfiles/issues/62)

## [1.11.0](https://github.com/nivintw/dotfiles/compare/v1.10.0...v1.11.0) (2026-06-28)


### Features

* **installer:** Add --core profile and run the smoke harness on it ([cd930a8](https://github.com/nivintw/dotfiles/commit/cd930a8830e791fce00b48ecd602ef68a6c4728a))
* **test:** Add Tart VM end-to-end installer smoke harness ([23f2f61](https://github.com/nivintw/dotfiles/commit/23f2f61c7b8ada63ff71d253f91374705f7468b8))


### Bug Fixes

* Address Copilot review round 2 ([b59e758](https://github.com/nivintw/dotfiles/commit/b59e75812f3bb302b9a9d9ac212bcb900908e242)), closes [#31](https://github.com/nivintw/dotfiles/issues/31)
* Address Copilot review round 3 ([9873300](https://github.com/nivintw/dotfiles/commit/98733005931f243c7e46f6f9fa54684ea28307e2))
* **installer:** Core profile must also drop vscode/mas entries ([069f073](https://github.com/nivintw/dotfiles/commit/069f073eec4cf1df18d50c2b7ce6c00ab1c39d68))
* **installer:** Harden network-bootstrap steps against transient failure ([e5400b5](https://github.com/nivintw/dotfiles/commit/e5400b550ea7024bdc356322b14bd2725e89a6c4))
* **installer:** Re-clone TPM when the checkout is partial ([6534baf](https://github.com/nivintw/dotfiles/commit/6534bafd3feffd7125573cd770eaffdb60ef8204))
* **installer:** Trust all Brewfile taps before bundling ([560054f](https://github.com/nivintw/dotfiles/commit/560054f641ad2c2ecddda002806411d6aa96fccd))
* **installer:** Use stow --no-folding so fresh-machine symlinks are per-file ([7624c68](https://github.com/nivintw/dotfiles/commit/7624c68fe60fb887c6e988c97cf311b77aa65a63))
* **test:** Disable sudo auth in the VM so the install runs unattended ([8abca33](https://github.com/nivintw/dotfiles/commit/8abca33d41e7064811a8242596274c115cf5b2f8)), closes [#31](https://github.com/nivintw/dotfiles/issues/31)
* **test:** Gate on the non-fatal install outputs; harden harness inputs ([e558bc9](https://github.com/nivintw/dotfiles/commit/e558bc9762da5dccca5e82aadf04450f13331ddc))
* **test:** Make VM smoke cleanup trap-safe and sudo unattended ([12eb85e](https://github.com/nivintw/dotfiles/commit/12eb85e4911eff9998ec5d5bd238fbcac22f4934)), closes [#31](https://github.com/nivintw/dotfiles/issues/31)

## [1.10.0](https://github.com/nivintw/dotfiles/compare/v1.9.1...v1.10.0) (2026-06-27)


### Features

* **installer:** Port pure-logic helpers to a Python package ([429c7d2](https://github.com/nivintw/dotfiles/commit/429c7d278f9fe2f26a2f6dac91f18b8fae02a70c))


### Bug Fixes

* **installer:** Harden verify predicate and correct diff docstring ([b581999](https://github.com/nivintw/dotfiles/commit/b581999499198a529c47e5bb6979a34a5259288d))
* **installer:** Tighten symlink_into_repo to match the bash original ([f37e2a9](https://github.com/nivintw/dotfiles/commit/f37e2a929a1ff4d9279275fae8b76f9dd9d1e610))

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
