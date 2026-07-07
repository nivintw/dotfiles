# Quality &amp; Testing

Guiding principle: don't build a test suite heavier than the thing it tests. A broken alias
costs seconds; a leaked secret or a bricked bootstrap costs real money — spend the budget
there.

## The testing pyramid

```text
  many  ┌─ Layer 1 · Static analysis (every commit + CI) ─┐  shellcheck, fish -n,
        │         lint · secret scan · syntax             │  typos, gitleaks, taplo
        ├─ Layer 2 · Unit + config tests (CI) ────────────┤  bats: fish + zsh behavior
        │         logic + declarative-config checks       │  pytest: config validity
        ├─ Layer 3 · Integration (CI smoke + local VM) ───┤  install.sh on ephemeral runners,
  few   └─        idempotency · real bootstrap ───────────┘  Tart VM (2× run) locally
```

## Layer 1 — the hook suite

Run on every commit by prek and re-run identically in CI. Most hooks self-bootstrap a pinned
environment.

- **Git hygiene** — large-file block, conflict markers, main-branch protection, case-conflict
  (macOS FS), shebang ⇄ exec-bit, LF endings, trailing whitespace, EOF newline.
- **Security** — gitleaks secret scan, `detect-private-key`, a custom no-concrete-ssh-hosts
  guard.
- **Config &amp; format** — YAML/JSON/TOML validity, taplo (TOML), rumdl (Markdown),
  ruff check + format, ty type-check, validate-pyproject, uv-lock sync.
- **Languages** — shellcheck + `bash -n`, fish -n + `fish_indent`, typos (check-only).
- **Licensing &amp; commits** — hawkeye SPDX headers, REUSE compliance, Conventional Commits via
  commitizen, release-please releases.

```bash
prek run --all-files     # validate the whole tree
prek install             # install the git hook
```

## Layer 2 — tests

Two runners, each idiomatic for its half — they don't overlap.

| Suite | File | Asserts |
| --- | --- | --- |
| bats (fish + zsh) | `git_prune_local.bats` | The full branch-state matrix — merged, squash-merged, gone-remote, current-branch |
| | `fish_functions.bats` | Usage / guard paths of the fish wrapper helpers (OS dispatch, WSL/Wayland clipboard, DNS fallbacks) |
| | `zsh_functions.bats` | The same guard-rail coverage for the ported zsh functions |
| | `dock.bats` | The Dock rebuild: atomic restart on a mid-rebuild failure, idempotent skip, `--check` drift |
| | `check_ssh_config.bats` | The SSH-host guard both ways — generic passes, a planted host/IP/user fails |
| pytest (config &amp; coverage) | `test_data_files.py` | Every `*.toml` parses; JSON/JSONC/plist load |
| | `test_secret_hygiene.py` | No literal token in `claude_mcp.json`; GitHub auth stays an `op://` reference |
| | `test_stow.py` / `test_verify_install.py` | Installer-core behavior (stow cleanup, verify records) |
| | `test_consistency.py` | Tools used by hooks are in the Brewfile; managed files are stowed |
| | `test_coverage.py` | Inventory coverage — every function &amp; script is tested or on a documented allowlist |
| | `template_sync.bats` | Every template-owned file matches the copier render unless a divergence is registered |

```bash
bats tests/          # fish + zsh behavior
uv run pytest --cov  # config validity, consistency + installer-core line-coverage gate
```

## Layer 3 &amp; CI

CI runs the real bootstrap directly on ephemeral GitHub-hosted runners — no VM needed there,
since a fresh Actions runner already *is* a clean machine for one pass. `installer-smoke-macos`
and `installer-smoke-linux` each run `install.sh --core` once, then gate on the installer's
`--verify-stream` output — tolerating only the no-Touch-ID-sensor case on macOS; Linux runs
fully strict.

What CI can't cheaply prove is idempotency — that means running the installer twice — so
that's still `scripts/vm-smoke.sh`'s job: it boots a clean Tart VM (macOS or Linux), runs
`install.sh --core` from scratch *twice*, and gates on the same `--verify-stream` output. It's
heavy and opt-in, so it runs on demand — `scripts/vm-smoke.sh` or
`DOTFILES_VM_SMOKE=1 uv run pytest -m integration` — never in the default suite.

`ci.yml` also runs a full-history `gitleaks` secret scan and, on `lint-and-test`, the same prek
hooks plus `bats tests/` and `uv run pytest --cov`, followed by an informational `kcov` step
reporting shell line-coverage of the bats-exercised `scripts/`.

## Licensing

The repo is REUSE 3.3 compliant. Every file that can carry a comment gets an SPDX header,
maintained by hawkeye from a single templated source; the handful that can't (strict JSON, the
binary iTerm plist, generated lockfiles) are annotated in `REUSE.toml` instead — plus
`docs/llms.txt`/`docs/llms-full.txt`, which *could* carry a `#`-comment header but are excluded
for a spec-conformance reason (a header would parse as a stray heading ahead of the file's real
first-H1 title).
