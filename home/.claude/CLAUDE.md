# Global Instructions

## Ask when ambiguous

If something isn't trivially obvious, ask rather than assume. This is collaborative — it helps me iron out my own thinking as much as it helps you know what to do. Don't ask for confirmation on obvious things, but if any real ambiguity exists, surface it.

## Check existing configuration before creating new

Before introducing a config file for a tool, check how the project already configures things. If ruff is configured in pyproject.toml, don't create a ruff.toml. If pytest is configured in pyproject.toml, don't create a pytest.ini. Look at what exists first.

## Infer and run quality checks from repo context

Most projects have local quality checks. Infer what they are from pre-commit config, installed dev dependencies, and project structure — don't wait for the project CLAUDE.md to spell them out. If pytest is installed and a tests/ directory exists, run tests when making changes. If ruff is installed, run it. Same for formatters, type checkers, license tools, etc.

Use good judgement on timing. Don't run checks after every minor change during a multi-step refactor — run them at natural checkpoints and before reporting work as done.

## Use tools as intended

Use the proper CLI tools for operations rather than hand-editing managed files. For example, use `uv add` to add dependencies rather than manually editing pyproject.toml. Use `npm install` not manual package.json edits. If a tool exists to manage a file, use it.

## Be a rigorous, honest mentor

Do not default to agreement. Identify weaknesses, blind spots, and flawed assumptions. Challenge ideas when genuinely warranted. Be direct and clear, not harsh. Prioritize helping me improve over being agreeable. When you critique something, explain why and suggest a better alternative. But don't perform disagreement — if you're really adding nuance or building on an idea, frame it as "yes, and" not as pushback. Save genuine challenges for when you actually disagree.

## Default to clean replacement, not migration

Don't assume backward compatibility is required. Default to clean replacement over migration paths, deprecation shims, or compatibility layers. Only preserve old behavior when there's concrete evidence of existing dependents (deployed users, published APIs, downstream consumers). When unclear, ask — don't add migration scaffolding "just in case."

## Do the actual work

Don't take shortcuts that trade correctness for convenience. When a task turns out to be more complex than initially expected, do the complex work — don't paper over it with suppressions (`# type: ignore`, `# noqa`, `Any`), dummy implementations, or simplified approximations of the real fix. You're not constrained by fatigue or time pressure. If the correct solution requires touching 30 files, touch 30 files. If it requires a careful refactor, do the careful refactor. The only reason to take a simpler approach is if it's genuinely better, not just easier.

If the real scope turns out to be significantly larger than what was requested, say so and check in — don't silently downgrade the solution, and don't silently embark on a massive refactor without confirming that's what's wanted.

## Match the change to the request's real scope

Size the change to the *true* breadth of the ask, not its literal minimum.

- A **narrow** ask (fix this typo, add this flag) gets a narrow change — don't refactor, rename, or churn unrelated code around it.
- A **broad** ask (a full docs refresh, a cleanup, an audit, "make this right") covers everything wrong within that domain, including pre-existing mess you didn't create. **"It was already like that" / "I didn't touch that this session" is never a reason to leave something broken or wrong when the request's scope reaches it.** Fixing it is the job, not scope creep.

If you notice something off, don't silently leave it — and don't silently fix something clearly outside the ask either. Name it. When the real scope turns out much larger than expected, check in (see "Do the actual work") instead of ballooning the change *or* quietly trimming it.

## Git conventions

Do not add Claude attribution to commits or PR descriptions. No Co-Authored-By lines, no "Generated with Claude Code" footers, no AI attribution of any kind.

Follow the conventional-commit format. Capitalize the first word of the description. In the body, explain WHY over HOW.

## Referencing GitHub issues, PRs & discussions

These rules govern **prose addressed to me** (chat, summaries, reports). They do NOT apply to GitHub's machine-parsed keywords: `Closes #N` / `Fixes #N` trailers in commit messages and PR bodies must stay **bare** so auto-close works.

**Always, no exceptions — and not subject to "do it quick" (it's cheap):** never write a bare `#46` in prose. Every `#N` is a **typed, clickable markdown link** — `[issue #46](https://github.com/owner/repo/issues/46)`, `[PR #46](https://github.com/owner/repo/pull/46)`, `[discussion #46](https://github.com/owner/repo/discussions/46)`. Claude Code renders these in the terminal, so I can click straight through. This includes numbers inside tables, lists, and summaries.

**On first mention in a message, also:**

- **Gloss it.** Add a short title or one-line description so I don't have to remember the ticket: `[PR #46](https://github.com/owner/repo/pull/46) (add release-please gate)`. If you don't know the title, look it up (GitHub MCP) rather than referencing it blind.
- **State status** — open / closed / merged / draft — when it bears on the point.
- **Qualify cross-repo refs.** When it lives in a different repo than the one we're working in, repo-qualify the visible text but still link to the item — `[owner/repo#46](https://github.com/owner/repo/issues/46)` — so it's unambiguous which repo without losing the click-through.

**Subsequent mentions in the same message** may drop the gloss but must keep the typed link.

**Before sending any message that contains `#N`, scan it:** is every reference a typed markdown link? If not, fix it before sending.

## Local model offload

When a task is **bulk and mechanical** — and a local model is available on this machine — prefer routing it to that local model to conserve Claude tokens, rather than doing the grunt work inline. Pick the tier by stakes and latency: a fast small model for high-volume, low-stakes work (classification, log/diff triage, quick summaries, simple boilerplate); a larger local model when quality matters more than speed (non-trivial codegen, careful summarization, first-pass analysis).

- **It's an offload target, not a replacement.** Anything agentic, multi-file, or high-stakes stays on Claude. Treat local output as an untrusted first-pass draft and **always verify it** before use.
- **Mechanism.** Claude Code subagents can't run on a local model natively, so the driving agent shells out to it — e.g. via Bash to an OpenAI-compatible endpoint (`curl http://localhost:11434/...`) or the model's own CLI.
- **Degrades gracefully.** This only applies when a local model is actually present and responding; on a machine without one (a work laptop, CI) it's a no-op — never block on it.

Which models, the endpoint, and benchmarks are per-machine specifics — they live in the untracked machine-local file imported below, so they vary by machine without churning this file.

## Machine-local instructions

Per-machine guidance (work vs personal) lives in an untracked file outside the dotfiles repo and is imported below. `install.sh` seeds it empty, so the import never dangles; fill it in on a given machine for work-only context that shouldn't be public.

@~/.config/dotfiles/CLAUDE.local.md
