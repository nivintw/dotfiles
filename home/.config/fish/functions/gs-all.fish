# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function gs-all --description "git status (short) across every repo under the current tree"
    forrepos git -c color.status=always status --short --branch
end
