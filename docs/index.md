# dotfiles

**Setting up my new computer: clone. run. done.**

Tyler Nivin's personal, idempotent bootstrap for **macOS, Linux, and WSL2** — one command
(`install.sh`) converges a fresh machine to a declared state via Homebrew, GNU Stow, and
fish (zsh selectable via `--shell zsh`). Built to be forked: the machinery is generic, the
package list / Dock / keys are his.

## Quick start

--8<-- "install.md"

## Explore the docs

<div class="grid cards" markdown>

- :material-rocket-launch-outline: **[Getting Started](getting-started.md)**

    Clone, run `install.sh`, and what each of its phases does — which are macOS-only vs.
    cross-platform, forking it, the human-only steps, and uninstalling.

- :material-sitemap-outline: **[Architecture](architecture.md)**

    How `home/` mirrors `$HOME` via GNU Stow, what isn't stowed and why, the machine-local
    overlay pattern, and the idempotency contract.

- :material-layers-outline: **[The Stack](stack.md)**

    The tools by role — fish or zsh, the modern-CLI replacements, terminal/multiplexer,
    package managers, the editor, and the local Ollama AI fleet.

- :material-console-line: **[Commands](commands.md)**

    The custom fish functions — fuzzy git, live search, process kill, clipboard/open
    helpers, local AI offload via `ollm` — most with a zsh port too.

- :material-check-decagram-outline: **[Quality &amp; Testing](quality.md)**

    The prek hook suite, the bats + pytest layers, the CI pipeline, the Tart VM idempotency
    harness, and REUSE licensing.

- :material-shield-lock-outline: **[Security](security.md)**

    1Password-based secret handling, SSH-host hygiene, and the defense-in-depth control
    list.

</div>

## Idempotent by design

Re-run `install.sh` any time. It converges the machine to the declared state instead of
clobbering it: `brew bundle` adopts already-installed casks in place, `stow` refuses to
overwrite existing real files, and the MCP / symlink / shell steps no-op once they're done.
The two declarative system steps are the deliberate exception — `macos.sh` re-asserts its
preferences and `dock.sh` rebuilds the Dock from its list every run.
