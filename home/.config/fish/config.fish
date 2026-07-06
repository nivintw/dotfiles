# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

# In VS Code, override Tide with a plain prompt — the Tide prompt breaks AI
# terminal tool output parsing. Tide is the default everywhere else (via Fisher).
if test "$TERM_PROGRAM" = vscode
    function fish_prompt
        echo (prompt_pwd)' $ '
    end
end

# Guard each init on its tool being present so a machine without zoxide/direnv
# (e.g. a fresh clone, mid-bootstrap) doesn't spew "command not found" per shell.
command -q zoxide; and zoxide init fish | source

# -------------- Configure direnv for Python virtual environments --------------
# https://direnv.net/docs/hook.html
if command -q direnv
    direnv hook fish | source
    set -g direnv_fish_mode eval_on_arrow
end

### MANAGED BY RANCHER DESKTOP START (DO NOT EDIT)
set --export --prepend PATH "$HOME/.rd/bin"
### MANAGED BY RANCHER DESKTOP END (DO NOT EDIT)
