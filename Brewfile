# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# Brewfile — curated desired state, NOT a dump of what's installed.
#
# This is the source of truth for Homebrew formulae and casks. Hand-edit it;
# do not regenerate with `brew bundle dump` (that scrapes everything installed,
# including cruft you don't want).
#
# Grouped by purpose (alphabetical within each group) so the rationale reads at
# a glance. The grouping is cosmetic — `brew bundle` ignores the comments.
#
# Install everything listed here (and nothing it removes by default):
#   brew bundle install --file=~/dotfiles/Brewfile
#
# See what's installed but NOT listed here (candidates to prune by hand):
#   brew bundle cleanup --file=~/dotfiles/Brewfile
#
# Apply the cleanup (uninstall anything not listed) — review the list first:
#   brew bundle cleanup --force --file=~/dotfiles/Brewfile
#
# NOTE on VS Code: `brew bundle cleanup` would otherwise also uninstall any VS
# Code extension not listed below. Most extensions are managed by VS Code
# Settings Sync (not this file), so cleanup is told to skip extensions via
# HOMEBREW_BUNDLE_CLEANUP_NO_VSCODE=1 (set in conf.d/01_brew.fish). Only the
# extensions in the "VS Code extensions" section below are installed by bundle.

# ---------------------------------------------------------------------------
# Taps (third-party formula/cask sources)
# ---------------------------------------------------------------------------
tap "terraform-linters/tap"   # Source for the tflint cask below

# ===========================================================================
# Formulae (CLI tools)
# ===========================================================================

# --- Shell & navigation ----------------------------------------------------
brew "atuin"            # SQLite shell history w/ search (rebinds Ctrl+R; see conf.d/atuin.fish)
brew "bash"             # Modern Bash 5.x (Apple ships 3.2); also a dep of direnv
brew "direnv"           # Load/unload environment variables based on $PWD
brew "fish"             # The shell. A brew upgrade can disturb an open session until restart.
brew "fzf"              # Command-line fuzzy finder
brew "zoxide"           # Smarter cd that learns your habits

# --- Terminal & remote sessions --------------------------------------------
brew "asciinema"        # Record and share terminal sessions
brew "mosh"             # Remote terminal application (roaming, low-latency)
brew "tmux"             # Terminal multiplexer

# --- Dotfiles bootstrap & macOS management ---------------------------------
brew "dockutil"         # Scriptable macOS Dock — drives dock.sh
brew "duti"             # Set default apps for file types / URL schemes
brew "mas"              # Mac App Store CLI — installs the `mas` apps listed below
brew "pam-reattach"     # Makes Touch ID sudo work inside tmux (see install.sh sudo_local)
brew "stow"             # Symlink farm manager — deploys this dotfiles repo into $HOME
brew "topgrade"         # One command to update brew + mas + uv + fisher + more

# --- Modern CLI file & text tools ------------------------------------------
brew "bat"              # cat(1) clone with syntax highlighting and Git integration
brew "eza"              # Modern ls with a git-status column and icons
brew "fd"               # Simple, fast, user-friendly alternative to find
brew "glow"             # Terminal markdown renderer
brew "jless"            # Interactive collapsible JSON/YAML viewer (pairs with jq)
brew "jq"               # Lightweight, flexible command-line JSON processor
brew "ripgrep"          # Fast recursive grep (rg) — the natural companion to fd/fzf/bat
brew "sd"               # Intuitive find-and-replace (sane sed)
brew "tree"             # Display directories as trees

# --- Git & version control -------------------------------------------------
brew "difftastic"       # Structural (AST-aware) diff; used as `git difftool`
brew "gh"               # GitHub command-line tool
brew "git"              # Distributed revision control system
brew "git-delta"        # Syntax-highlighting pager for git diff/log/show
brew "git-filter-repo"  # Fast history rewriting / secret removal
brew "git-lfs"          # Git Large File Storage — run `git lfs install` once after install
brew "gource"           # Version control visualization tool

# --- Code quality & dev tooling --------------------------------------------
brew "bats-core"        # Bash automated testing system
brew "gitleaks"         # Secret scanner (pre-commit hook; see .pre-commit-config.yaml)
brew "hadolint"         # Smarter Dockerfile linter
brew "hawkeye"          # SPDX license-header formatter (pre-commit; REUSE compliance)
brew "hyperfine"        # Command-line benchmarking tool
brew "shellcheck"       # Static analysis for shell scripts
brew "taplo"            # TOML toolkit
brew "typos-cli"        # Source-code spell checker

# --- Containers & Kubernetes -----------------------------------------------
brew "k9s"              # Kubernetes CLI to manage your clusters in style
brew "lazydocker"       # TUI for Docker / Compose
brew "trivy"            # Vulnerability/misconfig scanner

