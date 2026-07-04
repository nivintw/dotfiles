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
uv run pytest          # the installer package + config validity & consistency
bats tests/            # fish/shell behavior (needs bats-core + fish, both in the Brewfile)
```

The installer is exercised end-to-end against a clean VM by the opt-in Tart smoke harness
(`DOTFILES_VM_SMOKE=1 uv run pytest -m integration`, or `scripts/vm-smoke.sh` directly) — run
it before pushing any change under the installer paths (`install.sh`, `src/dotfiles_install/`,
`scripts/vm-smoke.sh`, `macos.sh`, `dock.sh`). The prek **pre-push** hook runs it automatically
for those paths, skipping cleanly when Tart isn't installed.

## Layout

- `home/` — stowed into `$HOME` (e.g. `home/.claude/` → `~/.claude/`). Editing a
  stowed file edits the live target.
- `src/dotfiles_install/` — **the installer.** A real Python package exposing the
  `dotfiles-install` console script; an ordered phase registry (`phases.py`) walks
  bootstrap → brew → stow → … → verify. This is where install logic lives.
- `install.sh` — a thin shim: macOS guard + uv bootstrap, then `exec uv run … dotfiles-install`.
  Idempotent, safe to re-run. Don't add install logic here — add a phase.
- `Brewfile` / `Brewfile.d/` — package manifests; `macos.sh` — system defaults.
- `docs/` — static docs site with asciinema casts; `tests/test_docs_site.py` drives
  it via pytest-playwright.
- `scripts/` — repo helper scripts. `tests/` — pytest (`test_*.py`: the installer
  package + config validity) and bats (`*.bats`, fish behavior).

## Gotchas

- **`~/.claude/settings.json` is generated, not stowed.** The installer deep-merges
  the tracked `claude_settings.json` baseline with the untracked
  `~/.config/dotfiles/claude_settings.local.json` overlay (arrays like
  `permissions.allow` union; the overlay wins per scalar) and writes a real file.
  `/config`, `/plugin`, and plugin installs write through that real file; the next
  install run folds whatever they changed into this machine's overlay — not the
  repo. Change shared defaults by editing `claude_settings.json` and re-running
  install. Merge logic + caveats live in `src/dotfiles_install/settings_merge.py`.
- **`.gitconfig` overlays via git's native `[include]`, not a generated merge.** The
  tracked `home/.gitconfig` is stowed and `[include]`s `~/.gitconfig_local` **last**,
  so the overlay wins for every key. It ships **no `[user]` identity** — that lives in
  the overlay. A pre-existing real `~/.gitconfig` is backed up to `*.pre-stow.bak` and
  its contents folded into `~/.gitconfig_local` before stow (so a fresh install never
  stomps it). Logic in `src/dotfiles_install/gitconfig_migrate.py`. Don't add a jq-style
  merge here — git layers config itself; only `settings.json` needs the generated merge.
- **The installer is a real package** (`[tool.uv] package = true`, hatchling build).
  pyproject.toml declares the `dotfiles-install` console script (`[project.scripts]`)
  and the installer's runtime deps (`rich`, `typer`) under `[project.dependencies]`;
  everything else is dev-only (`[dependency-groups].dev`). `install.sh` hands off via
  `uv run --no-dev … dotfiles-install`, so end-user installs skip the dev toolchain.
  Manage deps with `uv` (`uv add` / `uv add --group dev`), never by hand.
- **SPDX headers are required** — reuse/hawkeye enforce them; new files need a
  license header (the hooks add/format them).
- **`docs/llms.txt`/`docs/llms-full.txt` are hand-maintained, not generated.** No script
  ties them to `docs/*.html` — they're a separate source of truth that drifts silently on
  the next docs edit unless someone re-syncs them by hand (a real instance of this already
  happened once: a clause dropped from `llms-full.txt`'s security table mid-authoring,
  caught only by a `/simplify` review pass). `.txt` is in hawkeye's `SCRIPT_STYLE` mapping
  (`.config/licenserc.toml`), so both files are explicitly excluded there and licensed via
  `REUSE.toml` instead — a `#`-comment header would parse as a stray H1 ahead of the real
  one, breaking the llms.txt spec's "first H1 is the title" contract. `link-check.yml`'s
  path/glob includes both files, so at least broken links self-report; prose drift does
  not. Treat both as reconciliation targets on every future docs refresh (`/dev-kit:generate-docs`
  or by hand), not just the HTML pages.
- **Serena is self-hosted in `claude_mcp.json`, not the marketplace plugin.** The
  official `serena@claude-plugins-official` plugin runs `serena start-mcp-server` with
  no flags, which means: no `--project-from-cwd` (so it can't tell which project you're
  in across worktrees), a hardcoded 60s tool timeout (Serena's first-run LSP indexing on
  a large repo can exceed that), and its dashboard auto-opens a browser tab on every
  session start. The self-hosted `claude_mcp.json` entry pins `--project-from-cwd`, the
  `claude-code` built-in context (not a custom vendored one — Serena ships this context
  specifically for this client), `--open-web-dashboard False` (dashboard still reachable
  manually, just no surprise tab), and `MCP_TIMEOUT=200000` in `env` (Claude Code's own
  client-side MCP timeout, not Serena's `--tool-timeout`). `claude_settings.json`
  explicitly sets `serena@claude-plugins-official: false` so a fresh install doesn't
  register both. **This only disables it on a fresh install.** `generate_settings`
  (`settings_merge.py`) re-reads the *live* `~/.claude/settings.json` every run and folds
  any drift from the baseline back into the overlay — so the *first* run after this landed
  on a machine where the plugin was already live-enabled (`true`) permanently **caches**
  `true` into `~/.config/dotfiles/claude_settings.local.json`. From then on the overlay
  itself keeps re-asserting `true` on every run regardless of the live file — verified by
  driving `merge`/`diff` directly: running `claude plugin disable
  serena@claude-plugins-official` (which only flips the *live* file) does **not** fix it,
  because the next run reads live `false` (no new drift, since it now matches the
  baseline) but still folds the overlay's stale cached `true` into the merge, and writes
  `true` right back out — silently undoing the disable in the same run that reads it. The
  overlay is the actual source of truth here, not the live file. **The real fix**: edit
  `~/.config/dotfiles/claude_settings.local.json` and remove (or set `false`) the
  `serena@claude-plugins-official` key under `enabledPlugins`, *and* disable the plugin
  live via Claude Code (`claude plugin disable serena@claude-plugins-official`) — both, not
  either — then re-run install. Skipping either one leaves it re-enabling itself: overlay
  alone reverts on the next run's drift-fold (live is still `true`), live alone reverts
  because the overlay's stale cached `true` never gets cleared by a later run (the merge
  engine only *adds* drift, per its own documented limitation — it never removes an overlay
  key on its own).
- **The vetted plugin baseline has three tiers, not two.** `claude_settings.json`'s
  `enabledPlugins` distinguishes tracked-and-default-on (`true` — e.g. `castify`,
  `worktree-guard`), tracked-but-opt-in (`false` — vetted and known, e.g. `serena`,
  `claude-hud`; flip to `true` in your local overlay to enable), and untracked/ad-hoc
  (installed via `/plugin` on one machine, never added here — fine for a one-off, but it
  won't reproduce on a fresh install). `claude-hud`'s marketplace is `extraKnownMarketplaces`-registered
  here too, but its `statusLine` command block is **not** hand-copied into this repo —
  that command string is plugin-version-resolving (it globs
  `plugins/cache/*/claude-hud/*/` for the newest installed copy) and would go stale the
  moment claude-hud restructures its own directories. Enable the plugin, then run
  `/claude-hud:setup` (its own configurator) to write the real command for your machine.

## Git & releases

- **`main` is protected** (prek `no-commit-to-branch`). Make changes on a branch in
  a git worktree, then open a PR. Live-test stow-symlinked dotfiles in the main
  checkout first, then move the change into a worktree for the PR.
- **Commits:** write a plain Conventional Commit (`type(scope): Description`) — **no
  gitmoji**. release-please derives version bumps from the bare commit type and can't
  parse a leading emoji, so don't prepend one. (The joyful emoji labels live on the
  prek hooks, not in commit messages.)
- **Releases:** release-please drives versioning and `CHANGELOG.md` (manifest mode). The
  version-of-record is `.config/.release-please-manifest.json` + the `vX.Y.Z` git tags;
  release-please *mirrors* that version into `pyproject.toml` and `uv.lock` (the `dotfiles`
  entry) via `extra-files`, rewriting **both** together so `uv lock --check` stays green —
  it's now the built wheel's version (`package = true`), so keep the three in step
  (manifest = pyproject = uv.lock). On push
  to `main`, release-please maintains a Release PR (CHANGELOG + manifest) that auto-merges
  by rebase once the required CI check passes, then cuts the tag + GitHub Release. `main`
  has no signature requirement, so the App token's rebase-merge lands directly. The
  changelog and manifest are tool-generated — don't hand-edit.
