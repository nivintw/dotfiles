# Quality & Testing

Guiding principle: don't build a test suite heavier than the thing it tests. A
broken alias costs seconds; a leaked secret or a bricked bootstrap costs real
money — spend the budget there.

## The testing pyramid

Three layers, each matched to what it's actually protecting against — cheap
static checks on every commit, focused behavior and config tests in CI, and a
small number of real end-to-end installs at the top.

| Layer | Runs | What it proves |
| --- | --- | --- |
| **1 · Static analysis** | every commit + CI | lint, syntax (`shellcheck`, `fish -n`, `zsh -n`), secret scan ([gitleaks](https://github.com/gitleaks/gitleaks)), spelling ([typos](https://github.com/crate-ci/typos)), formatting ([taplo](https://taplo.tamasfe.dev/)) |
| **2 · Unit + config tests** | CI | [bats](https://github.com/bats-core/bats-core) — fish + zsh behavior; [pytest](https://docs.pytest.org/) — config validity + installer-core coverage |
| **3 · Integration** | CI smoke + local VM | `install.sh` on ephemeral CI runners; a [Tart](https://tart.run) VM (2× run) locally |

## Layer 1 — the hook suite

Run on every commit by [prek](https://github.com/j178/prek) and re-run
identically in CI. Most hooks self-bootstrap a pinned environment; the handful
that need a system binary (`fish`, `zsh`, `ty`, `taplo`, `hawkeye`, the local
scripts) come from the Brewfile or `uv`.

| Category | Hooks |
| --- | --- |
| 🌳 **Git hygiene** | large-file block · conflict markers · `main`-branch protection · case-conflict (macOS FS) · shebang ⇄ exec-bit · LF line endings · trailing whitespace · single newline at EOF |
| 🔒 **Security** | **gitleaks** secret scan · `detect-private-key` · a custom **no-concrete-ssh-hosts** guard |
| 🔒 **Dependency CVEs** | **`uv audit`** (resolved deps vs PyPA advisories) · **osv-scanner** (`uv.lock` vs the OSV database) |
| 🗂️ **Config validity** | YAML / JSON / TOML parse checks · `validate-pyproject` |
| 🐚 **Shell** | **shellcheck** lint · **shfmt** format |
| 🐟 **Fish** | `fish -n` syntax · `fish_indent` formatting |
| 🐚 **Zsh** | `zsh -n` syntax (no formatter — there's no `zsh_indent`) |
| 🐍 **Python** | [**ruff**](https://docs.astral.sh/ruff/) check + format · [**ty**](https://github.com/astral-sh/ty) type-check |
| 📐 **YAML** | **yamllint** style (beyond the parse check above) |
| 📝 **TOML** | **taplo** format |
| 📝 **Markdown** | [**rumdl**](https://github.com/rvben/rumdl) lint/format |
| ✨ **Spelling** | **typos** — check-only, never auto-writes |
| ⚙️ **GitHub Actions** | **actionlint** (lints workflows + their `run:` blocks) · **zizmor** security audit |
| ⚖️ **Licensing** | [**hawkeye**](https://github.com/korandoru/hawkeye) SPDX headers · [**REUSE**](https://reuse.software/) compliance |
| ✨ **Commits** | [**commitizen**](https://commitizen-tools.github.io/commitizen/) enforces [Conventional Commits](https://www.conventionalcommits.org/) at `commit-msg` (feeding [release-please](https://github.com/googleapis/release-please)) |
| ⚙️ **Environment** | `uv-lock` keeps `uv.lock` in sync with `pyproject.toml` |

```bash
prek run --all-files     # validate the whole tree
prek install             # install the git hooks
```

!!! note "Plain Conventional Commits — no gitmoji"
    Commit messages start with a bare type (`feat:`, `fix:`, …). release-please
    derives version bumps from the commit type and can't parse a leading emoji.
    The joyful emoji labels live on the prek hooks themselves, not in commit
    messages.

## Layer 2 — tests

Two runners, each idiomatic for its half — they don't overlap. The tables below
are representative; the suites are broader (see `tests/`).

### bats — fish + zsh behavior

| File | Asserts |
| --- | --- |
| `git_prune_local.bats` | The full branch-state matrix — merged, squash-merged, gone-remote, current-branch — where a bug deletes work |
| `git_prune_local_zsh.bats` | The zsh twin of the above, exercising the same matrix |
| `fish_functions.bats` | Usage / guard paths of the fish wrapper helpers |
| `zsh_functions.bats` | The same guard-rail coverage for the ported zsh functions, plus OS-dispatch (macOS / Linux / WSL) via a `uname` shim |
| `check_ssh_config.bats` | The SSH-host guard both ways — generic passes; a planted host / IP / user fails |

### pytest — config & coverage

| File | Asserts |
| --- | --- |
| `test_data_files.py` | Every `*.toml` parses; JSON / JSONC / plist load |
| `test_secret_hygiene.py` | No literal token in `claude_mcp.json`; GitHub auth stays an `op://` reference |
| `test_manifests.py` | Brewfile directives & `uv_tools.txt` lines are well-formed |
| `test_consistency.py` | Tools used by hooks are in the Brewfile; managed files are stowed |
| `test_coverage.py` | Inventory coverage — every function & script is tested or on a documented allowlist |
| `test_docs_site.py` | Drives the docs site headless via pytest-playwright |
| `pytest --cov` | Line coverage of the installer core (`src/dotfiles_install/`) stays above a floor (`fail_under = 95`, config in `pyproject.toml` `[tool.coverage]`) |

```bash
bats tests/          # fish + zsh behavior
uv run pytest        # config validity + consistency
uv run pytest --cov  # + the installer-core line-coverage gate
```

!!! tip "`--cov` is opt-in on purpose"
    Coverage isn't in `addopts`, so a bare `pytest tests/test_foo.py` during
    development doesn't report partial coverage and trip `fail_under`. The gate
    runs explicitly via `pytest --cov` — the local [check](getting-started.md)
    stage and CI both use it.

## Layer 3 & CI

CI runs the real bootstrap directly on ephemeral GitHub-hosted runners — no VM
needed there, since a fresh Actions runner already *is* a clean machine for one
pass. `installer-smoke-macos` and `installer-smoke-linux` each run
`install.sh --no-bundles --core` once, then gate on the installer's
`--verify-stream` output — tolerating only the no-Touch-ID-sensor case on macOS;
Linux runs fully strict (it never emits that record).

What CI can't cheaply prove is **idempotency** — that means running the installer
twice, and macOS's Touch ID sudo prompt makes that awkward without a disposable
environment — so that's still `scripts/vm-smoke.sh`'s job: it boots a clean
[Tart](https://tart.run) VM (macOS or Linux), runs `install.sh --core` from
scratch *twice*, and gates on the same `--verify-stream` output. It's heavy and
opt-in (a multi-GB base image plus two full installs), so it runs on demand —
`scripts/vm-smoke.sh` or `DOTFILES_VM_SMOKE=1 uv run pytest -m integration` —
never in the default suite. The prek **pre-push** hook runs it automatically for
installer-path changes and skips cleanly when Tart isn't installed.

!!! note "CI — five jobs"
    `ci.yml` is a reusable workflow (`workflow_call`) invoked by `pr.yml` on pull
    requests and by `main.yml` on pushes to `main`, so both pipelines run the
    identical gate. It defines five jobs:

    - **secret-scan** (`ubuntu-latest`) — a full-history [gitleaks](https://github.com/gitleaks/gitleaks) scan (`fetch-depth: 0`), catching a secret that was committed then removed in a later commit. It fails loudly on a shallow checkout rather than silently scanning partial history. (The pre-commit `gitleaks` hook only sees *staged* changes, so this is the CI complement.)
    - **lint-and-test** (`ubuntu-latest`) — runs the **same prek hooks** (not a parallel set of actions), plus `bats tests/` and `uv run pytest --cov` (which enforces the installer-core coverage floor). It pre-installs the few `language: system` tools it needs (`fish`, `zsh`, `bats`, `ripgrep`); `taplo`, `hawkeye`, and the online **zizmor** audit run as dedicated steps (their `language: system` hooks are `SKIP`'d), and its release-binary fetches (osv-scanner, hawkeye, taplo) are version-pinned **and** SHA256-verified on download. An informational `kcov` step reports shell line-coverage of the bats-exercised `scripts/` — not a gate.
    - **installer-path-gate** (`ubuntu-latest`) — computes once, via a single full-history checkout, whether this push/PR touched an installer path, separately for macOS and Linux (they skip different phases). It fails *open* — running both installers — if the git diff itself errors, so a plumbing hiccup can't masquerade as a green build.
    - **installer-smoke-macos** (`macos-latest`) and **installer-smoke-linux** (`ubuntu-latest`) — each depend on the gate and, when it says so, run the real `--core` install once on an ephemeral runner. Path-gated to installer-touching changes, so most PRs skip the heavy work while still reporting a stable, always-green success — making them safe required-status checks.

See [Security](security.md) for the secret-scanning and SSH-host guards in depth,
and [Architecture](architecture.md) for the installer phases the smoke jobs
exercise.

## Licensing

The repo is **REUSE 3.3** compliant. Every file that can carry a comment gets an
SPDX header, maintained by **hawkeye** from a single templated source; the
handful that can't (strict JSON, the binary iTerm plist, generated lockfiles) —
plus `docs/llms.txt` / `docs/llms-full.txt`, which technically could but a header
would break the llms.txt spec's first-line-is-the-title contract — are annotated
in `REUSE.toml` instead. In the prek gate the two are complementary, not
redundant: **hawkeye** adds/formats headers while **reuse** verifies overall
compliance; in CI both run in check-only mode and fail on drift.

<!-- REUSE-IgnoreStart -->

```text
# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT
```

<!-- REUSE-IgnoreEnd -->