# --- Networking ------------------------------------------------------------
brew "iperf3"           # Network throughput measurement (homelab)
brew "mtr"              # traceroute + ping in one network diagnostic (homelab)
brew "nmap"             # Port scanning utility for large networks
brew "step"             # smallstep CLI — private CA, X.509/SSH certs, ACME, mTLS
brew "wget"             # Internet file retriever

# --- System monitoring & disk ----------------------------------------------
brew "btop"             # Resource monitor — CPU/mem/disk/net graphs (replaces htop)
brew "ncdu"             # Interactive disk-usage explorer

# --- Misc utilities --------------------------------------------------------
brew "md5sha1sum"       # Hash utilities
brew "terminal-notifier" # Send macOS notifications from scripts (long runs)

# ===========================================================================
# Casks (GUI apps)
# ===========================================================================

# --- Security & secrets ----------------------------------------------------
cask "1password"             # Password manager (desktop app + browser extensions)
cask "1password-cli"         # `op` CLI; backs git SSH signing via op-ssh-sign
cask "suspicious-package"    # Inspect .pkg installer contents before running them

# --- Terminal, editor & fonts ----------------------------------------------
cask "font-meslo-for-powerlevel10k"  # MesloLGS NF — the iTerm2 profile font (romkatv build)
cask "iterm2"                # Terminal emulator
cask "visual-studio-code"    # VS Code (sign in to sync extensions/settings)

# --- Browsers --------------------------------------------------------------
cask "firefox"               # Firefox browser
cask "google-chrome"         # Google Chrome

# --- Dev & infrastructure --------------------------------------------------
cask "claude"                # Claude Desktop
cask "ollama-app"            # Ollama.app — local LLM runner (menu-bar GUI; self-updates, by choice)
cask "rancher"               # Rancher Desktop (container runtime)
cask "tflint"                # Terraform linter (from terraform-linters/tap)

# --- Productivity & notes --------------------------------------------------
cask "anki"                  # Spaced-repetition flashcards
cask "microsoft-office"      # Office 365 (Word/Excel/PowerPoint/Outlook/OneNote + OneDrive). Bundles "Defender Shim"; conflicts with a standalone onedrive cask, so don't add one.
cask "obsidian"              # Second-brain / notes

# --- System utilities ------------------------------------------------------
cask "appcleaner"            # Thorough app uninstaller (catches leftover support files)
cask "resilio-sync"          # Peer-to-peer file sync

# --- Media & gaming --------------------------------------------------------
cask "discord"               # Discord
cask "openemu"               # Retro game console emulator
cask "steam"                 # Steam game client

# --- Hardware & 3D printing ------------------------------------------------
cask "creality-print"        # Slicer for Creality FDM 3D printers
cask "raspberry-pi-imager"   # Flash Raspberry Pi OS images to SD cards

# ===========================================================================
# VS Code extensions (installed via `code --install-extension` by brew bundle)
# A curated mix of the work laptop's python-project-template set plus picks from
# this machine's installed extensions. Most are also carried by VS Code Settings
# Sync; listing them here guarantees them at bootstrap. See the VS Code cleanup
# NOTE in the header (cleanup leaves Sync-managed extensions alone).
# Comments are intentionally left unaligned: the IDs span a wide range, so
# column-aligning to the longest reads worse than a single space.
# ===========================================================================

# AI assistance
vscode "anthropic.claude-code" # Claude Code in the editor

# General editing
vscode "aaron-bond.better-comments"  # Color-coded comment tags (TODO, FIXME, etc.)
vscode "tyriar.sort-lines"           # Sort selected lines
vscode "mrmlnc.vscode-duplicate"     # Duplicate files/dirs from the explorer
vscode "chouzz.vscode-better-align"  # Align =, :, => and trailing-comment columns
vscode "gruntfuggly.todo-tree"       # Tree view of TODO/FIXME tags (pairs with better-comments)
vscode "nhoizey.gremlins"            # Highlight invisible / zero-width characters
vscode "sleistner.vscode-fileutils"  # Fast move/rename/duplicate file commands
vscode "xisabla.title-comments"      # Decorative section/banner comments

# Remote & collaboration
vscode "ms-vscode-remote.vscode-remote-extensionpack"  # Remote Dev pack (SSH, containers, dev containers; pulls the rest)
vscode "ms-vsliveshare.vsliveshare"                    # Live Share — real-time collaborative editing

# Git & forge
vscode "eamodio.gitlens"                         # Git blame / history / authorship lenses
vscode "vivaxy.vscode-conventional-commits"      # Guided conventional-commit messages
vscode "codezombiech.gitignore"                  # Pull canonical .gitignore templates (github/gitignore)
vscode "piotrpalarz.vscode-gitignore-generator"  # Generate .gitignore from gitignore.io
vscode "qezhu.gitlink"                           # Open the current file/line in the remote git host
vscode "gitlab.gitlab-workflow"                  # GitLab MRs / pipelines / issues

