# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# Keep $path (and the $PATH string it's tied to) free of duplicates, so the conf.d
# snippets below can unconditionally prepend their directory without a manual
# ":$PATH:"-matching guard (fish_add_path is idempotent the same way).
typeset -U path

# conf.d/*.zsh loads in alphabetical order, mirroring fish's automatic conf.d directory —
# zsh has no built-in equivalent, so this loop is the whole mechanism. The (N) glob
# qualifier makes the glob expand to nothing (instead of erroring) if conf.d is ever empty.
for _dotfiles_conf in "$ZDOTDIR"/conf.d/*.zsh(N); do
    source "$_dotfiles_conf"
done
unset _dotfiles_conf

# Autoload every ported function by name (fpath + autoload -Uz), mirroring fish's
# functions/ autoloading. Almost every file defines one function named exactly after the
# file (zsh sources it lazily, on first call) — pubkey is the one exception, carrying an
# explicit trailing self-call because it also defines a private helper (see that file's
# own comment for why). The :t glob modifier keeps just the filename.
fpath=("$ZDOTDIR/functions" $fpath)
autoload -Uz "$ZDOTDIR"/functions/*(N:t)

# In VS Code, override Starship with a plain prompt — Tide (fish's prompt) breaks AI
# terminal tool output parsing and Starship's styled segments carry the same risk, so the
# same guard applies here. Starship is the default everywhere else (see Brewfile).
if [[ "$TERM_PROGRAM" == vscode ]]; then
    PROMPT='%~ %# '
else
    command -v starship >/dev/null 2>&1 && eval "$(starship init zsh)"
fi

# Guard each init on its tool being present so a machine without zoxide/direnv (e.g. a
# fresh clone, mid-bootstrap) doesn't spew "command not found" per shell.
command -v zoxide >/dev/null 2>&1 && eval "$(zoxide init zsh)"

# -------------- Configure direnv for Python virtual environments --------------
# https://direnv.net/docs/hook.html
command -v direnv >/dev/null 2>&1 && eval "$(direnv hook zsh)"

# -------------- zinit (plugin manager) --------------
# Standard self-installing bootstrap: clones itself into $ZINIT_HOME on first run, a
# no-op on every run after. Loads the two plugins that close fish's biggest built-in
# gap vs. zsh — inline autosuggestions and command syntax highlighting.
#
# Gated on zinit.zsh itself, not just the directory: a clone that fails partway (network
# drop, disk full) can still leave $ZINIT_HOME present, which would otherwise wedge this
# into "looks installed, never retries." The explicit warning on failure means a broken
# bootstrap is visible instead of surfacing only as an unrelated "command not found" from
# the zinit calls below.
ZINIT_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/zinit/zinit.git"
if [[ ! -f "${ZINIT_HOME}/zinit.zsh" ]]; then
    command mkdir -p "$(dirname "$ZINIT_HOME")"
    if ! command git clone --depth=1 https://github.com/zdharma-continuum/zinit.git "$ZINIT_HOME"; then
        echo "zsh: couldn't bootstrap zinit (git clone failed — network?); autosuggestions/syntax-highlighting won't load. Re-run your shell once connectivity is back, or delete $ZINIT_HOME to retry." >&2
    fi
fi

if [[ -f "${ZINIT_HOME}/zinit.zsh" ]]; then
    source "${ZINIT_HOME}/zinit.zsh"
    zinit light zsh-users/zsh-autosuggestions
    zinit light zsh-users/zsh-syntax-highlighting
else
    echo "zsh: zinit not installed — autosuggestions/syntax-highlighting disabled" >&2
fi
