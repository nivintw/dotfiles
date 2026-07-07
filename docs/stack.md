# The Stack

The headline tools, by role.

## Shell

fish is the login shell by default; zsh is a fully-supported, selectable opt-in
(`install.sh --shell zsh`, persisted for the next run). Both config trees are always stowed
regardless of which is selected, each wired to the same curated set of modern replacements:
tide (fish's prompt) or starship (zsh's), fzf.fish (fish) / zinit-managed zsh-autosuggestions
+ zsh-syntax-highlighting (zsh — closing the fish-parity gap, since fish has these built in),
atuin, zoxide, eza, bat, fd, ripgrep, sd, jq, jless, delta, difftastic.

atuin owns ++ctrl+r++ (SQLite history search) in both shells; up-arrow stays normal shell
history. eza aliases `ls`/`ll`/`la`/`lt`. zoxide is initialized in `config.fish` (fish) or
`.zshrc` (zsh) — no longer a fisher plugin. Both prompts fall back to a plain one inside VS
Code's terminal, which otherwise breaks AI terminal tool output parsing.

## Terminal &amp; multiplexer

iTerm2 (macOS only — skipped on Linux/WSL2), tmux, TPM, extrakto, tmux-yank,
vim-tmux-navigator, MesloLGS NF. iTerm reads its preferences straight from the tracked
`iterm2/` folder; tmux plugins are declared in `tmux.conf` and installed by TPM on every OS.

## Package managers

- **Homebrew** — formulae, GUI casks, and fonts, all declared in the `Brewfile`, installed
  with `brew bundle`. On Linux/WSL2, `install.sh` self-bootstraps Homebrew's own Linux build
  (`/home/linuxbrew/.linuxbrew`) the same way; Homebrew's Linux build has no cask support, so
  `--core` (formulae only, casks stripped) is required there, not just preferred.
- **uv** — Python toolchain and CLI tools (`uv tool install` from `uv_tools.txt`): ansible,
  ansible-dev-tools, checkov, commitizen, copier, prek, reuse, rumdl, yq, jc, serena.

## Editor

VS Code, with extensions declared in the Brewfile so they install with everything else: Ruff,
Pylance, GitLens, Even Better TOML, rumdl, Prettier, ShellCheck, hadolint, EditorConfig.
rumdl owns `.md`; Prettier handles everything else (`prettier.disableLanguages: ["markdown"]`).
`settings.json` is generated at install time from the tracked `vscode_settings.json` baseline
(see [Architecture](architecture.md#machine-local-overlays)) — it's no longer a stowed
symlink.

!!! warning "Settings Sync"
    If VS Code Settings Sync is also on, a cloud pull wins — pick one source of truth, not
    both. (Settings Sync also installs the `vscode` extensions out of band, which is why the
    install verifier excludes those extension lines from its Homebrew-baseline check.)

## AI tooling

- **Claude Code** — installed via the native, self-updating installer. MCP servers are
  declared in `claude_mcp.json` and registered at install time.
- **Ollama → a local role fleet for GitLens &amp; Claude offload** — role models from
  `scripts/ollama_models.sh`: a fast tier (`qwen3:4b-instruct-2507-q4_K_M`, also serving
  GitLens' AI features entirely offline), a vision tier (`qwen3-vl:4b-instruct`), and — on
  Apple Silicon with &gt;32 GB unified memory — the big pair: bulk coding
  (`qwen3.5:35b-a3b-coding-nvfp4`, MLX) and a brainstorm generalist (`gemma4:26b`). All pulls
  are idempotent. The `ollm` CLI fronts the fleet — picks the model by role, disables hidden
  thinking by default, and a SessionStart hook shows Claude Code the live roster.
