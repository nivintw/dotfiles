# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

if test "$TERM_PROGRAM" = vscode
    # Use simple prompt in VS Code
    # The tide prompt seems to break AI terminal tool output parsing
    function fish_prompt
        echo (prompt_pwd)' $ '
    end
else
    # Use Tide everywhere else
    # Tide is already configured via Fisher
end

zoxide init fish | source

if status is-interactive
    # Commands to run in interactive sessions can go here
    # These are things we want to _only_ happen in interactive sessions.
end

# -------------- Configure direnv for Python virtual environments --------------
# https://direnv.net/docs/hook.html
direnv hook fish | source
set -g direnv_fish_mode eval_on_arrow
