# Commands

Beyond the third-party tools on [The Stack](stack.md), the repo adds a small set of
custom [fish](https://fishshell.com/) functions in
[`home/.config/fish/functions/`](https://github.com/nivintw/dotfiles/tree/main/home/.config/fish/functions).
The interesting ones are [fzf](https://github.com/junegunn/fzf)-driven — fuzzy git
checkout, live full-text search, a process picker. They're written in fish; if you
selected [zsh](https://www.zsh.org/) as your login shell, most of them — everything
except the fuzzy-git pickers, `fsearch`, `pset`, and the multi-repo helpers — have a
[zsh port](https://github.com/nivintw/dotfiles/tree/main/home/.config/zsh/functions)
with equivalent behavior.

## At a glance

| Command | What it does |
| --- | --- |
| `fco` | Fuzzy-checkout any branch, local or remote (remotes get a tracking branch automatically). |
| `fcor` | Fuzzy-checkout a local branch, ordered by most-recent commit. |
| `gcor` | Checkout a recently-visited branch, pulled from the reflog. |
| `gccd` | `git clone` then `cd` into the new directory in one step. |
| `fif` | "Find in files": ripgrep re-run on every keystroke, then open the hit in `$EDITOR`. |
| `fsearch` | One-shot ripgrep, fuzzy-filter the results, open the pick. |
| `fkill` | Multi-select process picker over `ps`; kills your selection (SIGTERM by default). |
| `wtfis` | Resolve a name to alias / function / builtin / binary, following symlinks. |
| `pset` | Set an exported env var from a hidden prompt — never touches shell history. |
| `pubkey` | Print an SSH public key and copy it to the clipboard. |
| `dnsflush` | Flush the DNS resolver cache (macOS, WSL guidance, or systemd-resolved). |
| `eachdir` | Run a command in each immediate subdirectory. |
| `forrepos` | Run a command at the root of every git repo under `$PWD` (fans out). |
| `gs-all` | `git status` across every repo under the current tree. |
| `gp-all` | `git pull --ff-only` across every repo under the current tree. |
| `pyclean` | Recursively remove Python caches (`__pycache__`, `*.pyc`, …). |
| `git_prune_local` | Delete local branches already merged into `main` (rebase/squash-aware). |
| `launch-docs` | Serve the `docs/` site locally and open the browser. |
| `dotfiles-doctor` | Re-run the installer's read-only verify checks and report health. |
| `ollm` | One-shot generation against the local Ollama fleet, picked by role. |

!!! tip "Forking?"
    These are mine — bend them to your own habits. `wtfis <name>` (below) is the
    quickest way to see what any short command currently resolves to on your machine.

## Fuzzy git

[fzf](https://github.com/junegunn/fzf) pickers over git, each with a commit-log
preview pane. Type to filter, ++enter++ to act.

### `fco`

Fuzzy-checkout any branch, local or remote. It lists local **and** remote branches,
strips the `remotes/<remote>/` prefix, and dedupes — so checking out a name that only
exists on a remote makes git create a local tracking branch automatically. The preview
pane shows that branch's recent commit graph.

```fish
fco
# type to filter the branch list; Enter checks the pick out
```

<figure class="cast" markdown="1">
  <div class="cast__player"
       data-cast="../casts/fco.cast" data-cols="92" data-rows="22"
       aria-label="Recorded terminal demo of the fco command"></div>

  <figcaption markdown="span">`fco` — fuzzy-checkout any branch, local or remote (remotes get a tracking branch automatically).</figcaption>
</figure>

### `fcor` · `gcor`

Two recency-oriented siblings of `fco`:

- **`fcor`** lists local branches by most-recent commit date (`git for-each-ref
  --sort=-committerdate`).
- **`gcor`** pulls names out of the reflog's "moving from X to Y" entries, so it
  surfaces branches you visited even after their remote was pruned.

### `gccd`

`git clone` then `cd` into the new directory in one step — the directory name is
inferred from the URL, or passed explicitly as a second argument.

```fish
gccd git@github.com:nivintw/dotfiles.git      # cd into dotfiles/
gccd git@github.com:nivintw/dotfiles.git dots # cd into dots/
```

## Search & jump to code

[ripgrep](https://github.com/BurntSushi/ripgrep) into
[fzf](https://github.com/junegunn/fzf) into `$EDITOR` — pick a match and land on the
exact `file:line`.

### `fif`

"Find in files." ripgrep **re-runs on every keystroke** (fzf's own fuzzy filtering is
disabled with `--disabled`, so each change reloads the search), with a `bat`-highlighted
preview of the match line. ++enter++ opens the hit at its exact line in your editor. An
initial pattern can seed the search, or start empty and type.

```fish
fif                 # start empty, search live
fif TODO            # seed the search with a pattern
```

<figure class="cast" markdown="1">
  <div class="cast__player"
       data-cast="../casts/fif.cast" data-cols="92" data-rows="22"
       aria-label="Recorded terminal demo of the fif command"></div>

  <figcaption markdown="span">`fif` — “find in files”: ripgrep re-runs on every keystroke with a `bat` preview; ++enter++ opens the hit in your editor.</figcaption>
</figure>

### `fsearch`

The one-shot variant: run ripgrep **once** for a pattern, fuzzy-filter the results in
fzf, then open the pick. Lighter than `fif` when you already know the term.

```fish
fsearch "def main"
```

## Processes & the shell

### `fkill`

Multi-select process picker over `ps` in [fzf](https://github.com/junegunn/fzf):
filter, ++tab++ to mark several, ++enter++ to kill. Sends `SIGTERM` by default; pass a
signal number or name to override (`fkill 9`, `fkill KILL`). The signal is validated up
front — a number is range-checked (1–64) and a name is checked against what this host's
`kill -l` actually knows — so a typo is caught before anything is killed. If a kill is
denied (usually a permissions issue) and the process is still alive, it offers to retry
under `sudo` — never escalating silently.

```fish
fkill        # SIGTERM the selection
fkill 9      # SIGKILL instead
```

### `wtfis`

"What is this?" Resolves a name to alias / function / builtin / binary, following
symlinks to show where they ultimately point — handy for untangling the `ls`→`eza`
aliases. Accepts one or more names, and returns non-zero if any didn't resolve, so it's
usable in conditionals.

```fish
wtfis ls
# ── ls ──
# ls is an alias for eza --group-directories-first
```

<figure class="cast" markdown="1">
  <div class="cast__player"
       data-cast="../casts/wtfis.cast" data-cols="92" data-rows="16"
       aria-label="Recorded terminal demo of the wtfis command"></div>

  <figcaption markdown="span">`wtfis` — “what is this?”: resolves a name to alias / function / builtin / binary, following symlinks.</figcaption>
</figure>

### `pset`

Set an **exported** environment variable from a **hidden prompt** — the value is typed
at a `read -s` prompt, so it never touches the command line or shell history. The
variable name is validated first.

```fish
pset GITHUB_TOKEN
# GITHUB_TOKEN = ****   (typed silently; not echoed or recorded)
```

### `pubkey`

Print an SSH public key and copy it to the clipboard in one move.

With no argument it **discovers** the key so the same command works on every machine:
first from whatever agent `$SSH_AUTH_SOCK` points at (`ssh-add -L`), then from the
1Password agent's well-known socket, and finally from `~/.ssh/*.pub` on disk. When more
than one key is found it offers an fzf picker labelled by each key's comment (or type +
tail of the blob) with its SHA256 fingerprint appended. Pass a path to copy a specific
key. If no clipboard tool is available it still prints the key and reports honestly that
the copy didn't happen.

```fish
pubkey                       # discover and copy
pubkey ~/.ssh/id_ed25519.pub # copy a specific key
```

### `dnsflush`

Flush the DNS resolver cache — the incantation you can never remember, made
platform-aware:

- **macOS** runs both `dscacheutil -flushcache` and `killall -HUP mDNSResponder`
  (the second is what actually refreshes the resolver).
- **WSL** doesn't flush the Linux cache — name resolution is the Windows host's job, so
  it points you at `ipconfig /flushdns` instead.
- **Linux** with `systemd-resolved` runs `resolvectl flush-caches`.

## Many directories at once

Fan a command out across a tree — both engines handle paths with spaces or newlines
safely (NUL-delimited iteration).

### `eachdir`

`eachdir <cmd>` runs a command in each **immediate** subdirectory, printing a header
per directory.

```fish
eachdir git fetch
```

### `forrepos` · `gs-all` · `gp-all`

`forrepos <cmd>` runs a command at the root of **every git repo** in the tree
(recursively — it finds each `.git`, matching both a normal clone and the `.git` file
of a worktree or submodule). `gs-all` and `gp-all` are just `forrepos` with a fixed
command:

- **`gs-all`** → `git status --short --branch` across every repo.
- **`gp-all`** → `git pull --ff-only` across every repo.

```fish
cd ~/work/some-project
gs-all                       # status of every repo below here
forrepos git fetch --all     # arbitrary command, fanned out
```

<figure class="cast" markdown="1">
  <div class="cast__player"
       data-cast="../casts/gs-all.cast" data-cols="92" data-rows="20"
       aria-label="Recorded terminal demo of the gs-all command"></div>

  <figcaption markdown="span">`gs-all` — `git status` across every repo under `$PWD` at once. `gp-all` is the `git pull --ff-only` sibling.</figcaption>
</figure>

!!! warning "No dry-run, no confirmation — and a `$HOME`/root guard"
    `forrepos` (and the `*-all` helpers) run your command in **every** repo they find,
    with no preview. Great for `git status`; think twice before
    `forrepos git reset --hard`.

    As a guard, `forrepos` **refuses to run from `$HOME` or `/`** — it resolves symlinks
    on both `$PWD` and `$HOME` first (`path resolve`), so a symlink pointing at either
    can't slip past. This stops a destructive command from fanning out across every repo
    you own at once. `cd` into a specific project subtree first.

## Housekeeping

### `pyclean`

Recursively remove Python caches — `__pycache__`, `.pytest_cache`, `.mypy_cache`,
`.ruff_cache`, and `*.pyc` — from the current directory down. `-n`/`--dry-run` lists
what would be removed without deleting anything; an unknown flag or stray argument makes
it fail rather than fall through to the destructive path.

```bash
pyclean --dry-run   # preview
pyclean             # delete
```

<figure class="cast" markdown="1">
  <div class="cast__player"
       data-cast="../casts/pyclean.cast" data-cols="92" data-rows="18"
       aria-label="Recorded terminal demo of the pyclean command"></div>

  <figcaption markdown="span">`pyclean --dry-run` — preview the Python caches (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `*.pyc`) it would delete; drop `--dry-run` to remove them.</figcaption>
</figure>

### `git_prune_local`

Delete local branches already merged into `main` — carefully. It detects normal,
rebase, **and** squash merges, and keeps a branch whose remote is gone but whose commits
aren't in `main` yet. `--dry-run` shows the plan first. This is the one function with
its own full bats test matrix (see the [Quality](quality.md) page), because a bug here
deletes work.

```bash
git_prune_local --dry-run
git_prune_local
```

### `launch-docs`

Serve the repo's `docs/` site locally over `python3 -m http.server` and open the browser
once the server is actually accepting connections (so the first load never races the
listener). It resolves `docs/` without hardcoding a path — honoring `$DOTFILES`, then a
`docs/` in the current repo, then `~/dotfiles/docs` — so it works from any worktree.

It serves on port **8000** by default, or a port you pass; it **refuses a port that's
already in use** rather than opening the browser at a server that isn't yours.

```fish
launch-docs        # http://localhost:8000
launch-docs 9000   # a different port
```

### `dotfiles-doctor`

Re-derive the intended install end state and report it — Homebrew packages, the login
shell, Touch ID for sudo, the firewall, key symlinks, the generated Claude settings, the
gitconfig overlay, and that the repo's pre-push hook is still prek's — exiting non-zero
if anything needs attention. It reads only and never needs sudo (it runs
`dotfiles-install --verify --no-sync`, the same checks the install ends with), so it's
safe to run any time to answer "is my setup still healthy?"

```bash
dotfiles-doctor
```

## Local AI offload

One command fronting the local [Ollama](https://ollama.com/) fleet the installer
provisions (see [The Stack](stack.md)). Unlike the fish functions above, it's a plain
bash script stowed onto `PATH` (`~/.local/bin/ollm`), so it works from any shell —
including Claude Code's non-interactive one, its primary caller.

### `ollm`

One-shot generation against a local model picked by **role** — `--role
fast|bulk|brainstorm|vision`, with the role→model mapping read from
`scripts/ollama_models.sh` so it can never drift from what the installer pulled. The
prompt comes from arguments, context is piped via stdin, `--image` targets the vision
model, and only the model's text lands on stdout so it composes in pipes. It disables
hidden thinking by default (reasoning models otherwise return an empty response after
burning their token budget) and fails fast with a clear message when the server is down.

```bash
git diff | ollm "summarize this diff"
ollm --role bulk "write a fish function that …"
ollm --list        # roles, resolved model tags, and installed state
```

`ollm --list` prints the roster with installed state — the same table a `SessionStart`
hook injects into Claude Code so it knows what's available for offload.

### `ollm --tools`

Opt-in agentic mode: instead of pasting context into the prompt, the model gathers its
own via three **read-only** tools — `read_file`, `grep`, `ls` — sandboxed to
`--tools-root` (default: the current directory). Every tool path is resolved and checked
against that root, defeating both `../` traversal and symlink escapes; there's no write,
shell, or network access beyond talking to Ollama itself. `--tools-cap` bounds the
round-trips so a model that never stops calling tools fails loudly instead of looping
forever. It dispatches to a small companion script, `ollm-tools-loop`, that errors
clearly if the selected model lacks tool-calling capability.

```bash
ollm --tools --tools-root ./src "where is the retry logic defined?"
```

## Abbreviations & aliases

The muscle-memory layer, in
[`conf.d/`](https://github.com/nivintw/dotfiles/tree/main/home/.config/fish/conf.d).
[Abbreviations](https://fishshell.com/docs/current/cmds/abbr.html) expand inline as you
type (you see the real command before it runs); aliases are interactive-only, so scripts
still get the real binaries.

| Type | Short | Expands to |
| --- | --- | --- |
| **abbr** | `gco` | `git checkout` |
| **abbr** | `gst` | `git status` |
| **abbr** | `gp` | `git pull` |
| **abbr** | `gl` | `git log --oneline --graph --decorate` |
| **abbr** | `k` | `kubectl` |
| **abbr** | `ka` | `kubectl apply -f` |
| **alias** ([eza](https://eza.rocks/)) | `ls` | `eza --group-directories-first` |
| **alias** ([eza](https://eza.rocks/)) | `ll` | `eza -l --git --icons=auto …` |
| **alias** ([eza](https://eza.rocks/)) | `la` | `eza -la --git --icons=auto …` |
| **alias** ([eza](https://eza.rocks/)) | `lt` | `eza --tree --level=2 --icons=auto` |
