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
