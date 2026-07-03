---
name: local-offload
description: Offload a bounded, mechanical sub-step to a local Ollama model via the `ollm` CLI to save Claude tokens. Use whenever a task contains a self-contained chunk of classification, log/diff/output triage, summarization, boilerplate or scaffolding generation, commit-message drafting, test-data generation, screenshot/diagram reading, or first-pass analysis — even mid-task. Trigger on the sub-step, not the whole task; if part of the work is mechanical and its output is cheap to verify, route that part through ollm.
---

# local-offload

Route bounded **mechanical sub-steps** to the local Ollama fleet via `ollm` instead of
doing them inline on Claude tokens. This machine's roster is injected at session start
by the `ollama-roster.sh` hook; `ollm --list` shows it on demand.

## The one gate: ROI

Offload when *(assemble context + verify output)* is cheaper than doing it yourself.
That's the whole test. Corollaries:

- **Sub-steps, not whole tasks.** A big task usually contains offloadable chunks
  (triage this log, draft this table, summarize this diff) even when the task itself
  must stay on Claude.
- **Scale verification to stakes.** A commit-message draft needs a glance; generated
  boilerplate needs a read-through; anything load-bearing needs real review. A flat
  "audit everything exhaustively" tax kills the ROI — don't pay it where stakes are low.
- **Stakes × verifiability decide, not file count.** A mechanical three-file rename is
  a fine offload; a one-line safety-critical change is not.

Hard limits that stay: local output is untrusted until verified at the level the stakes
demand; never offload where a silently wrong answer is costly (security decisions, data
deletion, published claims); judgment and synthesis stay on Claude.

## Roles

| Role | Fit |
|------|-----|
| `fast` | high-volume, low-stakes text: classify, triage logs/diffs, quick summaries, simple boilerplate (also backs GitLens) |
| `bulk` | heavier coding offload: non-trivial codegen, careful summarization, first-pass code analysis (MLX machines) |
| `brainstorm` | generalist: idea generation, prose summarization, non-code first-pass analysis |
| `vision` | screenshots, charts, diagrams, rough OCR |

## Mechanism

`ollm` is on PATH (works from any shell, including Claude's Bash tool). Prompt from
args; pipe context via stdin; the model's text is the only thing on stdout.

```sh
git diff | ollm "One-line summary of this diff"
ollm --role bulk "Write pytest cases for this function:" < src/foo.py
ollm --role vision --image build-status.png "What does this dashboard show?"
ollm --role brainstorm "Ten names for a CLI that snapshots dotfiles"
ollm --list    # roles, resolved tags, installed state
```

Thinking is disabled by default (hidden reasoning otherwise consumes the whole token
budget and returns an empty response); `--think` opts in on models that support it.
`--num-predict` (default 4096) bounds output length.

## Degrades gracefully

No `ollama`, server down, or a role's model missing → `ollm` fails fast with a clear
error and you just do the work on Claude as usual. Never block on the local fleet;
it is an accelerator, not a dependency.
