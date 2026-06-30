# SPDX-FileCopyrightText: © 2026 Tyler Nivin
# SPDX-License-Identifier: MIT

function is_macos --description "Exit 0 when running on macOS (Darwin)"
    test (uname) = Darwin
end