# Python
vscode "charliermarsh.ruff"            # Ruff lint + format (matches your uv/prek ruff)
vscode "ms-python.python"              # Python language support
vscode "ms-python.vscode-pylance"      # Pylance language server
vscode "ms-python.debugpy"             # Python debugger
vscode "ms-python.vscode-python-envs"  # Python environment management
vscode "njpwerner.autodocstring"       # Generate Python docstrings

# Notebooks
vscode "ms-toolsai.jupyter" # Jupyter notebooks (pulls keymap/renderers as deps)

# Config & markup
vscode "tamasfe.even-better-toml"       # TOML support (same author/engine as taplo)
vscode "rvben.rumdl"                    # Rust markdown linter/formatter (reads .rumdl.toml)
vscode "samuelcolvin.jinjahtml"         # Jinja + HTML template syntax
vscode "editorconfig.editorconfig"      # Apply per-project .editorconfig rules
vscode "redhat.vscode-yaml"             # YAML language support
vscode "hashicorp.hcl"                  # HCL syntax (non-Terraform HCL files)
vscode "deitry.apt-source-list-syntax"  # apt sources.list syntax
vscode "dotenv.dotenv-vscode"           # .env highlighting, autocomplete, peeking (cloud/vault features opt-in — never log in to ignore them)
# vscode "irongeek.vscode-env"          # simpler alternative: lightweight .env highlighting + formatter, no cloud code at all
vscode "esbenp.prettier-vscode"         # Prettier (JSON/YAML/web) — scope off Markdown so it doesn't fight rumdl (see software_list)

# Markdown (preview & editing)
vscode "bierner.github-markdown-preview"      # GitHub-flavored preview pack (emoji/checkbox/footnotes)
vscode "bierner.markdown-image-size"          # Set image dimensions in preview
vscode "bierner.markdown-yaml-preamble"       # Render YAML front matter in preview
vscode "bierner.emojisense"                   # Emoji autocomplete
vscode "simonguo.vscode-markdown-table-sort"  # Sort Markdown tables

# Shell, tests & spelling
vscode "timonwong.shellcheck"                   # ShellCheck in the editor (uses the brew shellcheck)
vscode "jetmartin.bats"                         # Bats test syntax (you have bats-core in brew)
vscode "tekumara.typos-vscode"                  # typos in the editor (matches your ~/.typos.toml)
vscode "streetsidesoftware.code-spell-checker"  # Dictionary spell-check (broader than typos; catches novel misspellings)
vscode "bmalehorn.vscode-fish"                  # fish shell syntax (you edit fish config)

# Containers, Kubernetes & IaC
vscode "docker.docker"                                # Docker DX (Dockerfile/compose tooling)
vscode "jeff-hykin.better-dockerfile-syntax"          # Finer Dockerfile coloring (embedded shell in RUN); needs a rich theme; stale grammar
vscode "ms-azuretools.vscode-containers"              # Container Tools
vscode "ms-kubernetes-tools.vscode-kubernetes-tools"  # Kubernetes manifests / clusters
vscode "hashicorp.terraform"                          # Terraform language support
vscode "exiasr.hadolint"                              # Dockerfile linter (uses the brew hadolint binary)
vscode "XargsUK.checkov-prismaless"                   # Checkov IaC scanning, Prisma-free fork

# Cloud & AWS
vscode "bin3377.iam-policy"    # AWS IAM policy editing
vscode "boto3typed.boto3-ide"  # boto3 type hints / autocomplete

# Data, diagrams & files
vscode "mechatroner.rainbow-csv"              # CSV column coloring / queries
vscode "randomfractalsinc.vscode-data-table"  # Tabular data viewer
vscode "moshfeu.compare-folders"              # Diff two folders
vscode "hediet.vscode-drawio"                 # draw.io diagrams in-editor
vscode "tomoki1207.pdf"                       # View PDFs in-editor (handy even if less essential on macOS)

# Themes & appearance
vscode "vira.vsc-vira-theme"      # Vira theme (also provides icons; replaces material-icon-theme)
vscode "johnpapa.vscode-peacock"  # Tint each workspace a different color
vscode "azemoh.one-monokai"       # One Monokai theme
vscode "liviuschera.noctis"       # Noctis theme family
vscode "silofy.hackthebox"        # HackTheBox theme

# ---------------------------------------------------------------------------
# Mac App Store apps (installed via `mas`; requires being signed into the Store)
# IDs from `mas list`. Regenerate that view anytime with: mas list
# ---------------------------------------------------------------------------
mas "1Password for Safari", id: 1569813296   # Safari extension for 1Password
mas "Calca",                id: 635758264    # Markdown calculator
mas "Home Assistant",       id: 1099568401   # Home Assistant companion app
mas "Kindle",               id: 302584613    # Kindle reader
mas "The Unarchiver",       id: 425424353    # Archive extractor
