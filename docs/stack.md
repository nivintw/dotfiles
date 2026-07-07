# The Stack

The headline tools, by role — the shell, terminal, package managers, editor, and
AI tooling this repo provisions, plus the few behavior notes worth knowing. The full
list lives in the [`Brewfile`](https://github.com/nivintw/dotfiles/blob/main/Brewfile)
and [`uv_tools.txt`](https://github.com/nivintw/dotfiles/blob/main/uv_tools.txt).

## Shell

[**fish**](https://fishshell.com/) is the login shell by default;
[**zsh**](https://www.zsh.org/) is a fully-supported, selectable opt-in
(`install.sh --shell zsh`, persisted for the next run). Both config trees are always
stowed regardless of which one is selected, each wired to the same curated set of
modern replacements.

| Tool | Role |
| --- | --- |
| [fish](https://fishshell.com/) | The default login shell |
| [zsh](https://www.zsh.org/) | Opt-in login shell, Homebrew-managed like fish |
| [tide](https://github.com/IlanCosman/tide) | fish prompt (Fisher-managed) |
| [starship](https://starship.rs/) | zsh cross-shell prompt |
| [zinit](https://github.com/zdharma-continuum/zinit) | zsh plugin manager (autosuggestions, syntax highlighting) |
| [fzf.fish](https://github.com/PatrickF1/fzf.fish) | fzf key bindings for fish |
| [atuin](https://atuin.sh/) | SQLite shell history with search |
| [zoxide](https://github.com/ajeetdsouza/zoxide) | Smarter `cd` that learns your habits |
| [eza](https://eza.rocks/) | Modern `ls` with a git column and icons |
| [bat](https://github.com/sharkdp/bat) | `cat` with syntax highlighting |
| [fd](https://github.com/sharkdp/fd) | Friendly, fast `find` |
| [ripgrep](https://github.com/BurntSushi/ripgrep) | Fast recursive grep (`rg`) |
| [sd](https://github.com/chmln/sd) | Intuitive find-and-replace (sane `sed`) |
| [jq](https://jqlang.github.io/jq/) | Command-line JSON processor |
| [jless](https://jless.io/) | Interactive collapsible JSON/YAML viewer |
| [delta](https://github.com/dandavison/delta) | Syntax-highlighting pager for git |
| [difftastic](https://difftastic.wilfred.me.uk/) | Structural (AST-aware) diff, used as `git difftool` |

!!! note "Behavior notes"

    - **atuin** owns ++ctrl+r++ (SQLite history search) in both shells; up-arrow stays
      normal shell history.
    - **eza** aliases `ls`/`ll`/`la`/`lt` in interactive shells.
    - **zoxide** is initialized in `config.fish` (fish) or `.zshrc` (zsh) — no longer a
      Fisher plugin.
    - fish's Tide prompt and zsh's Starship prompt both fall back to a plain prompt inside
      VS Code's terminal, which otherwise breaks AI terminal tool output parsing.
    - zsh gains inline autosuggestions and command syntax highlighting via
      [zinit](https://github.com/zdharma-continuum/zinit)-managed plugins — fish has these
      built in.

## Terminal & multiplexer

| Tool | Role |
| --- | --- |
| [iTerm2](https://iterm2.com/) | Terminal emulator (macOS only) |
| [tmux](https://github.com/tmux/tmux) | Terminal multiplexer |
| [TPM](https://github.com/tmux-plugins/tpm) | tmux plugin manager |
| [extrakto](https://github.com/laktak/extrakto) | Fuzzy-extract scrollback text (`prefix + Tab`) |
| [tmux-yank](https://github.com/tmux-plugins/tmux-yank) | Copy selections to the system clipboard |
| [vim-tmux-navigator](https://github.com/christoomey/vim-tmux-navigator) | `Ctrl-h/j/k/l` between panes and vim splits |
| [MesloLGS NF](https://github.com/ryanoasis/nerd-fonts) | Nerd Font for the iTerm2 profile |

iTerm reads its preferences straight from the tracked `iterm2/` folder — macOS only,
skipped on Linux/WSL2. tmux plugins are declared in `tmux.conf` and installed by TPM
during the bootstrap on every OS.

## Package managers

### :material-beer: [Homebrew](https://brew.sh)

Formulae, GUI casks, and fonts — all declared in the `Brewfile`, installed with
`brew bundle`. On Linux/WSL2, `install.sh` self-bootstraps Homebrew's own Linux build
(`/home/linuxbrew/.linuxbrew`) the same way; Homebrew's Linux build has no cask support,
so `--core` (formulae only, casks stripped) is required there, not just preferred.

### :material-flash: [uv](https://docs.astral.sh/uv/)

Python toolchain and CLI tools (`uv tool install` from `uv_tools.txt`):
[ansible](https://www.ansible.com/),
[ansible-dev-tools](https://ansible.readthedocs.io/projects/dev-tools/) (`molecule`),
[checkov](https://www.checkov.io/),
[commitizen](https://commitizen-tools.github.io/commitizen/),
[copier](https://copier.readthedocs.io/),
[jc](https://github.com/kellyjonbrazil/jc),
[playwright](https://playwright.dev/python/),
[prek](https://github.com/j178/prek),
[reuse](https://reuse.software/),
[rumdl](https://github.com/rvben/rumdl),
[serena](https://github.com/oraios/serena) (self-hosted MCP server, pinned to a commit SHA),
and [yq](https://github.com/mikefarah/yq).

## Editor

[**VS Code**](https://code.visualstudio.com/), with extensions declared in the Brewfile
so they install with everything else.

| Extension | Role |
| --- | --- |
| [Ruff](https://docs.astral.sh/ruff/) | Python lint + format |
| [Pylance](https://marketplace.visualstudio.com/items?itemName=ms-python.vscode-pylance) | Python language server |
| [GitLens](https://www.gitkraken.com/gitlens) | Git blame / history / authorship lenses |
| [Even Better TOML](https://marketplace.visualstudio.com/items?itemName=tamasfe.even-better-toml) | TOML support |
| [rumdl](https://github.com/rvben/rumdl) | Rust Markdown linter/formatter |
| [Prettier](https://prettier.io/) | Formatter for JSON/YAML/web (Markdown scoped off) |
| [ShellCheck](https://www.shellcheck.net/) | Shell static analysis in the editor |
| [hadolint](https://github.com/hadolint/hadolint) | Dockerfile linter |
| [EditorConfig](https://editorconfig.org/) | Apply per-project `.editorconfig` rules |

!!! note "rumdl vs Prettier"

    Both format Markdown, so the split is explicit: **rumdl owns `.md`**, Prettier handles
    everything else (`prettier.disableLanguages: ["markdown"]` in the generated settings).

!!! warning "Settings Sync"

    `settings.json` is generated at install time from the tracked `vscode_settings.json`
    baseline (see [Architecture](architecture.md)) — it's no longer a stowed symlink. If
    VS Code Settings Sync is also on, a cloud pull wins — pick one source of truth, not both
    for the same file.

## AI tooling

### [Claude Code](https://github.com/anthropics/claude-code)

Installed via the native, self-updating installer (chosen over a brew cask precisely so it
stays current). MCP servers are declared in `claude_mcp.json` and registered at install
time.

### [Ollama](https://ollama.com/) — a local role fleet for GitLens & Claude offload

The installer provisions a fleet of role models declared in `scripts/ollama_models.sh`:

- a **fast** tier ([`qwen3:4b-instruct-2507-q4_K_M`](https://ollama.com/library/qwen3)),
  which also serves GitLens' AI features entirely offline — no cloud key, no Copilot seat;
- a **vision** tier (`qwen3-vl:4b-instruct`); and
- on Apple Silicon with >32&nbsp;GB unified memory (macOS&nbsp;13+), the big pair:
  **bulk** coding (`qwen3.5:35b-a3b-coding-nvfp4`, MLX) and a **brainstorm** generalist
  (`gemma4:26b`).

All pulls are idempotent. The [ollm](commands.md) CLI fronts the fleet — it picks the
model by role, disables hidden thinking by default (the reasoning models otherwise burn
their whole token budget on it), and a SessionStart hook shows Claude Code the live roster
so bulk mechanical work gets routed off the paid token budget.
