<!--
SPDX-FileCopyrightText: © 2026 Tyler Nivin
SPDX-License-Identifier: MIT
-->

# Changelog

<!-- release-please prepends new releases above; entries below predate the release-please migration. -->

## [1.24.0](https://github.com/nivintw/dotfiles/compare/v1.23.2...v1.24.0) (2026-07-07)


### Features

* **portability:** Harden WSL detection, clipboard, DNS, and docs probes ([fcc6420](https://github.com/nivintw/dotfiles/commit/fcc6420b217d0e3bb03e266d4c5cd230f7518ece)), closes [#160](https://github.com/nivintw/dotfiles/issues/160) [#161](https://github.com/nivintw/dotfiles/issues/161) [#162](https://github.com/nivintw/dotfiles/issues/162) [#163](https://github.com/nivintw/dotfiles/issues/163)


### Bug Fixes

* **dock:** Make the rebuild atomic and skip when the Dock already matches ([dad5c51](https://github.com/nivintw/dotfiles/commit/dad5c51298c6cb26eab923ea5846cbdf1ecf625d)), closes [#155](https://github.com/nivintw/dotfiles/issues/155) [#156](https://github.com/nivintw/dotfiles/issues/156)
* **forrepos:** Refuse to fan out from $HOME or / ([2538585](https://github.com/nivintw/dotfiles/commit/2538585a5b6cfcecbb5fd8795a9c6824cb21f90a)), closes [#154](https://github.com/nivintw/dotfiles/issues/154)
* **install:** Harden stow cleanup, screencapture, and verify brew check ([da197d7](https://github.com/nivintw/dotfiles/commit/da197d75bbcc215da9a2259913f5ea6bc81992c6)), closes [#153](https://github.com/nivintw/dotfiles/issues/153) [#157](https://github.com/nivintw/dotfiles/issues/157) [#158](https://github.com/nivintw/dotfiles/issues/158)

## [1.23.2](https://github.com/nivintw/dotfiles/compare/v1.23.1...v1.23.2) (2026-07-06)


### Bug Fixes

* distinguish absent-vs-unreadable paths in the tamper-gate base lookup ([3c34b78](https://github.com/nivintw/dotfiles/commit/3c34b78ada6eb7ab0f0e4bd984747a5ca1b6704f))
* force C locale for the tamper-gate's git-error string match ([300e84c](https://github.com/nivintw/dotfiles/commit/300e84cfa6e2afd997756ff30d7aefcee49c7d0e))

## [1.23.1](https://github.com/nivintw/dotfiles/compare/v1.23.0...v1.23.1) (2026-07-06)


### Bug Fixes

* address 2 more Copilot findings (three-tier wording, vendor comment) ([8e1c087](https://github.com/nivintw/dotfiles/commit/8e1c087620e177f041e2b9b304a24d326bd2779f))
* drop redundant fish PATH block, correct CLAUDE.md overclaim ([01df00c](https://github.com/nivintw/dotfiles/commit/01df00c4265987bea9886dae95e7619d7cea8a75))
* **fish:** use $HOME instead of a hardcoded path for Rancher PATH ([b795365](https://github.com/nivintw/dotfiles/commit/b795365a765f57e04070afb48bfb0c7c9265190e))

## [1.23.0](https://github.com/nivintw/dotfiles/compare/v1.22.0...v1.23.0) (2026-07-06)


### Features

* **ollm:** add sandboxed --tools agentic mode ([75f35b9](https://github.com/nivintw/dotfiles/commit/75f35b900c7edbbfc0303a1b3359a9311e959b18)), closes [#121](https://github.com/nivintw/dotfiles/issues/121)


### Bug Fixes

* **ci:** also broaden the ty hook's own trigger, not just ruff's ([672f929](https://github.com/nivintw/dotfiles/commit/672f929e5e29f1f5af16e54e5da79dfa35a52cb3))
* **ollm:** 3 more Copilot findings — uninstall parsing, URL crash, ls symlink stat ([073a983](https://github.com/nivintw/dotfiles/commit/073a983a9e29960330b471e7572f41bb93e792e6))
* **ollm:** stop stat-ing symlink targets outside root before checking (Copilot review) ([2704849](https://github.com/nivintw/dotfiles/commit/27048491664c93852970ca4d276d77e796d2ec68))
* **ollm:** validate tool-call path/name shape before dispatch (Copilot review) ([748cfcd](https://github.com/nivintw/dotfiles/commit/748cfcd4228b302a4a2edae1fa361f7540fd382e))
* **uv-tools:** expose Ansible CLI shims and pin Serena to a real uv tool ([ce55c45](https://github.com/nivintw/dotfiles/commit/ce55c45abc501ec71301c1677731d1125269bbd2)), closes [#101](https://github.com/nivintw/dotfiles/issues/101) [#141](https://github.com/nivintw/dotfiles/issues/141)


### Performance Improvements

* **ollm:** stop materializing a whole directory before applying caps (Copilot review) ([de8fc10](https://github.com/nivintw/dotfiles/commit/de8fc10d2063e2b696a61aacb1eca9bfa61004eb))

## [1.22.0](https://github.com/nivintw/dotfiles/compare/v1.21.1...v1.22.0) (2026-07-06)


### Features

* **shell:** Add zsh as a selectable, opt-in login shell ([9dac03a](https://github.com/nivintw/dotfiles/commit/9dac03ae972ee38d95cd5549b5b3a54a4a7f6213)), closes [#35](https://github.com/nivintw/dotfiles/issues/35)


### Bug Fixes

* **ci:** Install zsh on the lint-and-test runner ([3e22699](https://github.com/nivintw/dotfiles/commit/3e22699ad0fe115c546a2052aaf889c8bbcbdf7e))
* **installer:** Check .zshenv is stowed; fail loudly on an invalid shell ([9ad9658](https://github.com/nivintw/dotfiles/commit/9ad9658c26e5a25ab2468c7b23f6f4d86e574679))
* **installer:** Check the real login shell, not \$SHELL, before chsh ([65e66ef](https://github.com/nivintw/dotfiles/commit/65e66ef13a12b2ed50d31bdb0f7ee3f468125c22))
* **installer:** Compare login shell by basename, not exact which() path ([bf77e91](https://github.com/nivintw/dotfiles/commit/bf77e9127f5cf32f7c9c2d979ca4eae950226dfd))

## [1.21.1](https://github.com/nivintw/dotfiles/compare/v1.21.0...v1.21.1) (2026-07-04)


### Bug Fixes

* **ci:** Persist Homebrew's PATH across steps in installer-smoke-linux ([304238e](https://github.com/nivintw/dotfiles/commit/304238ece0c0b9613cddd00a559a5e05c3675678))

## [1.21.0](https://github.com/nivintw/dotfiles/compare/v1.20.1...v1.21.0) (2026-07-04)


### Features

* **installer:** Generate VS Code settings and register Serena + claude-hud ([a2188a9](https://github.com/nivintw/dotfiles/commit/a2188a9e8eaa3414fdce448b3624a10500aa6cca))

## [1.20.1](https://github.com/nivintw/dotfiles/compare/v1.20.0...v1.20.1) (2026-07-04)


### Bug Fixes

* **installer:** Make Dock rebuild opt-out/safe and catch a silently hijacked pre-push hook ([36624d3](https://github.com/nivintw/dotfiles/commit/36624d3c843f9572c98a80d874f04290e2ce8c18)), closes [#41](https://github.com/nivintw/dotfiles/issues/41) [#124](https://github.com/nivintw/dotfiles/issues/124)

## [1.20.0](https://github.com/nivintw/dotfiles/compare/v1.19.0...v1.20.0) (2026-07-03)


### Features

* **installer:** Linux privileged setup + OS-aware verification (completes [#34](https://github.com/nivintw/dotfiles/issues/34)) ([e0a3fd5](https://github.com/nivintw/dotfiles/commit/e0a3fd50776d59202cb302926151c9afd8c394b0))
* **installer:** Linuxbrew package install on Linux + a Linux Tart smoke ([5c27bc4](https://github.com/nivintw/dotfiles/commit/5c27bc4ef7569e1cb1246b08bb0d2ffe733ceb66))
* **offload:** Rework local-model offload — role fleet, ollm CLI, roster hook, skill ([80eb3d4](https://github.com/nivintw/dotfiles/commit/80eb3d493e29ea3645265e6726ca61874c4d6932))


### Bug Fixes

* **ci:** Exclude the generated CHANGELOG from the typos hook ([3c12563](https://github.com/nivintw/dotfiles/commit/3c12563e846154642190fe1bf7fd562243e7ce78))
* **installer:** Abort the ufw enable when the SSH allow rule fails ([ab6ca16](https://github.com/nivintw/dotfiles/commit/ab6ca169ec2d33e9edcf8e1182c367f302873e03))
* **installer:** Address review — Linux re-run assert, bundle gating, comments ([aef13ba](https://github.com/nivintw/dotfiles/commit/aef13ba605ba9dddcbf75bbe83c1bf203b6ea0b8))
* **installer:** Allow SSH through ufw before enabling it (headless lockout) ([d0ec8fb](https://github.com/nivintw/dotfiles/commit/d0ec8fb838cb93b4ce0ea66d5fad2a60cb22836b))
* **installer:** Cover socket-activated OpenSSH; correct two docstrings ([0adc4f4](https://github.com/nivintw/dotfiles/commit/0adc4f419f4766fe9f694324a99450d9f63478c5))
* **installer:** Degrade to a BAD record when the UID has no passwd entry ([5b22537](https://github.com/nivintw/dotfiles/commit/5b22537aa52c2625290b96644f6b41bb30afc512))
* **installer:** Gate the Ollama app launch to macOS; fail the negative test loudly ([793082a](https://github.com/nivintw/dotfiles/commit/793082af9e8077adb4f72e23f9e86ba66b97154d))
* **installer:** OS-honest messaging for phase 2 and the Linux firewall check ([2769083](https://github.com/nivintw/dotfiles/commit/276908372ac48f536488b9e8aba43d6be7b36c46))
* **offload:** Harden ollm and the roster hook per review battery ([0a301aa](https://github.com/nivintw/dotfiles/commit/0a301aa49caa135df9022a105fba420b6a99776c))

## [1.19.0](https://github.com/nivintw/dotfiles/compare/v1.18.0...v1.19.0) (2026-06-30)


### Features

* **installer:** Add Linux/WSL2 foundation — OS-aware phases + shell bridges ([1828b9f](https://github.com/nivintw/dotfiles/commit/1828b9f65261070911c626b7255431ad7df96ab0))


### Bug Fixes

* **fish:** Harden Linux/WSL bridges from review (dnsflush WSL, stow guard, no-hang) ([98f9e81](https://github.com/nivintw/dotfiles/commit/98f9e81a2f08e7eba3bd2181945c2ca59b8affb3))

## [1.18.0](https://github.com/nivintw/dotfiles/compare/v1.17.0...v1.18.0) (2026-06-29)


### Features

* **installer:** Cut install.sh over to the Python installer ([010ec7c](https://github.com/nivintw/dotfiles/commit/010ec7c9852a2e6c93fe0699374353070424522c))
* **installer:** Port phases 14-16 and add verify CLI modes ([3a56c0b](https://github.com/nivintw/dotfiles/commit/3a56c0bd86a401d7bf4810ade958e0f559de45ff))


### Bug Fixes

* **installer:** Make the uv bootstrap errexit-safe ([edb266f](https://github.com/nivintw/dotfiles/commit/edb266f79accaa80d4218b6ebec7f726b1779cad))

## [1.17.0](https://github.com/nivintw/dotfiles/compare/v1.16.0...v1.17.0) (2026-06-29)


### Features

* **installer:** Port the verify-install summary to Python (phase 17) + dotfiles-doctor ([514811d](https://github.com/nivintw/dotfiles/commit/514811df6bf1892f81dce1adc6f7e2039aa7538d)), closes [#39](https://github.com/nivintw/dotfiles/issues/39) [#83](https://github.com/nivintw/dotfiles/issues/83)

## [1.16.0](https://github.com/nivintw/dotfiles/compare/v1.15.0...v1.16.0) (2026-06-29)


### Features

* **installer:** Port phases 3-13 to Python (modules + registry) ([32d2deb](https://github.com/nivintw/dotfiles/commit/32d2deb4047d9f75791fac8e6eda07885157b822))


### Bug Fixes

* **installer:** Address review findings on phases 3-13 ([6aec891](https://github.com/nivintw/dotfiles/commit/6aec8916a025f7aff199d5b5ffef766ddac0f3fc))
* **installer:** Degrade gracefully when op inject yields no parseable JSON ([9a34db5](https://github.com/nivintw/dotfiles/commit/9a34db58e9e69015a59b00b9158cb49fecf85149)), closes [#71](https://github.com/nivintw/dotfiles/issues/71)

## [1.15.0](https://github.com/nivintw/dotfiles/compare/v1.14.0...v1.15.0) (2026-06-29)


### Features

* **installer:** Port the privileged block (phase 2) to Python ([1f581be](https://github.com/nivintw/dotfiles/commit/1f581be23e37ea9c943cb748b9a13e2af19a06ae)), closes [#68](https://github.com/nivintw/dotfiles/issues/68) [#65](https://github.com/nivintw/dotfiles/issues/65)


### Bug Fixes

* **installer:** Address Copilot review on the privileged port ([2a55dc6](https://github.com/nivintw/dotfiles/commit/2a55dc66ae9cfa46a5412acdaf7efa53b31d0d2f))
* **installer:** Address review findings on the privileged port ([963c204](https://github.com/nivintw/dotfiles/commit/963c2047d2901b1bde257875ff6840fb2b9440dc))
* **installer:** Silence the run-level sudo -k backstop ([081ea80](https://github.com/nivintw/dotfiles/commit/081ea80c6c3ad9025221968718618d46cb890c9b))

## [1.14.0](https://github.com/nivintw/dotfiles/compare/v1.13.0...v1.14.0) (2026-06-28)


### Features

* Add scoped, idempotent uninstall.sh ([c24161b](https://github.com/nivintw/dotfiles/commit/c24161b871245cd9e2ba60a2efa4cf85fd10ba41)), closes [#36](https://github.com/nivintw/dotfiles/issues/36)
* **install:** Provision gated Ollama MLX model for Claude offload ([8392218](https://github.com/nivintw/dotfiles/commit/83922185d5de3f37e72d45ae7f5035dcaf31e249)), closes [#57](https://github.com/nivintw/dotfiles/issues/57)


### Bug Fixes

* Harden install non-fatality and uninstall failure honesty ([5ddd8a0](https://github.com/nivintw/dotfiles/commit/5ddd8a002898092905c50ef2ee3e981c0feecf16))
* **install:** Gate the MLX model pull on macOS 13+ too ([3f642bf](https://github.com/nivintw/dotfiles/commit/3f642bf5e8c0c566db12f87c37703a353364b602))
* **uninstall:** Correct --help to list TPM under OFFERS, not auto-removed ([d35548c](https://github.com/nivintw/dotfiles/commit/d35548c598edf6e1b2de151c8ee5a7901cb7049f))
* **uninstall:** Shell-escape the retry-by-hand hint in failed-step records ([15cd848](https://github.com/nivintw/dotfiles/commit/15cd848a5176495c1f0ee4647c73fa78ec21e0e6))

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
