# dotfiles

**Setting up a new computer: clone. run. done.**

The one repo cloned onto every machine — Mac, Linux, or WSL2 — and built to be forked. A GNU
Stow symlink farm with a single source of truth, driven by an idempotent Python installer that
is careful never to fight the machine it is setting up.

## Quick start

--8<-- "install.md"

!!! note "Forking?"
    `install.sh` installs *one person's* taste — package list, Dock, keys, macOS defaults.
    Review and edit those before running it. See [Make it yours](getting-started.md#make-it-yours).

## Explore

<div class="grid cards" markdown>

-   :material-rocket-launch: **[Getting Started](getting-started.md)**

    ---

    Clone, run, and what the bootstrap does — phase by phase — plus how to make the repo yours.

-   :material-sitemap: **[Architecture](architecture.md)**

    ---

    A symlink farm with one source of truth, an OS-gated phase registry, and overlays that keep
    machine-specific state out of the tracked repo.

-   :material-package-variant: **[The Stack](stack.md)**

    ---

    The CLI tools, shells, and apps the dotfiles set up — and why each earns its place.

-   :material-console: **[Commands](commands.md)**

    ---

    The custom fish functions the repo ships: what each does, how to invoke it, and its caveats.

-   :material-check-decagram: **[Quality](quality.md)**

    ---

    The prek hook suite, pytest + bats tests, and the CI installer-smoke jobs that run
    `install.sh` end-to-end on real macOS and Linux runners.

-   :material-shield-lock: **[Security](security.md)**

    ---

    Secret hygiene, pinned supply-chain binaries, and the tamper gate that keeps the pins honest.

</div>

## What makes it tick

| Feature | What it gives you |
| --- | --- |
| **GNU Stow** | `home/` mirrors `$HOME` via symlinks — editing `~/.config/fish/config.fish` edits the repo file directly, with no copy or apply step. |
| **Idempotent bootstrap** | Re-run `install.sh` anytime; it adopts existing packages and symlinks instead of clobbering them, converging the machine to the declared state. |
| **Machine-local overlays** | One branch across every machine — work box, homelab, personal — with nothing machine-specific leaking into the public repo. |
| **Quality gate** | A prek hook suite plus bats and pytest, run identically locally and in CI, with installer-smoke jobs that run `install.sh --core` end-to-end on ephemeral macOS *and* Linux runners. |
| **Local AI fleet** | Role-based Ollama models provisioned by the installer; the `ollm` CLI routes mechanical work to them, and a session-start hook shows Claude Code the live roster. |
