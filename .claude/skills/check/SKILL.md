---
name: check
description: >-
  Run the full local quality gate for the dotfiles repo — prek hooks, the pytest
  config-validation suite, and the bats fish/shell behavior tests — reporting
  pass/fail per stage. Use before committing or opening a PR, or when asked to "run
  the checks", "run the gate", or confirm the repo is green.
---

# /check — run the dotfiles quality gate

Run the three stages below in order, from the repo root. Run all three even if an
earlier one fails, so the report is complete, then summarize.

1. **prek — lint / format / security / license / commit hooks**

   ```bash
   prek run --all-files
   ```

2. **pytest — config validity, consistency & installer-core coverage gate**

   ```bash
   uv run pytest --cov
   ```

   `--cov` enforces the line-coverage floor for `src/dotfiles_install/` (see
   `[tool.coverage]` in `pyproject.toml`). Omit it for a quick subset run.

3. **bats — fish / shell behavior**

   ```bash
   bats tests/
   ```

## Reporting

Report each stage as pass or fail with a one-line summary. For a failure, surface
the specific failing hook or test and the actionable error. If all three pass, say
the gate is green. Report first — don't fix issues unless the user asks.
