# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function gp-all --description "git pull --ff-only across every repo under the current tree"
    forrepos git pull --ff-only
end
