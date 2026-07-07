# Commands

Beyond the third-party tools on [The Stack](stack.md), the repo adds a small set of custom
fish functions in `home/.config/fish/functions/`. The interesting ones are fzf-driven — fuzzy
git checkout, live full-text search, a process picker. Most of these — everything except the
fuzzy-git pickers, `fsearch`, `pset`, and the multi-repo helpers — have a zsh port in
`home/.config/zsh/functions/` with equivalent behavior.

## Fuzzy git

fzf pickers over git, each with a commit-log preview pane. Type to filter, ++enter++ to act.

- `fco` — fuzzy-checkout any branch, local or remote (remotes get a tracking branch
  automatically).
- `fcor` · `gcor` — two recency-oriented siblings of `fco`: `fcor` lists local branches by
  most-recent commit; `gcor` pulls from the reflog, so it surfaces branches visited even after
  their remote was deleted.
- `gccd` — `git clone` then `cd` into the new directory in one step.

## Search &amp; jump to code

ripgrep into fzf into `$EDITOR` — pick a match and land on the exact `file:line`.

- `fif` — "find in files": ripgrep re-runs on every keystroke with a preview pane; ++enter++
  opens the hit in your editor.
- `fsearch` — the one-shot variant: run ripgrep once for a pattern, fuzzy-filter the results,
  open the pick. Lighter than `fif` when you already know the term.

## Processes &amp; the shell

- `fkill` — multi-select process picker over `ps` in fzf: filter, ++tab++ to mark several,
  ++enter++ to kill. Sends SIGTERM by default (`fkill 9` for SIGKILL), and offers to retry
  under `sudo` if a kill is denied.
- `wtfis` — "what is this?": resolves a name to alias / function / builtin / binary, following
  symlinks.
- `pset` — set an environment variable from a hidden prompt — the value never touches the
  command line or shell history.
- `pubkey` — print an SSH public key and copy it to the clipboard in one move. With no
  argument it discovers the key from the running agent (1Password, the macOS keychain, or a
  plain ssh-agent), falling back to `~/.ssh/*.pub`. On WSL it copies via win32yank when
  present (codepage-clean, no trailing CR), falling back to `clip.exe`.
- `dnsflush` — flush the DNS resolver cache. macOS bounces `mDNSResponder`; Linux uses
  `resolvectl`, falling back to the older `systemd-resolve --flush-caches`; on WSL it points
  you at the Windows host (`ipconfig /flushdns`).

## Many directories at once

Fan a command out across a tree — both handle paths with spaces/newlines safely.

- `gs-all` — `git status` across every repo under `$PWD` at once. `gp-all` is the
  `git pull --ff-only` sibling.
- `eachdir` · `forrepos` — the generic engines underneath. `eachdir <cmd>` runs a command in
  each immediate subdirectory; `forrepos <cmd>` runs it at the root of every git repo in the
  tree (recursively). `gs-all`/`gp-all` are just `forrepos` with a fixed command.

!!! danger "No dry-run, no confirmation"
    `forrepos` runs your command in *every* repo it finds, with no preview. As a guard it
    refuses to run from `$HOME` or `/` (symlinks resolved), so a destructive command can't fan
    out across every repo you own — `cd` into a specific project subtree first.

## Housekeeping

- `pyclean --dry-run` — preview the Python caches (`__pycache__`, `.pytest_cache`,
  `.mypy_cache`, `.ruff_cache`, `*.pyc`) it would delete; drop `--dry-run` to remove them.
- `git_prune_local` — delete local branches already merged into `main`, detecting normal,
  rebase, *and* squash merges, and keeping a branch whose remote is gone but whose commits
  aren't in `main` yet. `--dry-run` shows the plan first. The one function with its own full
  bats matrix, because a bug here deletes work.
- `launch-docs` — serve this docs site locally (`python -m http.server`), pick a free port,
  open the browser once it's up. Its readiness probe is a dependency-free python3 socket check,
  so it works identically on macOS, Linux, and WSL.
- `dotfiles-doctor` — re-derive the intended install end state and report it (Homebrew
  packages, login shell, Touch ID for sudo, the firewall, key symlinks, generated Claude
  settings, the gitconfig overlay, the pre-push hook's provenance), exiting non-zero if
  anything needs attention. Read-only, never needs sudo — runs `dotfiles-install --verify`
  under the hood.

## Local AI offload

One command fronting the local Ollama fleet the installer provisions (see
[The Stack](stack.md#ai-tooling)). Unlike the fish functions above it's a plain bash script
stowed onto `PATH` (`~/.local/bin/ollm`), so it works from any shell — including Claude Code's
non-interactive one, its primary caller.

- `ollm` — one-shot generation against a local model picked by role
  (`--role fast|bulk|brainstorm|vision`), with the role→model mapping read from
  `scripts/ollama_models.sh` so it can never drift from what the installer pulled. Prompt from
  arguments, context piped via stdin (`git diff | ollm "summarize this diff"`), `--image` for
  the vision model, and only the model's text on stdout so it composes in pipes. `ollm --list`
  prints the roster with installed state.
- `ollm --tools` — opt-in agentic mode: the model gathers its own context via three read-only
  tools (`read_file`, `grep`, `ls`) sandboxed to `--tools-root` (default: the current
  directory). Every tool path is resolved and checked against that root, defeating both `../`
  traversal and symlink escapes; no writes, no shell, no network beyond Ollama itself.

## Abbreviations &amp; aliases

The muscle-memory layer, in `conf.d/`. Abbreviations expand inline as you type (you see the
real command before it runs); aliases are interactive-only, so scripts still get the real
binaries.

| Type | Short | Expands to |
| --- | --- | --- |
| abbr | `gco` | `git checkout` |
| abbr | `gst` | `git status` |
| abbr | `gp` | `git pull` |
| abbr | `gl` | `git log --oneline --graph --decorate` |
| abbr | `k` | `kubectl` |
| abbr | `ka` | `kubectl apply -f` |
| alias (eza) | `ls` | `eza --group-directories-first` |
| alias (eza) | `ll` | `eza -l --git --icons=auto …` |
| alias (eza) | `la` | `eza -la --git --icons=auto …` |
| alias (eza) | `lt` | `eza --tree --level=2 --icons=auto` |

These are personal — bend them to your own habits. `wtfis <name>` is the quickest way to see
what any short command currently resolves to on your machine.
