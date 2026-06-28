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

The heavyweight end-to-end VM smoke test is **opt-in** and never part of the above — see
[End-to-end VM smoke test](#end-to-end-vm-smoke-test-opt-in) below.

## bats — fish behavior

- **`git_prune_local.bats`** — the branch-pruning logic, the one function where a
  bug would delete unmerged work. Each test builds a throwaway repo with a local
  bare `origin` and asserts `--dry-run` decisions across the full matrix: merged +
  gone remote, multi-commit squash-merge, gone-but-unmerged (kept), merged
  local-only, unmerged local-only (kept), the current branch (never deleted), and
  a live-upstream branch (kept). Non-destructive — only `--dry-run` is exercised.
- **`fish_functions.bats`** — guard rails of the small wrapper helpers: usage
  messages, "not a git repository" (the fuzzy-checkout family), invalid-signal
  rejection (`fkill`), and the `pyclean --dry-run` no-delete path. The interactive
  happy paths (fzf/rg/git pickers) aren't driven headless.
- **`check_ssh_config.bats`** — the `no-concrete-ssh-hosts` guard, both ways: a
  generic config passes, while a planted concrete `Host`, `HostName`, `User`, or
  IP literal fails the commit.

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
  gitleaks doesn't know). Also self-tests the detector — it must match synthetic
  token shapes and must ignore the `op://` form — so the absence checks can't rot
  into green-by-default.
- **`test_manifests.py`** — Brewfile lines use known directives; `uv_tools.txt`
  lines are well-formed (`--with` flags paired).
- **`test_consistency.py`** — tools the scripts/hooks use are in the Brewfile,
  local hook scripts exist and are executable, and `install.sh`'s managed-files
  list matches what's actually stowed under `home/`.
- **`test_coverage.py`** — inventory coverage (see below).

## Coverage — what it means here

`coverage.py` is the wrong instrument for this repo: it would only measure these
Python helpers, which are thin glue, and say nothing about the fish/bash/config
that *is* the dotfiles. So the metric isn't line coverage — it's **inventory
coverage**: every shippable artifact either has a behavior test or sits on an
explicit, documented allowlist.

`test_coverage.py` enforces it. Every fish function and shell script must be named
in a bats test, or appear in the `UNTESTED_*` allowlist with a reason (the repo's
"known gaps" ledger — e.g. interactive-only pickers, thin wrappers, host-mutating
bootstrap). Add a function with no test and no entry, and the build goes red.
Stale or now-tested allowlist entries fail too, so the ledger stays honest.

This layers on top of the checks that already sweep *every* file: `fish -n`
parses each function, `shellcheck` lints each script, and `test_data_files.py`
parses each config. Inventory coverage answers the orthogonal question — does
each thing that can break have *something* watching it?

## End-to-end VM smoke test (opt-in)

`scripts/vm-smoke.sh` boots a clean [Tart](https://tart.run) VM, ships the repo in with
`git archive HEAD`, runs `install.sh` end-to-end inside it from scratch (by default
**twice**, to prove idempotency), and gates on `verify_install`'s `OK`/`BAD` stream — the
one thing the unit/config suites can't do: prove the installer works on a genuinely clean
machine. It tolerates only the Touch-ID-no-sensor `BAD` (a VM has no biometric sensor); the
application firewall and every other check stay strict, and a `VERIFY_DONE` sentinel makes a
truncated SSH stream fail closed rather than read as a pass.

It is **heavy and opt-in**: the first run pulls a multi-GB macOS base image and a full
install takes many minutes, so it never runs in the default `uv run pytest`.

**Prerequisite:** `tart` (in the Brewfile — `brew bundle` installs it) on an Apple Silicon
host. SSH into the guest authenticates via `SSH_ASKPASS`, so no password ever lands in the
process list.

```bash
# Directly:
scripts/vm-smoke.sh                 # clone -> boot -> install x2 -> verify -> teardown
scripts/vm-smoke.sh --once          # install only once (skip the idempotency re-run)
scripts/vm-smoke.sh --negative      # self-test: break the firewall, assert the gate fails
scripts/vm-smoke.sh --keep          # leave the VM in place to debug a failure
scripts/vm-smoke.sh --image REF     # clone a different base image

# Via pytest (opt-in gate — only runs with the env var set and tart present):
DOTFILES_VM_SMOKE=1 uv run pytest -m integration
```

`tests/vm_smoke.bats` unit-tests the harness's arg-parsing, preflight, and the pure
verify-gate helpers (`is_tolerated` / `evaluate_stream`) without booting a VM — the script is
sourceable for exactly this. The boot-and-install path is covered by the opt-in pytest above.
It targets the current bash installer today and is the verification gate for the Python
installer rewrite (#53).
